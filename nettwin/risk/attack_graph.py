"""Bayesian attack graph: compromise propagation + crown-jewel risk.

Per-node compromise probability is seeded from asset criticality, internet
exposure and a vulnerability prior, then propagated along topology edges with
personalized-PageRank-style iteration. Active alerts/attacks raise seeds.
"""
from __future__ import annotations

from typing import Any

from nettwin.config import RiskSettings
from nettwin.simulator.topology import Topology

CRITICAL_KINDS = ("core_router", "internet_gateway", "firewall",
                  "distribution_switch", "edge_switch")


class AttackGraph:
    def __init__(self, topology: Topology, settings: RiskSettings) -> None:
        self.topo = topology
        self.s = settings
        self.compromise: dict[str, float] = {}
        self.expected_loss: dict[str, float] = {}
        self.network_risk = 0.0
        self.top_paths: list[dict[str, Any]] = []
        self.recompute(seeds={})

    def _criticality(self, node_id: str) -> float:
        role = self.topo.nodes[node_id].role
        kind = self.topo.nodes[node_id].kind
        if role in self.s.criticality:
            return self.s.criticality[role]
        return self.s.criticality.get(kind, 0.4 if kind == "server" else 0.1)

    def _prior(self, node_id: str) -> float:
        node = self.topo.nodes[node_id]
        if node.kind == "attacker":
            return 1.0
        vuln = self.s.vuln_seed.get(node.kind,
                                    self.s.vuln_seed.get(node.role, 0.2))
        exposure = 1.0 if node.role == "web" else (
            0.6 if node.kind in ("internet_gateway", "firewall") else 0.2)
        return min(0.95, 0.05 + 0.35 * vuln + 0.25 * exposure * vuln)

    def recompute(self, seeds: dict[str, float]) -> None:
        nodes = list(self.topo.nodes)
        p = {nid: self._prior(nid) for nid in nodes}
        for nid, val in seeds.items():
            if nid in p:
                p[nid] = max(p[nid], val)
        d = self.s.damping
        adj = self.topo.adjacency
        for _ in range(self.s.iterations):
            new_p = {}
            for nid in nodes:
                if self.topo.nodes[nid].kind == "attacker":
                    new_p[nid] = 1.0
                    continue
                incoming = 0.0
                for nbr in adj[nid]:
                    deg = max(1, len(adj[nbr]))
                    incoming += p[nbr] / deg
                base = self._prior(nid)
                if nid in seeds:
                    base = max(base, seeds[nid])
                new_p[nid] = min(0.99, base + d * (1 - base) * incoming)
            p = new_p
        self.compromise = {nid: round(p[nid], 4) for nid in nodes}
        self.expected_loss = {
            nid: round(p[nid] * self._criticality(nid), 4) for nid in nodes}
        total_crit = sum(max(0.01, self._criticality(n)) for n in nodes)
        self.network_risk = round(
            100.0 * sum(self.expected_loss.values()) / total_crit, 1)
        self.top_paths = self._top_paths()

    def _top_paths(self, n: int = 3) -> list[dict[str, Any]]:
        """Greedy highest-compromise-probability paths attacker -> crown jewels."""
        paths = []
        jewels = sorted((nid for nid in self.topo.nodes
                         if self.topo.nodes[nid].role == "db"),
                        key=lambda j: -self.expected_loss.get(j, 0))[:2]
        start_node = "attacker" if "attacker" in self.topo.adjacency else ("igw" if "igw" in self.topo.adjacency else next(iter(self.topo.adjacency), None))
        if not start_node:
            return []
        for jewel in jewels:
            path = [start_node]
            cur = start_node
            seen = {start_node}
            while cur != jewel and len(path) < 12:
                nbrs = [nb for nb in self.topo.adjacency.get(cur, []) if nb not in seen]
                if not nbrs:
                    break
                nxt = max(nbrs, key=lambda nb: self.compromise.get(nb, 0))
                path.append(nxt)
                seen.add(nxt)
                cur = nxt
            if cur == jewel:
                prob = 1.0
                for hop in path[1:]:
                    prob *= self.compromise.get(hop, 0.1)
                paths.append({"path": path, "probability": round(prob, 4),
                              "expected_loss": self.expected_loss.get(jewel, 0)})
        return paths

    def snapshot(self) -> dict[str, Any]:
        return {
            "network_risk": self.network_risk,
            "nodes": [{"entity_id": nid,
                       "compromise": self.compromise[nid],
                       "expected_loss": self.expected_loss[nid],
                       "criticality": self._criticality(nid)}
                      for nid in sorted(self.topo.nodes,
                                        key=lambda n: -self.expected_loss[n])],
            "top_paths": self.top_paths,
        }
