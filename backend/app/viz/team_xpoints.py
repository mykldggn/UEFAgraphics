"""xG performance card — actual vs expected points stat display."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)


def render(
    team_name: str,
    season_label: str,
    league_label: str,
    actual_pts: int,
    xpts: float,
    xg: float,
    xga: float,
    actual_rank: int,
    xg_rank: int,
    league_avg_xg: float = 0.0,
    league_avg_xga: float = 0.0,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    fig = plt.figure(figsize=(9, 7), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Title
    ax.text(0.5, 0.96, team_name, fontsize=20, fontproperties=font,
            color=TEXT, ha="center", va="top", fontweight="bold")
    ax.text(0.5, 0.89, f"{league_label}  ·  {season_label}  ·  xG Performance",
            fontsize=10, fontproperties=font, color=TEXT_SUB, ha="center", va="top")

    # ── Top comparison section ────────────────────────────────────────────────
    delta = actual_pts - xpts
    delta_color = GREEN if delta > 0 else (RED if delta < 0 else TEXT_SUB)
    delta_arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
    delta_str   = f"{delta_arrow} {abs(delta):.1f} pts"

    # ACTUAL box (left)
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.03, 0.60), 0.28, 0.24,
        boxstyle="round,pad=0.015", facecolor=BG_CARD,
        edgecolor="#374151", lw=1.5))
    ax.text(0.17, 0.87, "ACTUAL", fontsize=9, fontproperties=font,
            color=TEXT_SUB, ha="center", va="top")
    ax.text(0.17, 0.79, str(actual_pts), fontsize=36, fontproperties=font,
            color=primary, ha="center", va="top", fontweight="bold")
    ax.text(0.17, 0.63, f"Rank: {actual_rank}", fontsize=9, fontproperties=font,
            color=TEXT_SUB, ha="center", va="bottom")

    # EXPECTED box (right)
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.69, 0.60), 0.28, 0.24,
        boxstyle="round,pad=0.015", facecolor=BG_CARD,
        edgecolor="#374151", lw=1.5))
    ax.text(0.83, 0.87, "EXPECTED", fontsize=9, fontproperties=font,
            color=TEXT_SUB, ha="center", va="top")
    ax.text(0.83, 0.79, f"{xpts:.1f}", fontsize=36, fontproperties=font,
            color=ACCENT, ha="center", va="top", fontweight="bold")
    ax.text(0.83, 0.63, f"xPts Rank: {xg_rank}", fontsize=9, fontproperties=font,
            color=TEXT_SUB, ha="center", va="bottom")

    # Delta centre
    ax.text(0.5, 0.77, delta_str, fontsize=22, fontproperties=font,
            color=delta_color, ha="center", va="center", fontweight="bold")
    ax.text(0.5, 0.63, "vs expected", fontsize=8, fontproperties=font,
            color=TEXT_SUB, ha="center", va="bottom")

    # ── 4 stat boxes ─────────────────────────────────────────────────────────
    stat_data = [
        ("xG",    f"{xg:.2f}",  ACCENT),
        ("xGA",   f"{xga:.2f}", RED),
        ("xG Rank",  str(xg_rank),   TEXT),
        ("vs Avg xG", f"{xg - league_avg_xg:+.2f}" if league_avg_xg > 0 else "—", TEXT_SUB),
    ]

    box_w = 0.20
    box_h = 0.13
    gap   = 0.016
    total_w = len(stat_data) * box_w + (len(stat_data) - 1) * gap
    x_start = (1 - total_w) / 2

    for i, (lbl, val, col) in enumerate(stat_data):
        bx = x_start + i * (box_w + gap)
        ax.add_patch(mpatches.FancyBboxPatch(
            (bx, 0.42), box_w, box_h,
            boxstyle="round,pad=0.012", facecolor=BG_CARD,
            edgecolor="#374151", lw=1.2))
        ax.text(bx + box_w / 2, 0.42 + box_h * 0.72, val,
                fontsize=16, fontproperties=font, color=col,
                ha="center", va="center", fontweight="bold")
        ax.text(bx + box_w / 2, 0.42 + box_h * 0.22, lbl,
                fontsize=7.5, fontproperties=font, color=TEXT_SUB,
                ha="center", va="center")

    # League avg comparison row (if provided)
    if league_avg_xg > 0 or league_avg_xga > 0:
        ax.text(0.5, 0.39, (f"League avg xG: {league_avg_xg:.2f}  ·  "
                             f"League avg xGA: {league_avg_xga:.2f}"),
                fontsize=8.5, fontproperties=font, color=TEXT_SUB,
                ha="center", va="top")

    # xG bar comparison
    ax_bar = fig.add_axes([0.10, 0.15, 0.80, 0.07])
    ax_bar.set_facecolor(BG)
    ax_bar.axis("off")
    ax_bar.set_xlim(0, max(xg, xga, league_avg_xg, league_avg_xga, 1) * 1.15)
    ax_bar.set_ylim(-0.5, 2.5)

    ax_bar.barh(1.5, xg,  height=0.5, color=ACCENT, alpha=0.8, label="xG")
    ax_bar.barh(0.5, xga, height=0.5, color=RED,    alpha=0.8, label="xGA")
    ax_bar.text(-0.15, 1.5, "xG",  fontsize=8, color=ACCENT,  va="center",
                ha="right", fontproperties=font)
    ax_bar.text(-0.15, 0.5, "xGA", fontsize=8, color=RED,     va="center",
                ha="right", fontproperties=font)
    if league_avg_xg > 0:
        ax_bar.axvline(league_avg_xg,  color=ACCENT, lw=1.2, ls="--", alpha=0.5)
    if league_avg_xga > 0:
        ax_bar.axvline(league_avg_xga, color=RED,    lw=1.2, ls="--", alpha=0.5)

    # Bottom note
    ax.text(0.5, 0.09,
            "xPts = expected points based on xG data. Positive delta = outperforming expected.",
            fontsize=8, fontproperties=font, color=TEXT_SUB, ha="center", va="top",
            style="italic")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    return fig_to_png(fig, dpi=150)
