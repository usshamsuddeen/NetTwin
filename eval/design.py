"""NetTwin 2.0 — Publication Design System v3.

Inch-perfect, camera-ready figure styling for all 5 research papers.
Single source of truth for colors, fonts, sizes, export settings, and
advanced visualization helpers (radar, Sankey, bump, heatmap, violin,
ridge, waterfall, strip-overlay, beeswarm, ECDF, etc.).

Conventions
-----------
- Figures:  {paper}_fig{N}_{descriptive_name}
- Results:  {paper}_exp{N}_{description}_{ticks}k_{seeds}s
- Telemetry unit: "telemetry tick" (abbrev: "tick")
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
import numpy as np
import seaborn as sns
from scipy import stats

# ─── directory roots ──────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).resolve().parent
FIG_DIR = EVAL_DIR / "figures"
RESULTS_DIR = EVAL_DIR / "results"

PAPER_DIRS = {
    "p1": FIG_DIR / "p1_sync",
    "p2": FIG_DIR / "p2_conformal",
    "p3": FIG_DIR / "p3_response",
    "p4": FIG_DIR / "p4_rca",
    "p5": FIG_DIR / "p5_system",
}

for _d in list(PAPER_DIRS.values()) + [RESULTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─── color palette (colorblind-safe, 10 colors) ──────────────────────────────
PALETTE = [
    "#2D4A7A",  # deep navy
    "#E85D3A",  # vermilion
    "#4CAF7D",  # teal green
    "#F5A623",  # amber
    "#8E44AD",  # plum
    "#1ABC9C",  # turquoise
    "#D35400",  # burnt orange
    "#2C3E50",  # charcoal
    "#E74C3C",  # red
    "#3498DB",  # sky blue
]

# Named semantic colors for consistent usage
C_PRIMARY = PALETTE[0]
C_ACCENT = PALETTE[1]
C_SUCCESS = PALETTE[2]
C_WARNING = PALETTE[3]
C_HIGHLIGHT = PALETTE[4]
C_TEAL = PALETTE[5]
C_BURNT = PALETTE[6]
C_CHARCOAL = PALETTE[7]
C_RED = PALETTE[8]
C_SKY = PALETTE[9]
C_BASELINE = "#AAAAAA"
C_GRID = "#E8E8E8"

# Attack-type color mapping (consistent across all papers)
ATTACK_COLORS = {
    "ddos": PALETTE[1],
    "portscan": PALETTE[0],
    "exfiltration": PALETTE[4],
    "lateral": PALETTE[3],
    "bruteforce": PALETTE[5],
}

ATTACK_LABELS = {
    "ddos": "DDoS",
    "portscan": "Port Scan",
    "exfiltration": "Exfiltration",
    "lateral": "Lateral Mvmt",
    "bruteforce": "Brute Force",
}

# Hatch patterns for B/W print readability
HATCHES = ["", "///", "\\\\\\", "xxx", "...", "ooo", "+++", "---"]

# Marker cycle for multi-line plots
MARKERS = ["o", "s", "D", "^", "v", "P", "X", "*", "h", "p"]

# ─── figure sizes (inches) — IEEE/ACM column widths ──────────────────────────
FIG_SINGLE = (3.5, 2.5)     # single-column
FIG_SINGLE_TALL = (3.5, 3.0)
FIG_DOUBLE = (7.0, 3.0)     # double-column
FIG_DOUBLE_TALL = (7.0, 4.0)
FIG_FULL = (7.0, 5.0)       # full-page panel
FIG_WIDE = (7.0, 2.5)       # wide but short
FIG_MEGA = (7.0, 7.0)       # mega-panel (4×3 grids)
FIG_TRIPLE = (7.0, 6.0)     # triple-row panel

# ─── matplotlib rcParams ─────────────────────────────────────────────────────
_RC = {
    # font
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "legend.title_fontsize": 8,
    # lines
    "lines.linewidth": 1.4,
    "lines.markersize": 4,
    # axes
    "axes.linewidth": 0.6,
    "axes.grid": True,
    "axes.grid.which": "major",
    "axes.edgecolor": "#444444",
    "axes.labelcolor": "#222222",
    "axes.spines.top": False,
    "axes.spines.right": False,
    # grid
    "grid.color": C_GRID,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.7,
    # ticks
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    # figure
    "figure.dpi": 150,
    "savefig.dpi": 600,  # publication-grade DPI
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
    # legend
    "legend.frameon": True,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#CCCCCC",
    "legend.fancybox": False,
    # patches
    "patch.linewidth": 0.5,
}


def apply_style() -> None:
    """Apply the NetTwin publication style globally."""
    sns.set_theme(style="whitegrid", font_scale=1.0, rc=_RC)
    sns.set_palette(PALETTE)
    mpl.rcParams.update(_RC)


def fig(size: tuple[float, float] = FIG_DOUBLE,
        nrows: int = 1, ncols: int = 1,
        **kwargs: Any) -> tuple[plt.Figure, Any]:
    """Create a figure with the design system applied."""
    apply_style()
    f, ax = plt.subplots(nrows=nrows, ncols=ncols,
                         figsize=size, constrained_layout=True, **kwargs)
    return f, ax


def save(f: plt.Figure, paper: str, name: str, close: bool = True) -> Path:
    """Save figure as PDF (vector) + PNG (raster) to the paper's directory."""
    d = PAPER_DIRS[paper]
    d.mkdir(parents=True, exist_ok=True)
    pdf_path = d / f"{name}.pdf"
    png_path = d / f"{name}.png"
    f.savefig(pdf_path, format="pdf", bbox_inches="tight", pad_inches=0.03)
    f.savefig(png_path, format="png", bbox_inches="tight", pad_inches=0.03, dpi=600)
    if close:
        plt.close(f)
    print(f"  [OK] {pdf_path.relative_to(EVAL_DIR)}")
    return pdf_path


