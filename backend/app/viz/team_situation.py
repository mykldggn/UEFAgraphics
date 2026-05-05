"""Goal situation breakdown — donut chart + xG vs goals bar chart."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_SIT_DISPLAY = {
    "OpenPlay":        "Open Play",
    "SetPiece":        "Set Piece",
    "FromCorner":      "Corner",
    "DirectFreekick":  "Free Kick",
    "Penalty":         "Penalty",
}
_SIT_COLORS = {
    "OpenPlay":       "#3B82F6",
    "SetPiece":       "#F59E0B",
    "FromCorner":     "#22C55E",
    "DirectFreekick": "#8B5CF6",
    "Penalty":        "#EF4444",
}
_SITUATIONS = list(_SIT_DISPLAY.keys())


def render(shots_df: "pd.DataFrame", team_name: str, season_label: str) -> bytes:
    font = get_font()

    try:
        import pandas as pd
        empty = shots_df is None or (hasattr(shots_df, "empty") and shots_df.empty)
    except Exception:
        empty = True

    if empty:
        fig, ax = plt.subplots(figsize=(10, 7), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.55, team_name, color=TEXT, fontsize=18, ha="center",
                va="center", transform=ax.transAxes, fontweight="bold",
                fontproperties=font)
        ax.text(0.5, 0.42, "No shot data available", color=TEXT_SUB,
                fontsize=12, ha="center", va="center", transform=ax.transAxes,
                fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    situation_col = shots_df["situation"] if "situation" in shots_df.columns else None
    result_col    = shots_df["result"]    if "result"    in shots_df.columns else None
    xg_col        = shots_df["xG"]        if "xG"        in shots_df.columns else None

    shot_counts = {}
    goal_counts = {}
    xg_totals   = {}

    for sit in _SITUATIONS:
        mask = (situation_col == sit) if situation_col is not None else shots_df.index == -1
        shot_counts[sit] = int(mask.sum()) if situation_col is not None else 0
        if result_col is not None:
            goal_counts[sit] = int((mask & (result_col == "Goal")).sum())
        else:
            goal_counts[sit] = 0
        if xg_col is not None:
            xg_totals[sit] = float(shots_df.loc[mask, "xG"].sum()) if shot_counts[sit] > 0 else 0.0
        else:
            xg_totals[sit] = 0.0

    total_shots = sum(shot_counts.values())
    total_goals = sum(goal_counts.values())
    active_sits = [s for s in _SITUATIONS if shot_counts[s] > 0]
    if not active_sits:
        active_sits = _SITUATIONS

    fig = plt.figure(figsize=(10, 7), facecolor=BG)
    fig.text(0.5, 0.97, f"{team_name}  ·  {season_label}  ·  Goal Situations",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")

    # Left panel — donut
    ax_donut = fig.add_axes([0.02, 0.10, 0.44, 0.82])
    ax_donut.set_facecolor(BG)
    ax_donut.axis("off")

    shot_vals = [shot_counts[s] for s in active_sits]
    goal_vals = [goal_counts[s] for s in active_sits]
    colors_sit = [_SIT_COLORS[s] for s in active_sits]

    def _autopct_shot(pct):
        return f"{pct:.1f}%" if pct > 3 else ""

    wedges_outer, texts_outer, autotexts = ax_donut.pie(
        shot_vals,
        radius=1.0,
        colors=colors_sit,
        startangle=90,
        wedgeprops=dict(width=0.38, edgecolor=BG, lw=1.5),
        autopct=_autopct_shot,
        pctdistance=0.82,
    )
    for t in autotexts:
        t.set_fontsize(7.5)
        t.set_color(TEXT)
        t.set_fontproperties(font)

    goal_vals_safe = [max(g, 0) for g in goal_vals]
    if sum(goal_vals_safe) > 0:
        ax_donut.pie(
            goal_vals_safe,
            radius=0.58,
            colors=colors_sit,
            startangle=90,
            wedgeprops=dict(width=0.28, edgecolor=BG, lw=1.5),
        )

    ax_donut.text(0, 0.12, str(total_shots), fontsize=18, color=TEXT,
                  ha="center", va="center", fontproperties=font,
                  fontweight="bold")
    ax_donut.text(0, -0.14, "shots", fontsize=9, color=TEXT_SUB,
                  ha="center", va="center", fontproperties=font)
    ax_donut.text(0, -0.38, str(total_goals), fontsize=13, color=GREEN,
                  ha="center", va="center", fontproperties=font,
                  fontweight="bold")
    ax_donut.text(0, -0.56, "goals", fontsize=8, color=TEXT_SUB,
                  ha="center", va="center", fontproperties=font)

    legend_patches = [
        mpatches.Patch(color=_SIT_COLORS[s],
                       label=_SIT_DISPLAY[s])
        for s in active_sits
    ]
    ax_donut.legend(handles=legend_patches, frameon=False, labelcolor=TEXT,
                    prop=font, fontsize=8, loc="lower center",
                    bbox_to_anchor=(0.5, -0.04), ncol=3)

    # Right panel — xG vs goals bar
    ax_bar = fig.add_axes([0.52, 0.12, 0.44, 0.76])
    ax_bar.set_facecolor(BG)
    for sp in ax_bar.spines.values():
        sp.set_edgecolor("#374151")

    ys = np.arange(len(active_sits))
    xg_bar  = [xg_totals[s]   for s in active_sits]
    goal_bar = [goal_counts[s] for s in active_sits]
    colors_a = [_SIT_COLORS[s] for s in active_sits]

    ax_bar.barh(ys, xg_bar,  color=colors_a, alpha=0.35, height=0.55, zorder=2, label="xG")
    ax_bar.barh(ys, goal_bar, color=colors_a, alpha=0.90, height=0.35, zorder=3, label="Goals")

    for i, (xg_v, g) in enumerate(zip(xg_bar, goal_bar)):
        ax_bar.text(max(xg_v, g) + 0.05, i,
                    f"  {g}G  {xg_v:.1f}xG",
                    fontsize=7.5, color=TEXT_SUB, va="center",
                    fontproperties=font)

    ax_bar.set_yticks(ys)
    ax_bar.set_yticklabels([_SIT_DISPLAY[s] for s in active_sits],
                           fontsize=8.5, color=TEXT, fontproperties=font)
    ax_bar.set_xlabel("Total", color=TEXT_SUB, fontsize=9,
                      fontproperties=font, labelpad=6)
    ax_bar.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_bar.grid(axis="x", color="#1F2937", lw=0.6)
    ax_bar.legend(frameon=False, labelcolor=TEXT, prop=font,
                  fontsize=8, loc="lower right")

    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    return fig_to_png(fig, dpi=150)
