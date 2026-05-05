"""Cumulative top-scorer goal timeline across the season."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_PALETTE = [ACCENT, RED, GREEN, AMBER, "#8B5CF6"]


def render(shots_df: "pd.DataFrame", team_name: str, season_label: str) -> bytes:
    font = get_font()

    try:
        empty = shots_df is None or (hasattr(shots_df, "empty") and shots_df.empty)
    except Exception:
        empty = True

    if empty:
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
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

    import pandas as pd

    df = shots_df.copy()
    if "result" not in df.columns or "player" not in df.columns or "date" not in df.columns:
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.5, "Insufficient columns in shot data",
                color=TEXT_SUB, fontsize=12, ha="center", va="center",
                transform=ax.transAxes, fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    goals_df = df[df["result"] == "Goal"].copy()
    if goals_df.empty:
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.5, "No goals recorded yet",
                color=TEXT_SUB, fontsize=13, ha="center", va="center",
                transform=ax.transAxes, fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    goals_df["date"] = pd.to_datetime(goals_df["date"], errors="coerce")
    goals_df = goals_df.dropna(subset=["date"])

    top_scorers = (
        goals_df.groupby("player")
        .size()
        .sort_values(ascending=False)
        .head(5)
        .index.tolist()
    )

    if len(top_scorers) < 1:
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.5, "Not enough scorer data",
                color=TEXT_SUB, fontsize=13, ha="center", va="center",
                transform=ax.transAxes, fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    all_dates = sorted(goals_df["date"].dt.normalize().unique())
    date_idx  = {d: i for i, d in enumerate(all_dates)}
    xs = np.arange(len(all_dates))

    fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")

    for pi, player in enumerate(top_scorers):
        color = _PALETTE[pi % len(_PALETTE)]
        p_goals = goals_df[goals_df["player"] == player].copy()
        p_goals["date_norm"] = p_goals["date"].dt.normalize()

        cumulative = np.zeros(len(all_dates))
        for d in p_goals["date_norm"]:
            if d in date_idx:
                cumulative[date_idx[d]] += 1
        cumulative = np.cumsum(cumulative)

        total = int(cumulative[-1]) if len(cumulative) > 0 else 0
        ax.plot(xs, cumulative, color=color, lw=2.2, zorder=3,
                label=f"{player} ({total})")

        # Dot markers where player scored
        scoring_dates = p_goals["date_norm"].unique()
        for sd in scoring_dates:
            if sd in date_idx:
                xi = date_idx[sd]
                ax.scatter(xi, cumulative[xi], s=55, color=color,
                           edgecolors=BG, lw=1, zorder=5)

        # End label
        if len(cumulative) > 0:
            name_short = player.split()[-1] if len(player.split()) > 1 else player
            ax.text(xs[-1] + 0.2, cumulative[-1],
                    f" {name_short} {total}",
                    fontsize=7.5, color=color, va="center",
                    fontproperties=font)

    n = len(all_dates)
    step = max(1, n // 12)
    tick_indices = list(range(0, n, step))
    ax.set_xticks([xs[i] for i in tick_indices])
    ax.set_xticklabels(
        [str(all_dates[i])[:10] for i in tick_indices],
        fontsize=7, color=TEXT_SUB, rotation=35, ha="right",
        fontproperties=font,
    )
    ax.set_ylabel("Cumulative Goals", color=TEXT_SUB, fontsize=10,
                  fontproperties=font, labelpad=6)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.grid(axis="y", color="#1F2937", lw=0.6)
    ax.set_xlim(-0.5, n + 0.5)

    ax.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8.5,
              loc="upper left", ncol=min(len(top_scorers), 3))

    fig.text(0.5, 0.97, f"{team_name}  ·  {season_label}  ·  Top Scorer Timeline",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)
    fig.subplots_adjust(left=0.08, right=0.88, top=0.92, bottom=0.12)
    return fig_to_png(fig, dpi=150)
