"""Squad minutes breakdown — horizontal bar chart coloured by position."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_POS_COLORS = {"GK": AMBER, "DEF": ACCENT, "MID": GREEN, "FWD": RED}


def _pos_category(pos: str) -> str:
    p = (pos or "").upper()
    if p.startswith("G"):
        return "GK"
    if p.startswith("D"):
        return "DEF"
    if p.startswith("M"):
        return "MID"
    return "FWD"


def render(players: list[dict], team_name: str, season_label: str) -> bytes:
    font = get_font()

    if not players:
        fig, ax = plt.subplots(figsize=(10, 9), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.55, team_name, color=TEXT, fontsize=18, ha="center",
                va="center", transform=ax.transAxes, fontweight="bold",
                fontproperties=font)
        ax.text(0.5, 0.42, "No squad data available", color=TEXT_SUB,
                fontsize=12, ha="center", va="center", transform=ax.transAxes,
                fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    sorted_players = sorted(players, key=lambda p: float(p.get("minutes", 0) or 0),
                            reverse=True)[:20]
    sorted_players = sorted_players[::-1]  # bottom-to-top for barh

    names = []
    for p in sorted_players:
        name = str(p.get("player", ""))
        parts = name.split()
        names.append(parts[-1] if len(parts) > 1 and len(parts[-1]) > 2 else name)

    minutes = [float(p.get("minutes", 0) or 0) for p in sorted_players]
    goals_list = [int(p.get("goals", 0) or 0) for p in sorted_players]
    assists_list = [int(p.get("assists", 0) or 0) for p in sorted_players]
    colors = [_POS_COLORS[_pos_category(p.get("pos", ""))] for p in sorted_players]

    fig, ax = plt.subplots(figsize=(10, 9), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")

    ys = np.arange(len(sorted_players))
    ax.barh(ys, minutes, color=colors, alpha=0.85, height=0.65, zorder=3)

    max_mins = max(minutes) if minutes else 3000
    for i, (m, g, a) in enumerate(zip(minutes, goals_list, assists_list)):
        parts = []
        if g > 0:
            parts.append(f"{g}G")
        if a > 0:
            parts.append(f"{a}A")
        if parts:
            ax.text(m + max_mins * 0.01, i, "  ".join(parts),
                    fontsize=7.5, color=TEXT_SUB, va="center",
                    fontproperties=font)

    ax.axvline(900,  color=TEXT_SUB, lw=1.0, ls="--", alpha=0.5, zorder=2)
    ax.axvline(2700, color=TEXT_SUB, lw=1.0, ls="--", alpha=0.5, zorder=2)
    ax.text(900,  len(sorted_players) - 0.3, "10 games", fontsize=7,
            color=TEXT_SUB, ha="center", fontproperties=font)
    ax.text(2700, len(sorted_players) - 0.3, "30 games", fontsize=7,
            color=TEXT_SUB, ha="center", fontproperties=font)

    ax.set_yticks(ys)
    ax.set_yticklabels(names, fontsize=8.5, color=TEXT, fontproperties=font)
    ax.set_xlim(0, max_mins + max_mins * 0.18)
    ax.set_xlabel("Minutes Played", color=TEXT_SUB, fontsize=9,
                  fontproperties=font, labelpad=6)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.grid(axis="x", color="#1F2937", lw=0.6)

    legend_patches = [mpatches.Patch(color=c, label=l)
                      for l, c in _POS_COLORS.items()]
    ax.legend(handles=legend_patches, frameon=False, labelcolor=TEXT,
              prop=font, fontsize=8, loc="lower right", ncol=4)

    fig.text(0.5, 0.97, f"{team_name}  ·  {season_label}  ·  Squad Minutes",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)

    fig.subplots_adjust(left=0.18, right=0.96, top=0.93, bottom=0.06)
    return fig_to_png(fig, dpi=150)
