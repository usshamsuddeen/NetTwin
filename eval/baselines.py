"""Baseline bandit/RCA algorithms for controlled comparisons.

Paper 3: ε-greedy, UCB1, random action baselines vs LinearThompsonBandit.
Paper 4: magnitude-only, onset-only, correlation-only, Granger, PC and
NOTEARS RCA baselines vs CausalNet-Rank.
"""
from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg, optimize, stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nettwin.response.agent import ACTION_KINDS, CTX_DIM
from nettwin.simulator.topology import Topology
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.state import TwinState


# ═══════════════════════════════════════════════════════════════════════════════
# Paper 3 — Bandit Baselines
# ═══════════════════════════════════════════════════════════════════════════════

class RandomBandit:
    """Uniform random action selection — lower bound baseline."""

    def __init__(self, dim: int = CTX_DIM):
        self.dim = dim
        self.rng = np.random.default_rng(42)

    def score(self, kind: str, ctx: np.ndarray) -> float:
        return float(self.rng.uniform(-1, 1))

    def update(self, kind: str, ctx: np.ndarray, reward: float) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        return {"dim": self.dim}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RandomBandit":
        return cls(int(data.get("dim", CTX_DIM)))


class EpsilonGreedy:
    """ε-greedy with decaying exploration."""

    def __init__(self, dim: int = CTX_DIM, eps_start: float = 0.3,
                 eps_min: float = 0.05, decay: float = 0.999):
        self.dim = dim
        self.eps = eps_start
        self.eps_min = eps_min
        self.decay = decay
        self.rng = np.random.default_rng(42)
        self.counts = {k: 0 for k in ACTION_KINDS}
        self.values = {k: 0.0 for k in ACTION_KINDS}

    def score(self, kind: str, ctx: np.ndarray) -> float:
        if self.rng.random() < self.eps:
            return float(self.rng.uniform(-1, 1))
        return self.values[kind]

    def update(self, kind: str, ctx: np.ndarray, reward: float) -> None:
        self.counts[kind] += 1
        n = self.counts[kind]
        self.values[kind] += (reward - self.values[kind]) / n
        self.eps = max(self.eps_min, self.eps * self.decay)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dim": self.dim,
            "eps": self.eps,
            "eps_min": self.eps_min,
            "decay": self.decay,
            "counts": dict(self.counts),
            "values": dict(self.values),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpsilonGreedy":
        bandit = cls(
            int(data.get("dim", CTX_DIM)),
            float(data.get("eps_start", 0.3)),
            float(data.get("eps_min", 0.05)),
            float(data.get("decay", 0.999)),
        )
        bandit.eps = float(data.get("eps", bandit.eps))
        bandit.counts = {k: data.get("counts", {}).get(k, 0) for k in ACTION_KINDS}
        bandit.values = {k: data.get("values", {}).get(k, 0.0) for k in ACTION_KINDS}
        return bandit


