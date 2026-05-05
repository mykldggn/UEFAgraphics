"""Per-match cumulative xG vs Goals arc for a single player/season."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)


def render(shots: pd.DataFrame, player_name: str, season_label: str) -> bytes:
    font = get_font()

    if shots.empty:
        return _no_data_png(player_name, season_label, font)

    df = shots.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    if df.empty:
        return _no_data_png(player_name, season_label, font)

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

    matches["cum_xg"]   = matches["xG"].cumsum()
    matches["cum_goals"] = matches["goals"].cumsum()
    x = np.arange(1, len(matches) + 1)

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor("#374151")
    ax.grid(axis="y", color="#1F2937", lw=0.8, zorder=0)

    cum_xg    = matches["cum_xg"].values
    cum_goals = matches["cum_goals"].values

    ax.fill_between(x, cum_xg, cum_goals,
                    where=cum_goals >= cum_xg,
                    color=GREEN, alpha=0.12, interpolate=True)
    ax.fill_between(x, cum_xg, cum_goals,
                    where=cum_xg > cum_goals,
                    color=RED, alpha=0.12, interpolate=True)

    ax.plot(x, cum_xg,    color=GREEN, lw=2,   ls="--", label="Cumulative xG",  zorder=3)
    ax.plot(x, cum_goals, color=AMBER, lw=2.5, ls="-",  label="Actual Goals",   zorder=3)

    ax.scatter(x, cum_xg,    s=40, color=GREEN, zorder=4)
    ax.scatter(x, cum_goals, s=40, color=AMBER, zorder=4)

    ax.annotate(f"{cum_xg[-1]:.1f}",
                xy=(x[-1], cum_xg[-1]),
                xytext=(6, 0), textcoords="offset points",
                color=GREEN, fontsize=9, va="center", fontproperties=font)
    ax.annotate(f"{int(cum_goals[-1])}",
                xy=(x[-1], cum_goals[-1]),
                xytext=(6, 0), textcoords="offset points",
                color=AMBER, fontsize=9, va="center", fontproperties=font)

    ax.set_xlabel("Match", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.set_ylabel("Cumulative", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    legend = ax.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=9, loc="upper left")

    fig.text(0.5, 0.97, f"{player_name}  ·  {season_label}  ·  xG Performance Arc",
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