# ─── statistical helpers ─────────────────────────────────────────────────────

def ci95(data: list[float] | np.ndarray) -> tuple[float, float, float]:
    """Return (mean, ci_lo, ci_hi) for 95% confidence interval."""
    arr = np.asarray(data, dtype=float)
    n = len(arr)
    if n < 2:
        m = float(arr.mean())
        return m, m, m
    m = float(arr.mean())
    se = float(arr.std(ddof=1) / np.sqrt(n))
    h = float(stats.t.ppf(0.975, n - 1) * se)
    return m, m - h, m + h


def ci95_bca(data: list[float] | np.ndarray,
             n_bootstrap: int = 10000, seed: int = 42) -> tuple[float, float, float]:
    """BCa bootstrap 95% CI — bias-corrected and accelerated.
    Returns (mean, ci_lo, ci_hi).
    """
    arr = np.asarray(data, dtype=float)
    n = len(arr)
    if n < 3:
        return ci95(arr)
    rng = np.random.default_rng(seed)
    m = float(arr.mean())
    boot = np.array([rng.choice(arr, n, replace=True).mean()
                     for _ in range(n_bootstrap)])
    # Bias correction
    prop_less = np.clip(np.mean(boot < m), 1e-4, 1 - 1e-4)
    z0 = float(stats.norm.ppf(prop_less))
    # Acceleration (jackknife)
    jk_means = np.array([np.delete(arr, i).mean() for i in range(n)])
    jk_diff = jk_means.mean() - jk_means
    denom = 6 * (np.sum(jk_diff ** 2)) ** 1.5 + 1e-12
    a = float(np.sum(jk_diff ** 3) / denom) if denom != 0 else 0.0
    # Adjusted percentiles
    z_alpha = float(stats.norm.ppf(0.025))
    z_1alpha = float(stats.norm.ppf(0.975))
    denom_lo = 1 - a * (z0 + z_alpha) + 1e-12
    denom_hi = 1 - a * (z0 + z_1alpha) + 1e-12
    p_lo = stats.norm.cdf(z0 + (z0 + z_alpha) / denom_lo) if denom_lo != 0 else 0.025
    p_hi = stats.norm.cdf(z0 + (z0 + z_1alpha) / denom_hi) if denom_hi != 0 else 0.975
    if np.isnan(p_lo) or np.isnan(p_hi):
        return ci95(arr)
    p_lo = float(np.clip(p_lo, 0.001, 0.999))
    p_hi = float(np.clip(p_hi, 0.001, 0.999))
    return m, float(np.percentile(boot, p_lo * 100)), float(np.percentile(boot, p_hi * 100))


