"""
Build the PNG charts embedded in the weekly email.

Quick check from the project root:
    python src/charts.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")       # draw straight to files, no window (needed when run by Task Scheduler)
import matplotlib.pyplot as plt
import pandas as pd

import config

BLUE = "#2a78d6"
GRAY = "#c9c8c3"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e8e7e3"
SURFACE = "#ffffff"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK2,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "font.size": 10,
})


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)          # free memory; important when running unattended
    return path


def funnel_chart(funnel: pd.DataFrame, path: Path) -> Path:
    f = funnel.iloc[::-1]   # "Applied" at the top
    fig, ax = plt.subplots(figsize=(6, 2.4))
    bars = ax.barh(f["stage"], f["count"], color=BLUE, height=0.6)
    labels = [f"{c}  ({p:.0%})" for c, p in zip(f["count"], f["pct_of_applied"])]
    ax.bar_label(bars, labels=labels, padding=4, fontsize=9, color=INK)
    ax.set_xlim(0, f["count"].max() * 1.25)
    ax.xaxis.set_visible(False)
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    return _save(fig, path)


def trend_chart(trend: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 2.6))
    labels = trend.index.strftime("%d %b")
    colors = [GRAY] * (len(trend) - 1) + [BLUE]          # highlight the report week
    bars = ax.bar(labels, trend["applications"], color=colors, width=0.65)
    ax.bar_label(bars, padding=2, fontsize=8.5, color=INK)
    ax.set_ylabel("Applications")
    ax.set_ylim(0, max(trend["applications"].max() * 1.2, 1))
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(axis="x", visible=False)
    return _save(fig, path)


def source_chart(sources: pd.DataFrame, path: Path) -> Path:
    s = sources.sort_values("screen_rate")                # best at the top
    best = s["screen_rate"].idxmax()
    fig, ax = plt.subplots(figsize=(6, 2.9))
    colors = [BLUE if name == best else GRAY for name in s.index]
    bars = ax.barh(s.index, s["screen_rate"] * 100, color=colors, height=0.6)
    labels = [f"{r:.0%}  (n={n})" for r, n in zip(s["screen_rate"], s["applications"])]
    ax.bar_label(bars, labels=labels, padding=4, fontsize=9, color=INK)
    ax.set_xlim(0, max(s["screen_rate"].max() * 100 * 1.35, 10))
    ax.set_xlabel("Applications that led to a screening call (%)")
    ax.grid(axis="y", visible=False)
    return _save(fig, path)


def make_charts(metrics: dict, out_dir: Path | None = None) -> dict[str, Path]:
    """Create all report charts and return {name: file path}."""
    out_dir = out_dir or (config.OUTPUT_DIR / "charts")
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "funnel": funnel_chart(metrics["funnel"], out_dir / "funnel.png"),
        "trend": trend_chart(metrics["trend"], out_dir / "trend.png"),
        "sources": source_chart(metrics["sources"], out_dir / "sources.png"),
    }


if __name__ == "__main__":
    from metrics import build_metrics
    from tracker import load_tracker

    today = config.report_date()
    df, _ = load_tracker(today=today)
    paths = make_charts(build_metrics(df, today))
    for name, path in paths.items():
        print(f"{name:8} → {path.relative_to(config.ROOT)}")