"""5-match rolling form chart for xG and goals."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)


def render(shots: pd.DataFrame, player_name: str, season_label: str) -> bytes:
    font = get_font()

    if shots.empty:
        return _no_data_png(player_name, season_label, font, "No shot data")

    df = shots.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    if df.empty:
        return _no_data_png(player_name, season_label, font, "No shot data")

    group_col = "match_id" if "match_id" in df.columns else "date"
    matches = (
        df.groupby(group_col, sort=False)
        .agg(
            date=("date", "first"),
            xG=("xG", "sum"),
            goals=("result", lambda s: (s == "Goal").sum()),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    if len(matches) < 2:
        return _no_data_png(player_name, season_label, font, "Not enough data")

    matches["roll_xg"]   = matches["xG"].rolling(5, min_periods=1).mean()
    matches["roll_goals"] = matches["goals"].rolling(5, min_periods=1).mean()
    x = np.arange(1, len(matches) + 1)

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor("#374151")
    ax.grid(axis="y", color="#1F2937", lw=0.8, zorder=0)

    bar_w = 0.4
    ax.bar(x - bar_w / 2, matches["xG"].values,    width=bar_w, color=GREEN, alpha=0.20, zorder=2)
    ax.bar(x + bar_w / 2, matches["goals"].values,  width=bar_w, color=AMBER, alpha=0.25, zorder=2)

    ax.plot(x, matches["roll_xg"].values,    color=GREEN, lw=2,   ls="--",
            label="Rolling xG (5-match)",   zorder=3)
    ax.plot(x, matches["roll_goals"].values, color=AMBER, lw=2.5, ls="-",
            label="Rolling Goals (5-match)", zorder=3)

    ax.set_xlabel("Match", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.set_ylabel("Per match / Rolling avg", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    last5_xg    = float(matches["xG"].tail(5).mean())
    last5_goals = int(matches["goals"].tail(5).sum())
    form_text   = f"Last 5:  {last5_xg:.2f} xG/match  ·  {last5_goals} goals"
    ax.text(0.98, 0.97, form_text,
            transform=ax.transAxes, fontsize=9, color=TEXT, ha="right", va="top",
            fontproperties=font,
            bbox=dict(facecolor=BG_CARD, edgecolor="#374151", boxstyle="round,pad=0.4", lw=1))

    ax.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=9, loc="upper left")

    fig.text(0.5, 0.97, f"{player_name}  ·  {season_label}  ·  Rolling Form (5-match)",
             fontsize=14, fontproperties=font, color=TEXT,
             ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    return fig_to_png(fig, dpi=150)


def _no_data_png(player_name: str, season_label: str, font, msg: str) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 4), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.text(0.5, 0.6, player_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, f"{msg} for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