def ci95_series(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """CI for each column across rows (seeds × ticks). Returns mean, lo, hi."""
    means = np.nanmean(matrix, axis=0)
    n = matrix.shape[0]
    if n < 2:
        return means, means, means
    se = np.nanstd(matrix, axis=0, ddof=1) / np.sqrt(n)
    h = stats.t.ppf(0.975, n - 1) * se
    return means, means - h, means + h


def effect_size_cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    pooled_std = np.sqrt(((n1 - 1) * group1.std(ddof=1)**2 +
                          (n2 - 1) * group2.std(ddof=1)**2) / (n1 + n2 - 2))
    return float((group1.mean() - group2.mean()) / max(pooled_std, 1e-12))


# ─── plot helpers ─────────────────────────────────────────────────────────────

def plot_ci_line(ax: plt.Axes, x: np.ndarray, matrix: np.ndarray,
                 label: str, color: str, alpha: float = 0.15,
                 linestyle: str = "-", marker: str | None = None,
                 markevery: int = 0) -> None:
    """Plot mean line with 95% CI shading."""
    mean, lo, hi = ci95_series(matrix)
    kw = dict(color=color, label=label, linestyle=linestyle, linewidth=1.4)
    if marker:
        kw.update(marker=marker, markevery=markevery or max(1, len(x) // 15),
                  markersize=4)
    ax.plot(x, mean, **kw)
    ax.fill_between(x, lo, hi, color=color, alpha=alpha)


def add_ci_bars(ax: plt.Axes, x_positions: np.ndarray,
                means: list[float], lows: list[float], highs: list[float],
                color: str = "black", capsize: int = 3) -> None:
    """Add error bars (CI whiskers) to an existing bar chart."""
    errs = np.array([[m - l for m, l in zip(means, lows)],
                     [h - m for m, h in zip(means, highs)]])
    ax.errorbar(x_positions, means, yerr=errs, fmt="none",
                ecolor=color, capsize=capsize, capthick=0.7, elinewidth=0.7)


def add_individual_points(ax: plt.Axes, x_positions: np.ndarray,
                          data_per_group: list[list[float]],
                          color: str = "#333333", alpha: float = 0.4,
                          jitter: float = 0.08, size: int = 15) -> None:
    """Overlay individual data points (strip/beeswarm) on bars."""
    rng = np.random.default_rng(42)
    for i, vals in enumerate(data_per_group):
        jittered_x = x_positions[i] + rng.uniform(-jitter, jitter, len(vals))
        ax.scatter(jittered_x, vals, s=size, color=color, alpha=alpha,
                   edgecolors="white", linewidths=0.3, zorder=5)


# ─── advanced viz: radar chart ───────────────────────────────────────────────

def plot_radar(ax: plt.Axes, categories: list[str],
               datasets: dict[str, list[float]],
               colors: list[str] | None = None,
               fill_alpha: float = 0.15) -> None:
    """Draw a filled radar (spider) chart on a polar axes."""
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close polygon

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(30)
    ax.set_thetagrids(np.degrees(angles[:-1]), categories, fontsize=7)

    palette = colors or PALETTE
    for i, (name, vals) in enumerate(datasets.items()):
        values = vals + vals[:1]
        color = palette[i % len(palette)]
        ax.plot(angles, values, 'o-', color=color, linewidth=1.2,
                markersize=3, label=name)
        ax.fill(angles, values, color=color, alpha=fill_alpha)


# ─── advanced viz: violin + strip combo ──────────────────────────────────────

def plot_violin_strip(ax: plt.Axes, data: list[list[float]],
                      labels: list[str], colors: list[str] | None = None,
                      orient: str = "v") -> None:
    """Violin + strip overlay for distribution visualization."""
    palette = colors or PALETTE
    import pandas as pd
    rows = []
    for i, (vals, label) in enumerate(zip(data, labels)):
        for v in vals:
            rows.append({"group": label, "value": v})
    df = pd.DataFrame(rows)
    if orient == "v":
        sns.violinplot(data=df, x="group", y="value", hue="group", palette=palette[:len(labels)],
                       ax=ax, inner=None, linewidth=0.6, alpha=0.3, cut=0, legend=False)
        sns.stripplot(data=df, x="group", y="value", hue="group", palette=palette[:len(labels)],
                      ax=ax, size=3, alpha=0.6, jitter=0.15, edgecolor="white",
                      linewidth=0.3, legend=False)
    else:
        sns.violinplot(data=df, y="group", x="value", hue="group", palette=palette[:len(labels)],
                       ax=ax, inner=None, linewidth=0.6, alpha=0.3, cut=0, legend=False)
        sns.stripplot(data=df, y="group", x="value", hue="group", palette=palette[:len(labels)],
                      ax=ax, size=3, alpha=0.6, jitter=0.15, edgecolor="white",
                      linewidth=0.3, legend=False)


# ─── advanced viz: ridge/joy plot ────────────────────────────────────────────

def plot_ridges(ax: plt.Axes, data: dict[str, np.ndarray],
                colors: list[str] | None = None,
                overlap: float = 0.5) -> None:
    """Draw a ridge (joy) plot — overlapping KDEs."""
    palette = colors or PALETTE
    labels = list(data.keys())
    n = len(labels)
    for i, (label, vals) in enumerate(data.items()):
        y_offset = i * (1 - overlap)
        xs = np.linspace(vals.min() - vals.std(), vals.max() + vals.std(), 200)
        kde = stats.gaussian_kde(vals)(xs)
        kde = kde / kde.max() * 0.8  # normalize height
        color = palette[i % len(palette)]
        ax.fill_between(xs, y_offset, y_offset + kde, alpha=0.6, color=color)
        ax.plot(xs, y_offset + kde, color=color, linewidth=0.8)
    ax.set_yticks([i * (1 - overlap) + 0.2 for i in range(n)])
    ax.set_yticklabels(labels, fontsize=7)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)


# ─── advanced viz: waterfall chart ───────────────────────────────────────────

def plot_waterfall(ax: plt.Axes, labels: list[str], values: list[float],
                   colors: list[str] | None = None) -> None:
    """Draw a waterfall chart showing cumulative contributions."""
    n = len(labels)
    running = 0.0
    palette = colors or [C_SUCCESS if v >= 0 else C_ACCENT for v in values]
    for i, (label, v) in enumerate(zip(labels, values)):
        bottom = running if v >= 0 else running + v
        color = palette[i] if isinstance(palette, list) and i < len(palette) else (
            C_SUCCESS if v >= 0 else C_ACCENT)
        ax.bar(i, abs(v), bottom=bottom, color=color, edgecolor="white",
               linewidth=0.5, width=0.6)
        # Connector line
        if i < n - 1:
            ax.plot([i + 0.3, i + 0.7], [running + v, running + v],
                    color="#888", linewidth=0.5, linestyle=":")
        running += v
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")


# ─── advanced viz: bump chart ────────────────────────────────────────────────

def plot_bump(ax: plt.Axes, time_labels: list[str],
              rank_data: dict[str, list[int]],
              colors: list[str] | None = None) -> None:
    """Bump chart showing rank evolution over time."""
    palette = colors or PALETTE
    x = np.arange(len(time_labels))
    for i, (name, ranks) in enumerate(rank_data.items()):
        color = palette[i % len(palette)]
        ax.plot(x, ranks, 'o-', color=color, linewidth=1.8,
                markersize=6, label=name, zorder=3)
        # Label endpoint
        ax.text(x[-1] + 0.15, ranks[-1], name, fontsize=6, va="center",
                color=color, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(time_labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_ylabel("Rank")


# ─── advanced viz: ECDF plot ─────────────────────────────────────────────────

def plot_ecdf(ax: plt.Axes, datasets: dict[str, np.ndarray],
              colors: list[str] | None = None) -> None:
    """Empirical CDF with step function."""
    palette = colors or PALETTE
    for i, (label, vals) in enumerate(datasets.items()):
        sorted_vals = np.sort(vals)
        ecdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
        color = palette[i % len(palette)]
        ax.step(sorted_vals, ecdf, color=color, linewidth=1.2,
                where="post", label=label)
    ax.set_ylabel("ECDF")
    ax.set_ylim(-0.02, 1.05)


# ─── advanced viz: grouped heatmap with annotations ─────────────────────────

def plot_annotated_heatmap(ax: plt.Axes, data: np.ndarray,
                           row_labels: list[str], col_labels: list[str],
                           cmap: str = "YlOrRd_r",
                           fmt: str = ".1f",
                           highlight_best_col: bool = True) -> None:
    """Publication-quality annotated heatmap with optional best-per-column highlight."""
    im = ax.imshow(data, cmap=cmap, aspect="auto")
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(col_labels, fontsize=7)
    ax.set_yticklabels(row_labels, fontsize=7)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isnan(val):
                continue
            text_color = "white" if val < (np.nanmax(data) - np.nanmin(data)) / 2 + np.nanmin(data) else "black"
            bold = ""
            if highlight_best_col and val == np.nanmax(data[:, j]):
                bold = "bold"
            ax.text(j, i, f"{val:{fmt}}", ha="center", va="center",
                    fontsize=7, color=text_color, fontweight=bold or "normal")
    return im


# ─── advanced viz: multi-metric summary table figure ─────────────────────────

def plot_results_table(ax: plt.Axes, headers: list[str],
                       rows: list[list[str]], row_colors: list[str] | None = None,
                       highlight_col: int = -1) -> None:
    """Render a results table as a matplotlib figure (for publication)."""
    ax.axis("off")
    n_cols = len(headers)
    n_rows = len(rows)
    cell_height = 1.0 / (n_rows + 1)
    cell_width = 1.0 / n_cols

    # Header
    for j, h in enumerate(headers):
        ax.text(j * cell_width + cell_width / 2, 1.0 - cell_height / 2,
                h, ha="center", va="center", fontsize=8,
                fontweight="bold", color="#222",
                transform=ax.transAxes)
    ax.plot([0.02, 0.98], [1.0 - cell_height, 1.0 - cell_height],
            color="#333", linewidth=0.8, transform=ax.transAxes)

    # Rows
    for i, row in enumerate(rows):
        y = 1.0 - (i + 1.5) * cell_height
        bg_color = row_colors[i] if row_colors and i < len(row_colors) else None
        if bg_color:
            rect = mpatches.FancyBboxPatch(
                (0.01, y - cell_height / 2), 0.98, cell_height,
                transform=ax.transAxes, boxstyle="square,pad=0",
                facecolor=bg_color, edgecolor="none", alpha=0.15)
            ax.add_patch(rect)
        for j, cell in enumerate(row):
            weight = "bold" if j == highlight_col else "normal"
            ax.text(j * cell_width + cell_width / 2, y,
                    str(cell), ha="center", va="center",
                    fontsize=7, fontweight=weight,
                    transform=ax.transAxes)


# ─── annotation helpers ──────────────────────────────────────────────────────

def label_bars(ax: plt.Axes, fmt: str = "{:.1f}", fontsize: int = 7,
               offset: float = 0.02) -> None:
    """Label bar chart with values above each bar."""
    ymax = ax.get_ylim()[1]
    for p in ax.patches:
        h = p.get_height()
        if h > 0:
            ax.annotate(fmt.format(h),
                        (p.get_x() + p.get_width() / 2., h + ymax * offset),
                        ha="center", va="bottom", fontsize=fontsize, color="#333")


def set_percent_yaxis(ax: plt.Axes) -> None:
    """Format y-axis as percentage."""
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100.0, decimals=0))


def despine(ax: plt.Axes) -> None:
    """Remove top and right spines."""
    sns.despine(ax=ax)


def add_attack_shading(ax: plt.Axes, schedule_entries: list[dict],
                       tick_to_x: float = 1.0,
                       color: str = "#E85D3A", alpha: float = 0.08,
                       label: bool = True) -> None:
    """Shade attack periods on a timeline axis."""
    for i, entry in enumerate(schedule_entries):
        s = entry["start"] * tick_to_x
        e = (entry["start"] + entry["duration_ticks"]) * tick_to_x
        ax.axvspan(s, e, color=color, alpha=alpha,
                   label="Attack" if i == 0 and label else "")


def add_threshold_line(ax: plt.Axes, y: float, label: str = "",
                       color: str = "#888888", linestyle: str = "--") -> None:
    """Add a horizontal threshold reference line."""
    ax.axhline(y=y, color=color, linestyle=linestyle, linewidth=0.7,
               alpha=0.6, label=label)


def panel_label(ax: plt.Axes, label: str, x: float = -0.12, y: float = 1.08,
                fontsize: int = 11) -> None:
    """Add a bold panel label (a), (b), (c) etc."""
    ax.text(x, y, label, transform=ax.transAxes,
            fontsize=fontsize, fontweight="bold", va="top")


# ─── convenience ─────────────────────────────────────────────────────────────

# Apply style on import so any script that imports design.py gets the style
apply_style()
