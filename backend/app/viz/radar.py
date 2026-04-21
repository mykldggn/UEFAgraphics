"""
Player percentile radar / pizza chart.
Uses mplsoccer's PyPizza for the donut-style pizza chart.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import PyPizza

from app.viz.common import BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, fig_to_png, get_font, team_color

# Stat groups — keys map to PARAM_TO_STAT below (which maps to canonical
# column names produced by fbref_service.get_combined_player_stats)
# All params use Understat columns (available for every player, every league)
ATTACKER_PARAMS = [
    "Goals/90", "xG/90", "npxG/90", "Shots/90",
    "Assists/90", "xA/90", "Key Passes/90",
    "xGChain/90", "xGBuildup/90",
]
MIDFIELDER_PARAMS = [
    "Goals/90", "xG/90", "Assists/90", "xA/90",
    "Key Passes/90", "Shots/90",
    "xGChain/90", "xGBuildup/90", "npxG/90",
]
DEFENDER_PARAMS = [
    "xGChain/90", "xGBuildup/90",
    "Goals/90", "Assists/90", "xA/90",
    "Key Passes/90", "xG/90", "npxG/90",
]
GK_PARAMS = [
    "xGBuildup/90", "xGChain/90",
    "Goals/90", "Assists/90", "xA/90",
]

POSITION_PARAMS = {
    "FW": ATTACKER_PARAMS, "ST": ATTACKER_PARAMS, "Attacker": ATTACKER_PARAMS,
    "MF": MIDFIELDER_PARAMS, "CM": MIDFIELDER_PARAMS, "AM": MIDFIELDER_PARAMS,
    "DM": MIDFIELDER_PARAMS, "Midfielder": MIDFIELDER_PARAMS,
    "DF": DEFENDER_PARAMS,  "CB": DEFENDER_PARAMS, "FB": DEFENDER_PARAMS,
    "WB": DEFENDER_PARAMS,  "Defender": DEFENDER_PARAMS,
    "GK": GK_PARAMS,        "Goalkeeper": GK_PARAMS,
    "Sub": ATTACKER_PARAMS,
}

# Display param name → Understat stat column name
PARAM_TO_STAT: dict[str, str] = {
    "Goals/90":      "goals_p90",
    "Assists/90":    "assists_p90",
    "xG/90":         "xg_p90",
    "npxG/90":       "npxg_p90",
    "xA/90":         "xa_p90",
    "Shots/90":      "shots_p90",
    "Key Passes/90": "key_passes_p90",
    "xGChain/90":    "xgchain_p90",
    "xGBuildup/90":  "xgbuildup_p90",
}

# Colour bands
SLICE_COLORS = {
    "high":   "#22C55E",   # top 80th pct
    "mid":    "#3B82F6",   # 40–80th
    "low":    "#EF4444",   # bottom 40th
}


def _pct_color(pct: float) -> str:
    if pct >= 80:
        return SLICE_COLORS["high"]
    if pct >= 40:
        return SLICE_COLORS["mid"]
    return SLICE_COLORS["low"]


def render(
    player_name: str,
    position: str,
    season_label: str,
    percentiles: dict[str, float],   # param_name → 0-100 percentile
    raw_values: dict[str, float],     # param_name → raw stat value
    team: str = "",
    compare_name: str | None = None,
    compare_percentiles: dict[str, float] | None = None,
) -> bytes:
    params = POSITION_PARAMS.get(position[:2].upper(), ATTACKER_PARAMS)
    # Filter to params we actually have data for
    params = [p for p in params if p in percentiles]
    if len(params) < 4:
        params = list(percentiles.keys())[:12]

    values = [round(percentiles.get(p, 0), 1) for p in params]
    raw    = [f"{raw_values.get(p, 0):.2f}" for p in params]
    colors = [_pct_color(v) for v in values]

    primary = team_color(team)
    font    = get_font()

    baker = PyPizza(
        params=params,
        straight_line_color=BG,
        straight_line_lw=1,
        last_circle_lw=1,
        other_circle_lw=1,
        inner_circle_size=20,
    )

    fig, ax = baker.make_pizza(
        values,
        figsize=(8, 8.5),
        color_blank_space="same",
        slice_colors=colors,
        value_colors=["#FFFFFF"] * len(params),
        value_bck_colors=colors,
        blank_alpha=0.4,
        kwargs_slices=dict(edgecolor=BG, zorder=2, linewidth=1),
        kwargs_params=dict(color=TEXT, fontsize=9, fontproperties=font, va="center"),
        kwargs_values=dict(fontsize=9, fontproperties=font, zorder=3,
                           bbox=dict(edgecolor=BG, facecolor="none", boxstyle="round,pad=0.2", lw=1.5)),
    )
    fig.patch.set_facecolor(BG)

    # Title
    fig.text(0.515, 0.975, player_name, ha="center", va="top",
             fontsize=18, fontproperties=font, color=TEXT, fontweight="bold")
    fig.text(0.515, 0.955, f"{season_label}  ·  {team}" if team else season_label,
             ha="center", va="top", fontsize=11, fontproperties=font, color=TEXT_SUB)
    fig.text(0.515, 0.025, "Percentile vs league peers  ·  Data: FBref  ·  UEFAgraphics",
             ha="center", va="bottom", fontsize=8, fontproperties=font, color="#374151")

    # Legend pills
    for xi, (label, col) in enumerate(SLICE_COLORS.items()):
        fig.text(0.30 + xi * 0.14, 0.935,
                 {"high": "Top 20%", "mid": "Top 60%", "low": "Bottom 40%"}[label],
                 ha="center", fontsize=8, color=col, fontproperties=font,
                 bbox=dict(facecolor=BG_CARD, edgecolor=col, boxstyle="round,pad=0.3", lw=1))

    return fig_to_png(fig, dpi=150)
