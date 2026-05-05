"""Golden boot race — top scorers with goals vs xG comparison bars."""
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
    players: list[dict],
) -> bytes:
    font = get_font()

    if not players:
        fig, ax = plt.subplots(figsize=(10, 9), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.55, f"{league_label}  ·  {season_label}",
                color=TEXT, fontsize=16, ha="center", va="center",
                transform=ax.transAxes, fontweight="bold", fontproperties=font)
        ax.text(0.5, 0.42, "No player data available", color=TEXT_SUB,
                fontsize=12, ha="center", va="center", transform=ax.transAxes,
                fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    top15 = sorted(players,
                   key=lambda p: float(p.get("goals", 0) or 0),
                   reverse=True)[:15]
    top15 = top15[::-1]  # bottom-to-top

    names      = []
    goals_list = []
    xg_list    = []
    colors     = []

    for p in top15:
        pname = str(p.get("player", ""))
        tname = str(p.get("team",   ""))
        g     = float(p.get("goals", 0) or 0)
        xg    = float(p.get("xg",   0) or p.get("xG", 0) or 0)

        names.append(pname)
        goals_list.append(g)
        xg_list.append(xg)

        # Bar color: over-performing = GREEN, under = RED
        tol = 1.5
        if g > xg + tol:
            colors.append(GREEN)
        elif g < xg - tol:
            colors.append(RED)
        else:
            colors.append(team_color(tname))

    ys = np.arange(len(top15))

    fig, ax = plt.subplots(figsize=(10, 9), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")

    # xG bar (background, wider)
    ax.barh(ys, xg_list, color=TEXT_SUB, alpha=0.30, height=0.65,
            zorder=2, label="xG (expected)")
    # Goals bar (foreground, slightly narrower)
    ax.barh(ys, goals_list, color=colors, alpha=0.88, height=0.50,
            zorder=3, label="Goals")

    max_val = max(max(goals_list), max(xg_list)) if goals_list else 1

    for i, (g, xg) in enumerate(zip(goals_list, xg_list)):
        ax.text(max(g, xg) + max_val * 0.012, i,
                f"  {int(g)}G  {xg:.1f}xG",
                fontsize=7.5, color=TEXT_SUB, va="center",
                fontproperties=font)

    # y labels: player name + team below in smaller text
    for i, p in enumerate(top15):
        pname = str(p.get("player", ""))
        tname = str(p.get("team",   ""))[:14]
        ax.text(-max_val * 0.01, i + 0.18, pname,
                fontsize=8.5, color=TEXT, ha="right", va="center",
                fontproperties=font)
        ax.text(-max_val * 0.01, i - 0.18, tname,
                fontsize=6.5, color=TEXT_SUB, ha="right", va="center",
                fontproperties=font)

    ax.set_yticks([])
    ax.set_xlim(0, max_val * 1.25)
    ax.set_xlabel("Goals / xG", color=TEXT_SUB, fontsize=9,
                  fontproperties=font, labelpad=6)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.grid(axis="x", color="#1F2937", lw=0.6)

    legend_patches = [
        mpatches.Patch(color=TEXT_SUB, alpha=0.30, label="xG (expected)"),
        mpatches.Patch(color=GREEN,    label="Over-performing"),
        mpatches.Patch(color=RED,      label="Under-performing"),
        mpatches.Patch(color=ACCENT,   label="On track"),
    ]
    ax.legend(handles=legend_patches, frameon=False, labelcolor=TEXT,
              prop=font, fontsize=8, loc="lower right")

    fig.text(0.5, 0.97,
             f"{league_label}  ·  {season_label}  ·  Golden Boot Race — Goals vs xG",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    fig.subplots_adjust(left=0.22, right=0.96, top=0.93, bottom=0.07)
    return fig_to_png(fig, dpi=150)
