"""League table with actual vs expected points comparison."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_UCL_COLOR = "#FFD700"


def render(
    league_label: str,
    season_label: str,
    teams: list[dict],
) -> bytes:
    font = get_font()

    if not teams:
        fig, ax = plt.subplots(figsize=(10, 12), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.55, f"{league_label}  ·  {season_label}",
                color=TEXT, fontsize=16, ha="center", va="center",
                transform=ax.transAxes, fontweight="bold", fontproperties=font)
        ax.text(0.5, 0.42, "No team data available", color=TEXT_SUB,
                fontsize=12, ha="center", va="center", transform=ax.transAxes,
                fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    sorted_teams = list(teams)  # already sorted by pts desc
    n = len(sorted_teams)

    # Compute xPts ranking separately
    xpts_sorted = sorted(enumerate(sorted_teams),
                         key=lambda x: float(x[1].get("xPts", 0) or 0),
                         reverse=True)
    xpts_rank = {orig_idx: rank + 1 for rank, (orig_idx, _) in enumerate(xpts_sorted)}

    fig = plt.figure(figsize=(10, max(8, n * 0.42 + 2.5)), facecolor=BG)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    fig_h = fig.get_figheight()
    header_y  = 0.95
    footer_y  = 0.025
    table_h   = header_y - footer_y - 0.06
    row_h     = table_h / (n + 1)

    # ── Header block ──────────────────────────────────────────────────────────
    fig.text(0.5, 0.98, f"{league_label}  ·  {season_label}  ·  Expected vs Actual Table",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")

    col_xs = [0.04, 0.09, 0.42, 0.53, 0.63, 0.73, 0.83, 0.93]
    col_labels = ["#", "Team", "Pts", "xPts", "Δ", "xG", "xGA", "Trend"]
    col_ha     = ["center", "left", "center", "center", "center", "center", "center", "center"]

    hdr_y = header_y - 0.01
    ax.add_patch(mpatches.Rectangle(
        (0.01, hdr_y - row_h * 0.9), 0.98, row_h * 0.9,
        facecolor=BG_CARD, edgecolor="#374151", lw=1.0, zorder=1))
    for cx, lbl, ha in zip(col_xs, col_labels, col_ha):
        ax.text(cx, hdr_y - row_h * 0.45, lbl,
                fontsize=8.5, fontproperties=font, color=TEXT_SUB,
                ha=ha, va="center")

    # ── Rows ──────────────────────────────────────────────────────────────────
    for i, team in enumerate(sorted_teams):
        actual_rank = i + 1
        xr          = xpts_rank.get(i, actual_rank)
        rank_delta  = actual_rank - xr   # positive = better in actual than xPts

        pts   = float(team.get("pts",  0) or 0)
        xpts  = float(team.get("xPts", 0) or 0)
        xg    = float(team.get("xG",   0) or 0)
        xga   = float(team.get("xGA",  0) or 0)
        delta = pts - xpts

        row_y = hdr_y - row_h * (i + 1) - row_h * 0.05

        # Alternating background
        if i % 2 == 0:
            ax.add_patch(mpatches.Rectangle(
                (0.01, row_y - row_h * 0.85), 0.98, row_h * 0.88,
                facecolor="#FFFFFF", alpha=0.015, edgecolor="none", zorder=1))

        # UCL zone highlight (top 4)
        if actual_rank <= 4:
            ax.add_patch(mpatches.Rectangle(
                (0.005, row_y - row_h * 0.85), 0.006, row_h * 0.88,
                facecolor=_UCL_COLOR, alpha=0.90, edgecolor="none", zorder=2))

        cy = row_y - row_h * 0.38

        # Rank
        ax.text(col_xs[0], cy, str(actual_rank), fontsize=9,
                fontproperties=font, color=TEXT_SUB, ha="center", va="center")

        # Rank trend arrow
        if rank_delta > 0:
            arrow_str = f"↑{rank_delta}"
            arrow_col = GREEN
        elif rank_delta < 0:
            arrow_str = f"↓{abs(rank_delta)}"
            arrow_col = RED
        else:
            arrow_str = "—"
            arrow_col = TEXT_SUB

        # Team name + arrow
        name = str(team.get("name", ""))[:22]
        ax.text(col_xs[1], cy, name, fontsize=9, fontproperties=font,
                color=TEXT, ha="left", va="center")
        ax.text(col_xs[1] + 0.29, cy, arrow_str, fontsize=7.5,
                fontproperties=font, color=arrow_col, ha="right", va="center")

        # Pts
        ax.text(col_xs[2], cy, str(int(pts)), fontsize=10, fontproperties=font,
                color=TEXT, ha="center", va="center", fontweight="bold")

        # xPts
        ax.text(col_xs[3], cy, f"{xpts:.1f}", fontsize=9, fontproperties=font,
                color=ACCENT, ha="center", va="center")

        # Delta
        d_col = GREEN if delta > 0 else (RED if delta < 0 else TEXT_SUB)
        d_str = f"{delta:+.1f}"
        ax.text(col_xs[4], cy, d_str, fontsize=9, fontproperties=font,
                color=d_col, ha="center", va="center", fontweight="bold")

        # xG
        ax.text(col_xs[5], cy, f"{xg:.1f}", fontsize=9, fontproperties=font,
                color=TEXT_SUB, ha="center", va="center")

        # xGA
        ax.text(col_xs[6], cy, f"{xga:.1f}", fontsize=9, fontproperties=font,
                color=TEXT_SUB, ha="center", va="center")

        # Trend (xPts rank)
        ax.text(col_xs[7], cy, f"xR{xr}", fontsize=8, fontproperties=font,
                color=TEXT_SUB, ha="center", va="center")

    # Footer note
    fig.text(0.5, footer_y,
             "xPts = Expected Points based on xG.  Arrow shows position change in xG table.  "
             "Data: Understat  ·  UEFAgraphics",
             fontsize=7.5, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    return fig_to_png(fig, dpi=150)
