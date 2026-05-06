"""Form table — last-5 results rendered as coloured pills with a mini points bar."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_RESULT_BG     = {"W": GREEN, "D": AMBER, "L": RED}
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
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
        ax.set_facecolor(BG); ax.axis("off")
        ax.text(0.5, 0.55, f"{league_label}  ·  {season_label}", color=TEXT, fontsize=16,
                ha="center", va="center", transform=ax.transAxes, fontweight="bold",
                fontproperties=font)
        ax.text(0.5, 0.42, "No team data available", color=TEXT_SUB, fontsize=12,
                ha="center", va="center", transform=ax.transAxes, fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)
        return fig_to_png(fig, dpi=150)

    sorted_teams = sorted(
        enumerate(teams),
        key=lambda x: (_form_pts(x[1].get("form", "")), float(x[1].get("pts", 0) or 0)),
        reverse=True,
    )

    n = len(teams)
    ROW_H   = 0.038          # fixed per-row height in axes coords
    HDR_H   = 0.040          # header row height
    TOP_PAD = 0.07           # space above header for title
    BOT_PAD = 0.04           # space below last row for footer
    fig_h   = max(7.0, n * ROW_H * 22 + 2.0)

    fig = plt.figure(figsize=(10, fig_h), facecolor=BG)
    ax  = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    fig.text(0.5, 0.985, f"{league_label}  ·  {season_label}  ·  Form Table (Last 5)",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")

    # Column x positions:  #   Team   pills-start   FormPts   Pts
    CX = {"rank": 0.04, "team": 0.10, "pills": 0.37, "fpts_bar": 0.66, "pts": 0.84, "frank": 0.93}
    PILL_W   = 0.032
    PILL_GAP = 0.007
    BAR_MAX  = 0.13

    # Layout: place rows from top, evenly spaced
    usable_h = 1.0 - TOP_PAD - BOT_PAD
    row_step = usable_h / (n + 1)     # +1 for header
    hdr_top  = 1.0 - TOP_PAD

    # Header
    ax.add_patch(mpatches.Rectangle(
        (0.01, hdr_top - row_step), 0.98, row_step * 0.88,
        facecolor=BG_CARD, edgecolor="#374151", lw=0.8, zorder=1))
    hdr_cy = hdr_top - row_step * 0.50
    for key, lbl, ha in [
        ("rank",     "#",           "center"),
        ("team",     "Team",        "left"),
        ("pills",    "Form (Last 5)", "left"),
        ("fpts_bar", "Form Pts",    "left"),
        ("pts",      "Pts",         "center"),
        ("frank",    "",            "center"),
    ]:
        ax.text(CX[key], hdr_cy, lbl, fontsize=8, fontproperties=font,
                color=TEXT_SUB, ha=ha, va="center")

    best_form_orig = sorted_teams[0][0] if sorted_teams else -1

    for form_rank, (orig_idx, team) in enumerate(sorted_teams):
        actual_rank = orig_idx + 1
        form_str    = str(team.get("form", ""))[-5:].upper()
        f_pts       = _form_pts(form_str)
        pts         = float(team.get("pts", 0) or 0)
        name        = str(team.get("name", ""))[:22]

        row_top = hdr_top - row_step * (form_rank + 2)
        cy      = row_top + row_step * 0.50

        # Alternating row background
        if form_rank % 2 == 0:
            ax.add_patch(mpatches.Rectangle(
                (0.01, row_top), 0.98, row_step * 0.96,
                facecolor="#FFFFFF", alpha=0.018, edgecolor="none", zorder=1))

        # Green left accent for best form team
        if orig_idx == best_form_orig:
            ax.add_patch(mpatches.Rectangle(
                (0.005, row_top), 0.005, row_step * 0.96,
                facecolor=GREEN, alpha=0.90, edgecolor="none", zorder=2))

        ax.text(CX["rank"], cy, str(actual_rank), fontsize=8.5, fontproperties=font,
                color=TEXT_SUB, ha="center", va="center")
        ax.text(CX["team"], cy, name, fontsize=8.5, fontproperties=font,
                color=TEXT, ha="left", va="center")

        # Form pills
        results = [c for c in form_str if c in "WDL"]
        for ri, res in enumerate(results[-5:]):
            px = CX["pills"] + ri * (PILL_W + PILL_GAP) + PILL_W / 2
            ax.text(px, cy, res, fontsize=7, fontproperties=font,
                    color=BG, ha="center", va="center",
                    bbox=dict(facecolor=_RESULT_BG.get(res, TEXT_SUB),
                              edgecolor="none", boxstyle="round,pad=0.20", alpha=0.92),
                    zorder=3)

        # Form pts: background track + coloured fill
        bx    = CX["fpts_bar"]
        bar_h = row_step * 0.35
        bar_y = cy - bar_h / 2
        ax.add_patch(mpatches.Rectangle(
            (bx, bar_y), BAR_MAX, bar_h,
            facecolor="#1F2937", edgecolor="none", zorder=1))
        fill_w = (f_pts / 15) * BAR_MAX
        if fill_w > 0:
            bar_col = GREEN if f_pts >= 10 else (AMBER if f_pts >= 5 else RED)
            ax.add_patch(mpatches.Rectangle(
                (bx, bar_y), fill_w, bar_h,
                facecolor=bar_col, alpha=0.80, edgecolor="none", zorder=2))
        ax.text(bx + BAR_MAX + 0.012, cy, str(f_pts),
                fontsize=8, fontproperties=font, color=TEXT, ha="left", va="center")

        ax.text(CX["pts"], cy, str(int(pts)), fontsize=9.5, fontproperties=font,
                color=TEXT, ha="center", va="center", fontweight="bold")

        ax.text(CX["frank"], cy, f"F{form_rank + 1}", fontsize=7,
                fontproperties=font, color=TEXT_SUB, ha="center", va="center")

    fig.text(0.5, 0.008, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)
    return fig_to_png(fig, dpi=150)
