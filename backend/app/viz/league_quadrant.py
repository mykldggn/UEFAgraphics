"""League attack vs defence quadrant scatter — all teams plotted by xG / xGA."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)


def render(
    league_label: str,
    season_label: str,
    teams: list[dict],
) -> bytes:
    font = get_font()

    if not teams or len(teams) < 2:
        fig, ax = plt.subplots(figsize=(10, 9), facecolor=BG)
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

    xg_vals  = [float(t.get("xG",  0) or 0) for t in teams]
    xga_vals = [float(t.get("xGA", 0) or 0) for t in teams]
    names    = [str(t.get("name", "")) for t in teams]

    mean_xg  = np.mean(xg_vals)
    mean_xga = np.mean(xga_vals)

    fig, ax = plt.subplots(figsize=(10, 9), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")

    x_pad = (max(xg_vals)  - min(xg_vals))  * 0.12
    y_pad = (max(xga_vals) - min(xga_vals)) * 0.12
    x_min = min(xg_vals)  - x_pad
    x_max = max(xg_vals)  + x_pad
    y_min = min(xga_vals) - y_pad
    y_max = max(xga_vals) + y_pad
    x_range = x_max - x_min
    y_range = y_max - y_min

    # Quadrant fills (inverted y: low xGA = top)
    # top-right (high xG, low xGA) → GREEN = Title Contenders
    ax.fill_between([mean_xg, x_max], [y_min, y_min], [mean_xga, mean_xga],
                    color=GREEN, alpha=0.04, zorder=1)
    # bottom-right (high xG, high xGA) → AMBER = High Scoring
    ax.fill_between([mean_xg, x_max], [mean_xga, mean_xga], [y_max, y_max],
                    color=AMBER, alpha=0.04, zorder=1)
    # top-left (low xG, low xGA) → ACCENT = Resolute
    ax.fill_between([x_min, mean_xg], [y_min, y_min], [mean_xga, mean_xga],
                    color=ACCENT, alpha=0.04, zorder=1)
    # bottom-left (low xG, high xGA) → RED = Relegation Battle
    ax.fill_between([x_min, mean_xg], [mean_xga, mean_xga], [y_max, y_max],
                    color=RED, alpha=0.04, zorder=1)

    # Quadrant corner labels
    q_kw = dict(fontsize=9, fontproperties=font, color=TEXT_SUB, alpha=0.5, zorder=2)
    ax.text(x_max - x_range * 0.01, y_min + y_range * 0.01, "Title Contenders",
            ha="right", va="bottom", **q_kw)
    ax.text(x_max - x_range * 0.01, y_max - y_range * 0.01, "High Scoring",
            ha="right", va="top", **q_kw)
    ax.text(x_min + x_range * 0.01, y_min + y_range * 0.01, "Resolute",
            ha="left", va="bottom", **q_kw)
    ax.text(x_min + x_range * 0.01, y_max - y_range * 0.01, "Relegation Battle",
            ha="left", va="top", **q_kw)

    ax.axvline(mean_xg,  color=TEXT_SUB, lw=1.2, ls="--", alpha=0.6, zorder=2)
    ax.axhline(mean_xga, color=TEXT_SUB, lw=1.2, ls="--", alpha=0.6, zorder=2)

    for name, x, y in zip(names, xg_vals, xga_vals):
        color = team_color(name)
        ax.scatter(x, y, s=180, color=color, edgecolors=BG, lw=1.5, zorder=4)

        # Place label left/right and away from the mean line (y-axis is inverted)
        ha = "left" if x >= mean_xg else "right"
        va = "top" if y >= mean_xga else "bottom"
        dx = x_range * 0.012 if ha == "left" else -x_range * 0.012
        dy = y_range * 0.012 if va == "top" else -y_range * 0.012
        ax.text(x + dx, y + dy, name, fontsize=7,
                color=TEXT, fontproperties=font, ha=ha, va=va, zorder=5)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_max, y_min)  # inverted: low xGA at top
    ax.set_xlabel("xG For (Season Total)", color=TEXT_SUB, fontsize=10,
                  fontproperties=font, labelpad=6)
    ax.set_ylabel("xGA (Season Total, lower = better)", color=TEXT_SUB,
                  fontsize=10, fontproperties=font, labelpad=6)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.grid(color="#1F2937", lw=0.6, alpha=0.5)

    fig.text(0.5, 0.97, f"{league_label}  ·  {season_label}  ·  Attack vs Defense Quadrant",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    fig.subplots_adjust(left=0.10, right=0.96, top=0.93, bottom=0.07)
    return fig_to_png(fig, dpi=150)
