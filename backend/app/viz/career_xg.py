"""
Career xG vs Goals chart.
Line chart showing cumulative xG and Goals over career (or filtered seasons).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED,
    fig_to_png, get_font, team_color,
)


def render(
    player_name: str,
    shots_df: pd.DataFrame,
    # columns: date, season, xG, result, team (optional)
    seasons: list[int] | None = None,   # None = all seasons
    team: str = "",
) -> bytes:
    font    = get_font()
    primary = team_color(team)

    if shots_df.empty:
        return _no_data_png(player_name, font)

    df = shots_df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")
    elif "season" in df.columns:
        df = df.sort_values("season")

    if seasons:
        df = df[df["season"].isin(seasons)]

    if df.empty:
        return _no_data_png(player_name, font)

    df["goal"] = (df["result"] == "Goal").astype(int)
    df["cum_xG"]    = df["xG"].cumsum()
    df["cum_goals"] = df["goal"].cumsum()

    # ── Per-season bar summary ────────────────────────────────────────────────
    season_stats = (
        df.groupby("season", sort=True)
        .agg(xG=("xG", "sum"), goals=("goal", "sum"))
        .reset_index()
    )

    single_season = len(season_stats) == 1

    fig = plt.figure(figsize=(10, 8), facecolor=BG)

    # ── Top: cumulative line chart ─────────────────────────────────────────────
    ax_line = fig.add_axes([0.08, 0.44, 0.88, 0.46])
    ax_line.set_facecolor(BG)
    for spine in ax_line.spines.values():
        spine.set_edgecolor("#374151")

    x = np.arange(len(df))
    ax_line.plot(x, df["cum_xG"].values,    color=ACCENT, lw=2.2, label="Cumulative xG", zorder=3)
    ax_line.plot(x, df["cum_goals"].values,  color=GREEN,  lw=2.2, label="Cumulative Goals", zorder=3)
    ax_line.fill_between(x, df["cum_xG"].values, df["cum_goals"].values,
                         where=df["cum_xG"].values >= df["cum_goals"].values,
                         alpha=0.10, color=ACCENT, interpolate=True)
    ax_line.fill_between(x, df["cum_xG"].values, df["cum_goals"].values,
                         where=df["cum_xG"].values < df["cum_goals"].values,
                         alpha=0.10, color=GREEN, interpolate=True)

    ax_line.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_line.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, nbins=6))
    ax_line.set_ylabel("Cumulative", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_line.set_xlabel("Shot #", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_line.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=9, loc="upper left")

    # Season boundary markers
    if "season" in df.columns:
        prev_s = None
        for i, row in df.reset_index(drop=True).iterrows():
            if prev_s is not None and row["season"] != prev_s:
                ax_line.axvline(i, color="#374151", lw=1, ls="--", alpha=0.6)
                ax_line.text(i + len(df) * 0.005, ax_line.get_ylim()[1] * 0.96,
                             str(int(row["season"])),
                             color=TEXT_SUB, fontsize=7, fontproperties=font, va="top")
            prev_s = row["season"]

    # Final annotations
    final_xg    = float(df["cum_xG"].iloc[-1])
    final_goals = int(df["cum_goals"].iloc[-1])
    diff        = final_xg - final_goals
    diff_label  = f"+{diff:.1f} xG" if diff > 0 else f"{diff:.1f} xG"
    diff_color  = RED if diff > 1 else (GREEN if diff < -1 else TEXT_SUB)
    ax_line.text(0.98, 0.06, diff_label,
                 transform=ax_line.transAxes, color=diff_color,
                 fontsize=10, ha="right", fontproperties=font,
                 bbox=dict(facecolor=BG_CARD, edgecolor=diff_color, boxstyle="round,pad=0.3", lw=1))

    # ── Bottom: per-season bar chart ──────────────────────────────────────────
    ax_bar = fig.add_axes([0.08, 0.06, 0.88, 0.32])
    ax_bar.set_facecolor(BG)
    for spine in ax_bar.spines.values():
        spine.set_edgecolor("#374151")

    n_seasons = len(season_stats)
    xs = np.arange(n_seasons)
    # Narrow bars for single season so they don't stretch wall-to-wall
    bar_w = 0.35 if n_seasons > 1 else 0.15
    ax_bar.bar(xs - bar_w / 2, season_stats["xG"],   width=bar_w, color=ACCENT,
               alpha=0.85, label="xG",    zorder=3)
    ax_bar.bar(xs + bar_w / 2, season_stats["goals"], width=bar_w, color=GREEN,
               alpha=0.85, label="Goals", zorder=3)

    for i, (_, row) in enumerate(season_stats.iterrows()):
        ax_bar.text(i - bar_w / 2, float(row["xG"]) + 0.1,
                    f"{row['xG']:.1f}", ha="center", fontsize=7,
                    color=TEXT_SUB, fontproperties=font)
        ax_bar.text(i + bar_w / 2, float(row["goals"]) + 0.1,
                    str(int(row["goals"])), ha="center", fontsize=7,
                    color=TEXT_SUB, fontproperties=font)

    ax_bar.set_xticks(xs)
    ax_bar.set_xticklabels([str(int(s)) for s in season_stats["season"]], fontsize=8, color=TEXT_SUB)
    ax_bar.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_bar.set_ylabel("Per Season", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_bar.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=9)
    ax_bar.grid(axis="y", color="#1F2937", lw=0.8)
    # For single season, constrain x-axis so bars sit centred rather than filling the width
    if n_seasons == 1:
        ax_bar.set_xlim(-0.5, 0.5)

    # ── Title ──────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.97, player_name, fontsize=18, fontproperties=font,
             color=TEXT, ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.940, "Career xG vs Goals",
             fontsize=11, fontproperties=font, color=TEXT_SUB, ha="center", va="top")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(player_name: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 4), facecolor=BG)
    ax.set_facecolor(BG); ax.axis("off")
    ax.text(0.5, 0.6, player_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, "No shot data available", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
