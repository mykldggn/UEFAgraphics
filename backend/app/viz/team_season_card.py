"""
Team Season Summary Card.
Combines: league table position over time, key stats block,
top scorers bar, xG vs Goals scatter.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)


def render(
    team_name: str,
    season_label: str,
    league_label: str,
    # League position over time — list of dicts {matchday, position}
    position_history: list[dict],
    # Season stats
    stats: dict,
    # top scorers: [{player, goals, xG}]
    top_scorers: list[dict] | None = None,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    fig = plt.figure(figsize=(10, 12), facecolor=BG)

    # ── Header ─────────────────────────────────────────────────────────────────
    ax_hdr = fig.add_axes([0, 0.90, 1, 0.10])
    ax_hdr.set_facecolor(BG_CARD); ax_hdr.axis("off")
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)
    ax_hdr.axvline(x=0.008, color=primary, lw=8, alpha=0.9)
    ax_hdr.text(0.04, 0.75, team_name, fontsize=22, fontproperties=font,
                color=TEXT, fontweight="bold", va="top")
    ax_hdr.text(0.04, 0.30, f"{league_label}  ·  {season_label}",
                fontsize=10, fontproperties=font, color=TEXT_SUB, va="top")

    # ── League position over time ──────────────────────────────────────────────
    ax_pos = fig.add_axes([0.08, 0.62, 0.88, 0.26])
    ax_pos.set_facecolor(BG)
    for sp in ax_pos.spines.values():
        sp.set_edgecolor("#374151")

    if position_history:
        matchdays = [p["matchday"] for p in position_history]
        positions = [p["position"] for p in position_history]
        ax_pos.plot(matchdays, positions, color=primary, lw=2.2, zorder=3)
        ax_pos.fill_between(matchdays, positions,
                            max(positions) + 1,
                            color=primary, alpha=0.10, zorder=2)
        ax_pos.scatter(matchdays[-1], positions[-1], s=80, color=primary,
                       zorder=5, edgecolors=BG, lw=1.5)
        ax_pos.invert_yaxis()
        ax_pos.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, nbins=6))
        ax_pos.set_xlim(min(matchdays), max(matchdays))
    else:
        ax_pos.text(0.5, 0.5, "No position data", color=TEXT_SUB,
                    ha="center", va="center", transform=ax_pos.transAxes,
                    fontproperties=font)

    ax_pos.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_pos.set_ylabel("League Position", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_pos.set_xlabel("Matchday", color=TEXT_SUB, fontsize=9, fontproperties=font)
    ax_pos.grid(axis="both", color="#1F2937", lw=0.6)

    # ── Season stats grid ──────────────────────────────────────────────────────
    def sv(key, fmt=".0f", default="—"):
        val = stats.get(key)
        if val is None:
            return default
        try:
            return format(float(val), fmt)
        except (ValueError, TypeError):
            return str(val)

    STAT_BLOCKS = [
        ("W",          sv("wins"),          GREEN),
        ("D",          sv("draws"),         AMBER),
        ("L",          sv("losses"),        RED),
        ("GF",         sv("goals_for"),     GREEN),
        ("GA",         sv("goals_against"), RED),
        ("GD",         sv("goal_diff", "+.0f"), ACCENT),
        ("xG",         sv("xG", ".1f"),     GREEN),
        ("xGA",        sv("xGA", ".1f"),    RED),
        ("xPts",       sv("xPts", ".1f"),   ACCENT),
        ("Pts",        sv("points"),        primary),
        ("Clean Sheets", sv("clean_sheets"), GREEN),
        ("Pos",        sv("final_position", ".0f"), primary),
    ]

    ax_stats = fig.add_axes([0.02, 0.38, 0.96, 0.22])
    ax_stats.set_facecolor(BG); ax_stats.axis("off")
    ax_stats.set_xlim(0, 1); ax_stats.set_ylim(0, 1)
    n_cols = 6; n_rows = 2
    pad = 0.010
    cw = 1 / n_cols; ch = 1 / n_rows

    for idx, (label, val, col) in enumerate(STAT_BLOCKS):
        r = idx // n_cols; c = idx % n_cols
        x0 = c * cw + pad; y0 = 1 - (r + 1) * ch + pad
        ax_stats.add_patch(mpatches.FancyBboxPatch(
            (x0, y0), cw - 2 * pad, ch - 2 * pad,
            boxstyle="round,pad=0.01", facecolor=BG_CARD,
            edgecolor="#1F2937", lw=0.8))
        cx = x0 + (cw - 2 * pad) / 2
        ax_stats.text(cx, y0 + (ch - 2 * pad) * 0.72, val,
                      fontsize=16, fontproperties=font, color=col,
                      fontweight="bold", ha="center", va="center")
        ax_stats.text(cx, y0 + (ch - 2 * pad) * 0.30, label,
                      fontsize=7.5, fontproperties=font, color=TEXT_SUB,
                      ha="center", va="center")

    # ── Top scorers bar ────────────────────────────────────────────────────────
    ax_score = fig.add_axes([0.08, 0.10, 0.88, 0.26])
    ax_score.set_facecolor(BG)
    for sp in ax_score.spines.values():
        sp.set_edgecolor("#374151")

    if top_scorers:
        scorers = top_scorers[:8]
        names   = [s.get("player", "?")[:16] for s in scorers]
        goals_v = [float(s.get("goals", 0)) for s in scorers]
        xg_v    = [float(s.get("xG", 0)) for s in scorers]
        ys      = np.arange(len(scorers))[::-1]
        ax_score.barh(ys, goals_v, color=primary,    alpha=0.85, label="Goals",   height=0.5, zorder=3)
        ax_score.barh(ys, xg_v,   color=TEXT_SUB,   alpha=0.45, label="xG",      height=0.5, zorder=2)
        ax_score.set_yticks(ys)
        ax_score.set_yticklabels(names, fontsize=8, color=TEXT_SUB)
        ax_score.tick_params(colors=TEXT_SUB, labelsize=8)
        ax_score.set_xlabel("Goals", color=TEXT_SUB, fontsize=9, fontproperties=font)
        ax_score.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8)
        ax_score.grid(axis="x", color="#1F2937", lw=0.6)
        ax_score.set_title("Top Scorers", fontsize=10, color=TEXT_SUB,
                           fontproperties=font, loc="left")
    else:
        ax_score.text(0.5, 0.5, "No scorer data", color=TEXT_SUB,
                      ha="center", va="center", transform=ax_score.transAxes,
                      fontproperties=font)

    # ── Footer ─────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.015, "Data: FBref / Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)
