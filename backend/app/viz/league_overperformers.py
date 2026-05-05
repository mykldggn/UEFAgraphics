"""Diverging bar chart of over/underperformers — actual pts vs xPts delta."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)


def render(
    league_label: str,
    season_label: str,
    teams: list[dict],
) -> bytes:
    font = get_font()

    if not teams or len(teams) < 2:
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.55, f"{league_label}  ·  {season_label}",
                color=TEXT, fontsize=16, ha="center", va="center",
                transform=ax.transAxes, fontweight="bold", fontproperties=font)
        ax.text(0.5, 0.42, "Not enough team data", color=TEXT_SUB,
                fontsize=12, ha="center", va="center", transform=ax.transAxes,
                fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    deltas = []
    for t in teams:
        pts  = float(t.get("pts",  0) or 0)
        xpts = float(t.get("xPts", 0) or 0)
        deltas.append((str(t.get("name", "")), pts - xpts))

    deltas.sort(key=lambda x: x[1], reverse=True)
    names  = [d[0] for d in deltas]
    values = [d[1] for d in deltas]

    n = len(names)
    bar_colors = [GREEN if v >= 0 else RED for v in values]

    fig, ax = plt.subplots(figsize=(12, max(6, n * 0.40 + 1.8)), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")

    ys = np.arange(n)
    ax.barh(ys, values, color=bar_colors, alpha=0.85, height=0.60, zorder=3)

    max_abs = max(abs(v) for v in values) if values else 1
    for i, v in enumerate(values):
        sign = "+" if v >= 0 else ""
        offset = max_abs * 0.015 if v >= 0 else -max_abs * 0.015
        ha = "left" if v >= 0 else "right"
        ax.text(v + offset, i, f"{sign}{v:.1f}",
                fontsize=8.5, color=TEXT, va="center", ha=ha,
                fontproperties=font)

    ax.axvline(0, color=TEXT, lw=1.5, zorder=4)
    ax.set_xlim(-max_abs * 1.35, max_abs * 1.35)

    ax.set_yticks(ys)
    ax.set_yticklabels(names, fontsize=8.5, color=TEXT, fontproperties=font)
    ax.set_xlabel("Actual Pts − xPts", color=TEXT_SUB, fontsize=9,
                  fontproperties=font, labelpad=6)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.grid(axis="x", color="#1F2937", lw=0.6)

    legend_patches = [
        mpatches.Patch(color=GREEN, label="Overperforming xG"),
        mpatches.Patch(color=RED,   label="Underperforming xG"),
    ]
    ax.legend(handles=legend_patches, frameon=False, labelcolor=TEXT,
              prop=font, fontsize=8.5, loc="lower right")

    fig.text(
        0.5, 0.97,
        f"{league_label}  ·  {season_label}  ·  Over/Underperformers — Actual vs Expected Points",
        fontsize=13, fontproperties=font, color=TEXT, ha="center",
        va="top", fontweight="bold",
    )
    fig.text(
        0.5, 0.93,
        "Positive = scoring more points than xG suggests.  Negative = underperforming xG.",
        fontsize=9, fontproperties=font, color=TEXT_SUB, ha="center", va="top",
    )
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    fig.subplots_adjust(left=0.20, right=0.96, top=0.90, bottom=0.08)
    return fig_to_png(fig, dpi=150)
