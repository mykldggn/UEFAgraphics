"""Season-by-season grouped bar comparison for a player."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_METRICS = [
    ("Goals",     "goals",      RED,       1.0,   "Goals"),
    ("Assists",   "assists",    GREEN,     1.0,   "Assists"),
    ("xG",        "xg",         "#3B82F6", 1.0,   "xG"),
    ("xA",        "xa",         "#06B6D4", 1.0,   "xA"),
    ("Shots/10",  "shots",      AMBER,     0.1,   "Shots ÷10"),
    ("KP/5",      "key_passes", "#8B5CF6", 0.2,   "Key Passes ÷5"),
]


def render(season_stats: list[dict], player_name: str) -> bytes:
    font = get_font()

    if not season_stats:
        return _no_data_png(player_name, font)

    seasons = season_stats[-6:]
    n       = len(seasons)
    n_met   = len(_METRICS)
    group_w = 0.7
    bar_w   = group_w / n_met

    x = np.arange(n)

    fig = plt.figure(figsize=(12, 7), facecolor=BG)
    ax  = fig.add_axes([0.07, 0.28, 0.90, 0.60])
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor("#374151")
    ax.grid(axis="y", color="#1F2937", lw=0.8, zorder=0)

    for mi, (label, key, color, scale, legend_label) in enumerate(_METRICS):
        vals = [float(s.get(key, 0) or 0) * scale for s in seasons]
        offsets = (mi - n_met / 2 + 0.5) * bar_w
        bars = ax.bar(x + offsets, vals, width=bar_w * 0.92,
                      color=color, alpha=0.85, label=legend_label, zorder=3)

    x_labels = [
        f"{s.get('season', '')}\n{s.get('team', '')}"
        for s in seasons
    ]
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=8, color=TEXT_SUB)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.set_ylabel("Value (scaled)", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6))

    legend = ax.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8,
                       loc="upper left", ncol=3)

    # Table: minutes + apps per season
    ax_table = fig.add_axes([0.07, 0.06, 0.90, 0.18])
    ax_table.set_facecolor(BG_CARD)
    ax_table.axis("off")

    col_labels  = [s.get("season", "") for s in seasons]
    row_labels  = ["Apps", "Minutes"]
    table_data  = [
        [str(int(s.get("apps", 0) or 0))     for s in seasons],
        [str(int(s.get("minutes", 0) or 0))  for s in seasons],
    ]

    tbl = ax_table.table(
        cellText=table_data,
        rowLabels=row_labels,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_facecolor(BG_CARD)
        cell.set_edgecolor("#374151")
        cell.set_text_props(color=TEXT if row > 0 else TEXT_SUB,
                            fontproperties=font)

    fig.text(0.5, 0.97, f"{player_name}  ·  Season-by-Season Comparison",
             fontsize=15, fontproperties=font, color=TEXT,
             ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(player_name: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 4), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.text(0.5, 0.6, player_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, "No season data available", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