class UCB1Bandit:
    """Upper Confidence Bound (UCB1) — exploration bonus via √(2 ln N / n_k)."""

    def __init__(self, dim: int = CTX_DIM, c: float = 1.5):
        self.dim = dim
        self.c = c
        self.counts = {k: 0 for k in ACTION_KINDS}
        self.values = {k: 0.0 for k in ACTION_KINDS}
        self.total = 0

    def score(self, kind: str, ctx: np.ndarray) -> float:
        self.total += 1
        if self.counts[kind] == 0:
            return 1e6  # explore unvisited
        bonus = self.c * math.sqrt(2 * math.log(self.total) / self.counts[kind])
        return self.values[kind] + bonus

    def update(self, kind: str, ctx: np.ndarray, reward: float) -> None:
        self.counts[kind] += 1
        n = self.counts[kind]
        self.values[kind] += (reward - self.values[kind]) / n

    def to_dict(self) -> dict[str, Any]:
        return {
            "dim": self.dim,
            "c": self.c,
            "counts": dict(self.counts),
            "values": dict(self.values),
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UCB1Bandit":
        bandit = cls(int(data.get("dim", CTX_DIM)), float(data.get("c", 1.5)))
        bandit.counts = {k: data.get("counts", {}).get(k, 0) for k in ACTION_KINDS}
        bandit.values = {k: data.get("values", {}).get(k, 0.0) for k in ACTION_KINDS}
        bandit.total = int(data.get("total", 0))
        return bandit


class PGPolicyBandit:
    """Simple policy-gradient (REINFORCE-style) baseline.

    A small linear-softmax policy over action kinds conditioned on an 8-dim
    context.  Included as a lightweight PPO-class baseline for Paper 3.
    """

    def __init__(self, dim: int = CTX_DIM, lr: float = 0.05,
                 entropy_coef: float = 0.01):
        self.dim = dim
        self.lr = lr
        self.entropy_coef = entropy_coef
        self.rng = np.random.default_rng(42)
        self.theta = {k: self.rng.normal(0, 0.01, dim).astype(np.float64)
                      for k in ACTION_KINDS}
        self._last_log_prob: dict[str, float] | None = None

    def _logits(self, ctx: np.ndarray) -> dict[str, float]:
        return {k: float(theta @ ctx) for k, theta in self.theta.items()}

    def score(self, kind: str, ctx: np.ndarray) -> float:
        logits = self._logits(ctx)
        mx = max(logits.values())
        exps = {k: math.exp(v - mx) for k, v in logits.items()}
        z = sum(exps.values())
        probs = {k: exps[k] / z for k in ACTION_KINDS}
        # Sample an action and remember log-prob for policy-gradient update.
        action = self.rng.choice(ACTION_KINDS, p=[probs[k] for k in ACTION_KINDS])
        self._last_log_prob = {k: math.log(probs[k] + 1e-12) for k in ACTION_KINDS}
        # Return the sampled action's score so the agent sorts by it; the
        # kind passed in is the candidate action being scored.
        return 1e6 if kind == action else probs[kind]

    def update(self, kind: str, ctx: np.ndarray, reward: float) -> None:
        if self._last_log_prob is None:
            return
        log_prob = self._last_log_prob.get(kind)
        if log_prob is None:
            return
        # REINFORCE gradient: ∇_θ log π(a|s) * R
        for k in ACTION_KINDS:
            indicator = 1.0 if k == kind else 0.0
            logits = self._logits(ctx)
            mx = max(logits.values())
            exps = {kk: math.exp(v - mx) for kk, v in logits.items()}
            z = sum(exps.values())
            prob = exps[k] / z
            grad = ctx * (indicator - prob)
            self.theta[k] += self.lr * reward * grad
        self._last_log_prob = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dim": self.dim,
            "lr": self.lr,
            "entropy_coef": self.entropy_coef,
            "theta": {k: v.tolist() for k, v in self.theta.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PGPolicyBandit":
        bandit = cls(int(data.get("dim", CTX_DIM)),
                     float(data.get("lr", 0.05)),
                     float(data.get("entropy_coef", 0.01)))
        for k in ACTION_KINDS:
            if k in data.get("theta", {}):
                bandit.theta[k] = np.array(data["theta"][k], dtype=np.float64)
        return bandit


BANDIT_BASELINES = {
    "Thompson": None,  # uses the real LinearThompsonBandit
    "ε-Greedy": EpsilonGreedy,
    "UCB1": UCB1Bandit,
    "Random": RandomBandit,
    "PPO-Policy": PGPolicyBandit,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Paper 4 — RCA Baselines
# ═══════════════════════════════════════════════════════════════════════════════

def magnitude_only_rank(scores: dict[str, float], top_n: int = 6) -> list[str]:
    """Rank by anomaly score magnitude only."""
    return sorted(scores, key=lambda e: -scores.get(e, 0))[:top_n]


def onset_only_rank(onsets: dict[str, int], top_n: int = 6) -> list[str]:
    """Rank by earliest anomaly onset only."""
    return sorted(onsets, key=lambda e: onsets.get(e, 10**9))[:top_n]


def correlation_only_rank(series: dict[str, np.ndarray],
                          scores: dict[str, float],
                          warn: float = 0.5,
                          top_n: int = 6) -> list[str]:
    """Rank by summed correlation to other anomalous entities (no topology)."""
    candidates = [e for e, s in scores.items() if s >= warn and e in series]
    if not candidates:
        return []
    totals: dict[str, float] = {}
    for cand in candidates:
        xs = series.get(cand)
        if xs is None:
            totals[cand] = 0.0
            continue
        total = 0.0
        for other, ys in series.items():
            if other == cand:
                continue
            n = min(len(xs), len(ys))
            if n < 10:
                continue
            a, b = xs[-n:], ys[-n:]
            if a.std() < 1e-9 or b.std() < 1e-9:
                continue
            r = float(np.corrcoef(a, b)[0, 1])
            if not np.isnan(r):
                total += abs(r)
        totals[cand] = total
    return sorted(totals, key=lambda e: -totals[e])[:top_n]


RCA_BASELINES = {
    "CausalNet": None,  # uses real CausalAnalyzer
    "Magnitude": "magnitude",
    "Onset": "onset",
    "Correlation": "correlation",
    "Granger": "granger",
    "PC": "pc",
    "NOTEARS": "notears",
}


def _extract_series(twin: TwinState, window: int = 80) -> dict[str, np.ndarray]:
    """Extract per-entity time series from TwinState history."""
    series: dict[str, np.ndarray] = {}
    for nid, buf in twin.node_history.items():
        vals = [m.throughput_mbps for m in list(buf)[-window:]]
        if len(vals) >= 30:
            series[nid] = np.asarray(vals, dtype=float)
    for lid, buf in twin.link_history.items():
        vals = [m.utilization_pct for m in list(buf)[-window:]]
        if len(vals) >= 30:
            series[lid] = np.asarray(vals, dtype=float)
    return series


def _granger_f_test(x: np.ndarray, y: np.ndarray, max_lag: int = 3) -> float:
    """Return p-value for the null hypothesis that y does NOT Granger-cause x.

    Implements a simple F-test comparing the restricted AR model (x lags only)
    to the unrestricted model (x lags + y lags).  Lower p-value => stronger
    evidence that y causes x.
    """
    n = min(len(x), len(y))
    x, y = x[-n:], y[-n:]
    if n <= 2 * max_lag + 2:
        return 1.0

    # Build lag matrices
    def _lags(z: np.ndarray, lag: int) -> np.ndarray:
        rows = len(z) - lag
        return np.array([z[i:rows + i] for i in range(lag)]).T

    # Restricted: x_t ~ x_{t-1}..x_{t-p}
    Xr = np.column_stack([np.ones(n - max_lag), _lags(x, max_lag)])
    yr = x[max_lag:]
    br, *_ = np.linalg.lstsq(Xr, yr, rcond=None)
    rss_r = float(((yr - Xr @ br) ** 2).sum())

    # Unrestricted: x_t ~ x_{t-1}..x_{t-p} + y_{t-1}..y_{t-p}
    Xu = np.column_stack([np.ones(n - max_lag),
                          _lags(x, max_lag),
                          _lags(y, max_lag)])
    yu = x[max_lag:]
    bu, *_ = np.linalg.lstsq(Xu, yu, rcond=None)
    rss_u = float(((yu - Xu @ bu) ** 2).sum())

    p = max_lag
    df1 = p
    df2 = n - 2 * p - 1
    if rss_u <= 0 or df2 <= 0:
        return 1.0
    f_stat = ((rss_r - rss_u) / df1) / (rss_u / df2)
    f_stat = max(0.0, f_stat)
    return float(1.0 - stats.f.cdf(f_stat, df1, df2))


def granger_causality_rank(twin: TwinState, detector: AnomalyDetector,
                           focus: str | None = None,
                           warn: float = 0.5, top_n: int = 6,
                           max_lag: int = 3) -> list[str]:
    """Rank candidates by how strongly they Granger-cause the focus entity."""
    series = _extract_series(twin)
    candidates = [e for e, s in detector.scores.items()
                  if s >= warn and e in series and e != focus]
    if focus and focus in series and focus not in candidates:
        candidates.append(focus)
    if not candidates:
        return []

    target = focus if focus and focus in series else next(iter(candidates))
    pvalues: dict[str, float] = {}
    for cand in candidates:
        pvalues[cand] = _granger_f_test(series[target], series[cand], max_lag)
    # Lower p-value => more likely root cause; tie-break by anomaly magnitude.
    return sorted(candidates,
                  key=lambda e: (pvalues[e], -detector.scores.get(e, 0.0)))[:top_n]


def _partial_corr(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    """Partial correlation of x and y conditioned on z (matrix or vector)."""
    def _resid(a: np.ndarray, pred: np.ndarray) -> np.ndarray:
        if pred.ndim == 1:
            pred = pred.reshape(-1, 1)
        if pred.shape[1] == 0:
            return a - a.mean()
        b, *_ = np.linalg.lstsq(np.column_stack([np.ones(pred.shape[0]), pred]),
                                a, rcond=None)
        return a - np.column_stack([np.ones(pred.shape[0]), pred]) @ b

    rx = _resid(x, z)
    ry = _resid(y, z)
    denom = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    if denom < 1e-12:
        return 0.0
    return float((rx * ry).sum() / denom)


def pc_skeleton_rank(twin: TwinState, topology: Topology,
                     detector: AnomalyDetector,
                     focus: str | None = None,
                     warn: float = 0.5, top_n: int = 6,
                     max_dist: int = 3,
                     alpha: float = 0.05) -> list[str]:
    """Simplified PC-algorithm skeleton: partial-correlation conditional
    independence tests over topology-constrained candidate sets."""
    series = _extract_series(twin)
    scores = detector.scores
    candidates = [e for e, s in scores.items()
                  if s >= warn and e in series]
    if focus and focus not in candidates and focus in series:
        candidates.append(focus)
    if not candidates:
        return []

    def _dist(a: str, b: str) -> int:
        if a == b:
            return 0
        path = topology.paths.get((a, b))
        return len(path) - 1 if path else 99

    # Build topology-constrained complete graph.
    adj = {c: set() for c in candidates}
    for a, b in itertools.combinations(candidates, 2):
        if _dist(a, b) <= max_dist:
            adj[a].add(b)
            adj[b].add(a)

    # Phase I: unconditional independence (correlation) screening.
    for a, b in list(itertools.combinations(candidates, 2)):
        if b not in adj[a]:
            continue
        n = min(len(series[a]), len(series[b]))
        if n < 10:
            continue
        r = float(np.corrcoef(series[a][-n:], series[b][-n:])[0, 1])
        if abs(r) < alpha:
            adj[a].discard(b)
            adj[b].discard(a)

    # Phase II: conditional independence given subsets of neighbors.
    for a in candidates:
        neighbors = list(adj[a])
        for b in neighbors:
            if b not in adj[a]:
                continue
            nbrs = [x for x in adj[a] if x != b]
            for cond in itertools.combinations(nbrs, min(1, len(nbrs))):
                if not cond:
                    continue
                cond_vars = np.column_stack([series[c][-len(series[a]):]
                                             for c in cond])
                pc = _partial_corr(series[a], series[b], cond_vars)
                if abs(pc) < alpha:
                    adj[a].discard(b)
                    adj[b].discard(a)
                    break

    # Rank by degree (causal hub) + own anomaly magnitude.
    ranked = sorted(candidates,
                    key=lambda e: (-len(adj[e]), -scores.get(e, 0.0)))
    return ranked[:top_n]


def notears_rank(twin: TwinState, topology: Topology,
                 detector: AnomalyDetector,
                 focus: str | None = None,
                 warn: float = 0.5, top_n: int = 6,
                 max_dist: int = 3,
                 lambda1: float = 0.01,
                 max_iter: int = 300) -> list[str]:
    """Simplified NOTEARS baseline: L1-regularized least squares with an
    acyclicity soft constraint, solved via scipy L-BFGS-B over a
    topology-constrained candidate set."""
    series = _extract_series(twin)
    scores = detector.scores
    candidates = [e for e, s in scores.items()
                  if s >= warn and e in series]
    if focus and focus not in candidates and focus in series:
        candidates.append(focus)
    if len(candidates) < 2:
        return candidates[:top_n]

    def _dist(a: str, b: str) -> int:
        if a == b:
            return 0
        path = topology.paths.get((a, b))
        return len(path) - 1 if path else 99

    # Restrict adjacency to topology neighbors to keep optimization small.
    idx = {e: i for i, e in enumerate(candidates)}
    d = len(candidates)
    mask = np.zeros((d, d), dtype=bool)
    for a, b in itertools.permutations(candidates, 2):
        if _dist(a, b) <= max_dist:
            mask[idx[a], idx[b]] = True

    # Align series lengths and normalize.
    n = min(len(v) for v in series.values())
    X = np.zeros((n, d))
    for e, i in idx.items():
        col = series[e][-n:].copy()
        std = col.std()
        X[:, i] = (col - col.mean()) / (std if std > 1e-9 else 1.0)

    def _loss(w_flat: np.ndarray) -> float:
        W = w_flat.reshape(d, d) * mask
        pred = X @ W
        mse = float(((X - pred) ** 2).sum() / (n * d))
        l1 = float(lambda1 * np.abs(W).sum())
        # Acyclicity penalty: h(W) = trace(exp(W∘W)) - d
        h = float(np.trace(linalg.expm(W * W)) - d)
        return mse + l1 + 1e3 * max(0.0, h) ** 2

    w0 = np.zeros(d * d)
    bounds = [(0.0, None) if mask[i // d, i % d] else (0.0, 0.0)
              for i in range(d * d)]
    result = optimize.minimize(_loss, w0, method="L-BFGS-B", bounds=bounds,
                               options={"maxiter": max_iter})
    W = result.x.reshape(d, d) * mask

    # Root-cause score: high in-degree parents + own anomaly magnitude.
    in_degree = W.sum(axis=0)  # column j = sum of parents -> j
    out_degree = W.sum(axis=1)
    ranked = sorted(candidates,
                    key=lambda e: (-in_degree[idx[e]] - out_degree[idx[e]],
                                   -scores.get(e, 0.0)))
    return ranked[:top_n]
