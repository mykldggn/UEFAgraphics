"""
Team xG / xPts timeline across a season.
Shows per-match xG for/against bars plus cumulative lines.
Uses data from understat_service.get_team_xg_history().
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)


def render(
    team_name: str,
    season_label: str,
    history: list[dict],
    # Each dict: match, date, opponent, xG, xGA, cumulative_xG, cumulative_xGA,
    #            goals, goals_against
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    if not history:
        return _no_data_png(team_name, season_label, font)

    matches       = [h["match"] for h in history]
    xg_per        = [h["xG"] for h in history]
    xga_per       = [h["xGA"] for h in history]
    cum_xg        = [h["cumulative_xG"] for h in history]
    cum_xga       = [h["cumulative_xGA"] for h in history]
    goals         = [h["goals"] for h in history]
    goals_against = [h["goals_against"] for h in history]

    fig = plt.figure(figsize=(12, 9), facecolor=BG)

    # ── Title ──────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.97, team_name, fontsize=18, fontproperties=font,
             color=TEXT, ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.955, f"{season_label} — xG Timeline",
             fontsize=11, fontproperties=font, color=TEXT_SUB, ha="center", va="top")

    xs = np.array(matches)

    # ── Top panel: cumulative xG vs xGA ────────────────────────────────────────
    ax_cum = fig.add_axes([0.08, 0.52, 0.88, 0.40])
    ax_cum.set_facecolor(BG)
    for sp in ax_cum.spines.values():
        sp.set_edgecolor("#374151")

    ax_cum.plot(xs, cum_xg,  color=GREEN,   lw=2.2, label="Cumulative xG",  zorder=3)
    ax_cum.plot(xs, cum_xga, color=RED,     lw=2.2, label="Cumulative xGA", zorder=3)
    ax_cum.fill_between(xs, cum_xg, cum_xga,
                        where=np.array(cum_xg) >= np.array(cum_xga),
                        alpha=0.12, color=GREEN, interpolate=True)
    ax_cum.fill_between(xs, cum_xg, cum_xga,
                        where=np.array(cum_xg) < np.array(cum_xga),
                        alpha=0.12, color=RED, interpolate=True)

    # Plot actual goals as scatter
    ax_cum.scatter(xs, np.cumsum(goals),         s=30, color=GREEN, zorder=5,
                   alpha=0.7, label="Actual Goals")
    ax_cum.scatter(xs, np.cumsum(goals_against),  s=30, color=RED,   zorder=5,
                   alpha=0.7, marker="v", label="Goals Conceded")

    ax_cum.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_cum.set_ylabel("Cumulative", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_cum.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8,
                  loc="upper left", ncol=2)
    ax_cum.grid(axis="y", color="#1F2937", lw=0.6)
    ax_cum.set_xlim(0.5, max(matches) + 0.5)

    # ── Bottom panel: per-match xG bars ────────────────────────────────────────
    ax_bar = fig.add_axes([0.08, 0.10, 0.88, 0.36])
    ax_bar.set_facecolor(BG)
    for sp in ax_bar.spines.values():
        sp.set_edgecolor("#374151")

    bar_w = 0.38
    ax_bar.bar(xs - bar_w / 2, xg_per,  width=bar_w, color=GREEN, alpha=0.85,
               label="xG For",    zorder=3)
    ax_bar.bar(xs + bar_w / 2, xga_per, width=bar_w, color=RED,   alpha=0.85,
               label="xG Against", zorder=3)

    # Actual goal annotations on top of bars
    for i, (g, ga) in enumerate(zip(goals, goals_against)):
        ax_bar.text(xs[i] - bar_w / 2, xg_per[i] + 0.04, str(g),
                    ha="center", fontsize=6, color=TEXT_SUB, fontproperties=font)
        ax_bar.text(xs[i] + bar_w / 2, xga_per[i] + 0.04, str(ga),
                    ha="center", fontsize=6, color=TEXT_SUB, fontproperties=font)

    # Opponent labels (every 5 matches)
    opponents = [h.get("opponent", "") or "" for h in history]
    step = max(1, len(matches) // 10)
    ax_bar.set_xticks(xs[::step])
    ax_bar.set_xticklabels(
        [opponents[i][:8] if i < len(opponents) else "" for i in range(0, len(xs), step)],
        fontsize=7, color=TEXT_SUB, rotation=30, ha="right"
    )
    ax_bar.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_bar.set_ylabel("Per Match", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_bar.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8)
    ax_bar.grid(axis="y", color="#1F2937", lw=0.6)
    ax_bar.set_xlim(0.5, max(matches) + 0.5)

    # ── Season summary pills ───────────────────────────────────────────────────
    total_xg  = cum_xg[-1]
    total_xga = cum_xga[-1]
    total_g   = sum(goals)
    total_ga  = sum(goals_against)

    fig.text(0.5, 0.025,
             f"xG: {total_xg:.1f}   xGA: {total_xga:.1f}   Goals: {total_g}   Goals Against: {total_ga}"
             f"   Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(team_name: str, season_label: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG)
    ax.set_facecolor(BG); ax.axis("off")
    ax.text(0.5, 0.6, team_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, f"No data for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
