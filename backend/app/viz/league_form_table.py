"""Form table — last-5 results rendered as coloured pills with a mini points bar."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_RESULT_BG = {"W": GREEN, "D": AMBER, "L": RED}
_RESULT_POINTS = {"W": 3, "D": 1, "L": 0}


def _form_pts(form_str: str) -> int:
    return sum(_RESULT_POINTS.get(c.upper(), 0) for c in str(form_str) if c.upper() in "WDL")


def render(
    league_label: str,
    season_label: str,
    teams: list[dict],
) -> bytes:
    font = get_font()

    if not teams:
        fig, ax = plt.subplots(figsize=(10, 10), facecolor=BG)
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

    # Sort by form pts desc, secondary: actual pts
    sorted_by_form = sorted(
        enumerate(teams),
        key=lambda x: (
            _form_pts(x[1].get("form", "")),
            float(x[1].get("pts", 0) or 0),
        ),
        reverse=True,
    )

    n = len(teams)
    fig = plt.figure(figsize=(10, max(8, n * 0.48 + 2.8)), facecolor=BG)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    fig.text(0.5, 0.98, f"{league_label}  ·  {season_label}  ·  Form Table (Last 5)",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")

    header_y  = 0.94
    footer_y  = 0.025
    table_h   = header_y - footer_y - 0.05
    row_h     = table_h / (n + 1)

    col_xs = [0.04, 0.10, 0.44, 0.64, 0.82, 0.93]
    col_labels = ["#", "Team", "Form (Last 5)", "Form Pts", "Pts", ""]
    col_ha     = ["center", "left", "left", "center", "center", "center"]

    # Header row
    ax.add_patch(mpatches.Rectangle(
        (0.01, header_y - row_h * 0.9), 0.98, row_h * 0.9,
        facecolor=BG_CARD, edgecolor="#374151", lw=1.0, zorder=1))
    for cx, lbl, ha in zip(col_xs, col_labels, col_ha):
        ax.text(cx, header_y - row_h * 0.45, lbl,
                fontsize=8.5, fontproperties=font, color=TEXT_SUB,
                ha=ha, va="center")

    max_form_pts  = max(_form_pts(t.get("form", "")) for t in teams) if teams else 15
    best_form_idx = sorted_by_form[0][0] if sorted_by_form else -1

    for form_rank, (orig_idx, team) in enumerate(sorted_by_form):
        actual_rank = orig_idx + 1
        form_str    = str(team.get("form", ""))[-5:].upper()
        f_pts       = _form_pts(form_str)
        pts         = float(team.get("pts", 0) or 0)
        name        = str(team.get("name", ""))[:22]

        row_y = header_y - row_h * (form_rank + 1) - row_h * 0.05
        cy    = row_y - row_h * 0.40

        # Alternating BG
        if form_rank % 2 == 0:
            ax.add_patch(mpatches.Rectangle(
                (0.01, row_y - row_h * 0.82), 0.98, row_h * 0.86,
                facecolor="#FFFFFF", alpha=0.015, edgecolor="none", zorder=1))

        # Highlight best form team
        if orig_idx == best_form_idx:
            ax.add_patch(mpatches.Rectangle(
                (0.005, row_y - row_h * 0.82), 0.004, row_h * 0.86,
                facecolor=GREEN, alpha=0.90, edgecolor="none", zorder=2))

        ax.text(col_xs[0], cy, str(actual_rank), fontsize=9,
                fontproperties=font, color=TEXT_SUB, ha="center", va="center")
        ax.text(col_xs[1], cy, name, fontsize=9, fontproperties=font,
                color=TEXT, ha="left", va="center")

        # Form pills
        pill_x = col_xs[2]
        pill_w = 0.034
        pill_gap = 0.008
        results = [c for c in form_str if c in "WDL"]
        for ri, res in enumerate(results[-5:]):
            px = pill_x + ri * (pill_w + pill_gap)
            bg_col = _RESULT_BG.get(res, TEXT_SUB)
            ax.text(px, cy, res,
                    fontsize=7.5, fontproperties=font,
                    color=BG, ha="center", va="center",
                    bbox=dict(facecolor=bg_col, edgecolor="none",
                              boxstyle="round,pad=0.22", alpha=0.92),
                    zorder=3)

        # Form pts mini bar
        bar_max_w = 0.14
        bar_w = (f_pts / 15) * bar_max_w if max_form_pts > 0 else 0
        bx = col_xs[3] - bar_max_w / 2
        ax.add_patch(mpatches.Rectangle(
            (bx, cy - row_h * 0.20), bar_max_w, row_h * 0.38,
            facecolor="#1F2937", edgecolor="none", zorder=1))
        if bar_w > 0:
            bar_col = GREEN if f_pts >= 10 else (AMBER if f_pts >= 5 else RED)
            ax.add_patch(mpatches.Rectangle(
                (bx, cy - row_h * 0.20), bar_w, row_h * 0.38,
                facecolor=bar_col, alpha=0.80, edgecolor="none", zorder=2))
        ax.text(col_xs[3] + bar_max_w / 2 + 0.015, cy, str(f_pts),
                fontsize=8.5, fontproperties=font, color=TEXT,
                ha="left", va="center")

        ax.text(col_xs[4], cy, str(int(pts)), fontsize=10, fontproperties=font,
                color=TEXT, ha="center", va="center", fontweight="bold")

        # Form rank number
        ax.text(col_xs[5], cy, f"F{form_rank + 1}", fontsize=7.5,
                fontproperties=font, color=TEXT_SUB, ha="center", va="center")

    fig.text(0.5, footer_y, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    return fig_to_png(fig, dpi=150)
