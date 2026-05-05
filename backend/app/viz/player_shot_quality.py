"""xG histogram showing shot quality distribution and conversion rate per bin."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_BIN_EDGES = [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70, 1.0]
_BIN_LABELS = ["0–5", "5–10", "10–15", "15–20", "20–25", "25–30", "30–40", "40–50", "50–70", "70–100"]


def render(shots: pd.DataFrame, player_name: str, season_label: str) -> bytes:
    font = get_font()

    if shots.empty:
        return _no_data_png(player_name, season_label, font)

    df = shots.copy()
    df["xG"] = pd.to_numeric(df["xG"], errors="coerce")
    df = df.dropna(subset=["xG"])

    if df.empty:
        return _no_data_png(player_name, season_label, font)

    goals_df = df[df["result"] == "Goal"]

    all_counts, _ = np.histogram(df["xG"].values, bins=_BIN_EDGES)
    goal_counts, _ = np.histogram(goals_df["xG"].values, bins=_BIN_EDGES)

    n_bins   = len(_BIN_LABELS)
    x        = np.arange(n_bins)
    bar_w    = 0.38

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor("#374151")
    ax.grid(axis="y", color="#1F2937", lw=0.8, zorder=0)

    ax.bar(x - bar_w / 2, all_counts,  width=bar_w, color="#3B82F6", alpha=0.6,
           label="All Shots", zorder=3)
    ax.bar(x + bar_w / 2, goal_counts, width=bar_w, color=AMBER,     alpha=0.9,
           label="Goals",     zorder=3)

    for i in range(n_bins):
        total = int(all_counts[i])
        goals = int(goal_counts[i])
        if total > 0:
            top_y = max(all_counts[i], goal_counts[i]) + 0.2
            ax.text(x[i], top_y, f"{goals}/{total}",
                    ha="center", fontsize=7, color=TEXT_SUB, fontproperties=font)

    ax.set_xticks(x)
    ax.set_xticklabels(_BIN_LABELS, fontsize=8, color=TEXT_SUB, rotation=45, ha="right")
    ax.set_xlabel("xG per shot (%)", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.set_ylabel("Count", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)

    total_shots  = len(df)
    total_goals  = len(goals_df)
    conv_pct     = (total_goals / total_shots * 100) if total_shots else 0
    info_text    = f"Shots: {total_shots}    Goals: {total_goals}    Conv: {conv_pct:.1f}%"
    ax.text(0.98, 0.97, info_text,
            transform=ax.transAxes, fontsize=9, color=TEXT, ha="right", va="top",
            fontproperties=font,
            bbox=dict(facecolor=BG_CARD, edgecolor="#374151", boxstyle="round,pad=0.4", lw=1))

    ax.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=9, loc="upper left")

    fig.text(0.5, 0.97, f"{player_name}  ·  {season_label}  ·  Shot Quality Distribution",
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
