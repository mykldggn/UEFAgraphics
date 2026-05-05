"""Shot and xG breakdown by situation (OpenPlay, SetPiece, etc.)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_SITUATIONS = ["OpenPlay", "SetPiece", "FromCorner", "DirectFreekick", "Penalty"]
_LABELS     = ["Open Play", "Set Piece", "Corner", "Free Kick", "Penalty"]
_COLORS     = {
    "OpenPlay":       "#3B82F6",
    "SetPiece":       "#F59E0B",
    "FromCorner":     "#22C55E",
    "DirectFreekick": "#8B5CF6",
    "Penalty":        "#EF4444",
}


def render(shots: pd.DataFrame, player_name: str, season_label: str) -> bytes:
    font = get_font()

    if shots.empty:
        return _no_data_png(player_name, season_label, font)

    df = shots.copy()

    rows = []
    for sit in _SITUATIONS:
        sub = df[df["situation"] == sit]
        rows.append({
            "situation": sit,
            "shots":     len(sub),
            "goals":     int((sub["result"] == "Goal").sum()),
            "xg":        float(sub["xG"].sum()),
        })
    stats = pd.DataFrame(rows)

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(10, 6), facecolor=BG)
    fig.subplots_adjust(wspace=0.05)

    y      = np.arange(len(_SITUATIONS))
    bar_h  = 0.35
    colors = [_COLORS[s] for s in _SITUATIONS]

    for ax in (ax_left, ax_right):
        ax.set_facecolor(BG)
        for spine in ax.spines.values():
            spine.set_edgecolor("#374151")
        ax.grid(axis="x", color="#1F2937", lw=0.8, zorder=0)
        ax.tick_params(colors=TEXT_SUB, labelsize=8)

    # Left: shots count + goals overlay
    ax_left.barh(y + bar_h / 2, stats["shots"], height=bar_h,
                 color=colors, alpha=0.7, label="Shots", zorder=3)
    ax_left.barh(y - bar_h / 2, stats["goals"], height=bar_h,
                 color=colors, alpha=1.0, label="Goals", zorder=3)

    for i, row in stats.iterrows():
        if row["shots"] > 0:
            ax_left.text(row["shots"] + 0.1, i + bar_h / 2,
                         str(int(row["shots"])), va="center", fontsize=8,
                         color=TEXT_SUB, fontproperties=font)
        if row["goals"] > 0:
            ax_left.text(row["goals"] + 0.1, i - bar_h / 2,
                         str(int(row["goals"])), va="center", fontsize=8,
                         color=TEXT, fontproperties=font)

    ax_left.set_yticks(y)
    ax_left.set_yticklabels(_LABELS, fontsize=9, color=TEXT)
    ax_left.set_xlabel("Count", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_left.set_title("Shots & Goals", color=TEXT_SUB, fontsize=10, fontproperties=font)
    ax_left.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8, loc="lower right")

    # Right: xG + actual goals per situation
    ax_right.barh(y + bar_h / 2, stats["xg"],   height=bar_h,
                  color=colors, alpha=0.7, label="xG",    zorder=3)
    ax_right.barh(y - bar_h / 2, stats["goals"], height=bar_h,
                  color=colors, alpha=1.0, label="Goals", zorder=3)

    for i, row in stats.iterrows():
        if row["xg"] > 0:
            ax_right.text(row["xg"] + 0.02, i + bar_h / 2,
                          f"{row['xg']:.2f}", va="center", fontsize=8,
                          color=TEXT_SUB, fontproperties=font)
        if row["goals"] > 0:
            ax_right.text(row["goals"] + 0.02, i - bar_h / 2,
                          str(int(row["goals"])), va="center", fontsize=8,
                          color=TEXT, fontproperties=font)

    ax_right.set_yticks(y)
    ax_right.set_yticklabels([])
    ax_right.set_xlabel("Value", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_right.set_title("xG & Goals", color=TEXT_SUB, fontsize=10, fontproperties=font)
    ax_right.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8, loc="lower right")

    fig.text(0.5, 0.97, f"{player_name}  ·  {season_label}  ·  Shot Situations",
             fontsize=14, fontproperties=font, color=TEXT,
             ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    return fig_to_png(fig, dpi=150)


def _no_data_png(player_name: str, season_label: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 4), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.text(0.5, 0.6, player_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, f"No shot data for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
