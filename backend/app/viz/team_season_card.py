"""
Team Season Summary Card.
Combines: league table position over time, key stats block,
top scorers bar, xG vs Goals scatter.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import matplotlib.ticker as ticker
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB,
    fig_to_png, get_font, team_color,
)


def render(
    team_name: str,
    season_label: str,
    league_label: str,
    position_history: list[dict],
    stats: dict,
    top_scorers: list[dict] | None = None,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    # ── Derive tinted colours from primary ────────────────────────────────────
    try:
        pr        = mcolors.to_rgb(primary)
        card_bg   = mcolors.to_hex(tuple(min(1.0, c * 0.18 + 0.07) for c in pr))
        card_edge = mcolors.to_hex(tuple(min(1.0, c * 0.45 + 0.06) for c in pr))
        hdr_bg    = mcolors.to_hex(tuple(min(1.0, c * 0.22 + 0.05) for c in pr))
    except Exception:
        card_bg   = BG_CARD
        card_edge = "#1F2937"
        hdr_bg    = BG_CARD

    fig = plt.figure(figsize=(10, 12), facecolor=BG)

    # ── Header — team-coloured gradient background ─────────────────────────────
    ax_hdr = fig.add_axes([0, 0.91, 1, 0.09])
    ax_hdr.axis("off")
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)

    # Horizontal gradient: primary tint left → dark right
    gradient = np.linspace(0, 1, 256).reshape(1, -1)
    ax_hdr.imshow(
        gradient, aspect="auto", extent=[0, 1, 0, 1],
        cmap=mcolors.LinearSegmentedColormap.from_list("hdr", [hdr_bg, BG_CARD]),
        zorder=0,
    )
    # Accent bar on left edge
    ax_hdr.add_patch(mpatches.Rectangle((0, 0), 0.008, 1,
                                         color=primary, zorder=2, alpha=0.95))
    ax_hdr.text(0.04, 0.76, team_name, fontsize=22, fontproperties=font,
                color=TEXT, fontweight="bold", va="top", zorder=3)
    ax_hdr.text(0.04, 0.28, f"{league_label}  ·  {season_label}",
                fontsize=10, fontproperties=font, color=TEXT_SUB, va="top", zorder=3)

    # ── League position over time ──────────────────────────────────────────────
    # Extra bottom padding (labelpad) pushes x-axis label clear of stats block
    ax_pos = fig.add_axes([0.10, 0.67, 0.86, 0.21])
    ax_pos.set_facecolor(BG)
    for sp in ax_pos.spines.values():
        sp.set_edgecolor("#374151")

    if position_history and len(position_history) >= 5:
        matchdays = [p["matchday"] for p in position_history]
        positions = [p["position"] for p in position_history]
        ax_pos.plot(matchdays, positions, color=primary, lw=2.2, zorder=3)
        ax_pos.fill_between(matchdays, positions,
                            max(positions) + 1,
                            color=primary, alpha=0.10, zorder=2)
        ax_pos.scatter(matchdays[-1], positions[-1], s=80, color=primary,
                       zorder=5, edgecolors=BG, lw=1.5)
        ax_pos.text(matchdays[-1] + 0.5, positions[-1],
                    f"P{positions[-1]}", fontsize=8, color=primary,
                    va="center", fontproperties=font)
        ax_pos.invert_yaxis()
        ax_pos.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, nbins=6))
        ax_pos.set_xlim(min(matchdays), max(matchdays) + 1)
    else:
        final_pos = stats.get("final_position") or (
            position_history[0]["position"] if position_history else None
        )
        if final_pos:
            ax_pos.text(0.5, 0.55, f"P{int(final_pos)}", fontsize=56,
                        color=primary, ha="center", va="center",
                        fontproperties=font, fontweight="bold",
                        transform=ax_pos.transAxes, alpha=0.85)
            ax_pos.text(0.5, 0.18, "Final League Position", fontsize=9,
                        color=TEXT_SUB, ha="center", va="center",
                        fontproperties=font, transform=ax_pos.transAxes)
        else:
            ax_pos.text(0.5, 0.5, "No position data", color=TEXT_SUB,
                        ha="center", va="center", transform=ax_pos.transAxes,
                        fontproperties=font)

    ax_pos.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_pos.set_ylabel("Position", color=TEXT_SUB, fontsize=8, fontproperties=font, labelpad=4)
    ax_pos.set_xlabel("Matchday", color=TEXT_SUB, fontsize=8, fontproperties=font, labelpad=6)
    ax_pos.grid(axis="both", color="#1F2937", lw=0.6)

    # ── Stats helper ──────────────────────────────────────────────────────────
    def sv(key, fmt=".0f", default="—"):
        val = stats.get(key)
        if val is None:
            return default
        try:
            return format(float(val), fmt)
        except (ValueError, TypeError):
            return str(val)

    STAT_BLOCKS = [
        ("W",       sv("wins")),
        ("D",       sv("draws")),
        ("L",       sv("losses")),
        ("GF",      sv("goals_for")),
        ("GA",      sv("goals_against")),
        ("GD",      sv("goal_diff", "+.0f")),
        ("xG",      sv("xG", ".1f")),
        ("xGA",     sv("xGA", ".1f")),
        ("xPts",    sv("xPts", ".1f")),
        ("Pts",     sv("points")),
        ("CS",      sv("clean_sheets")),
        ("Pos",     sv("final_position", ".0f")),
    ]

    # ── Season stats grid ──────────────────────────────────────────────────────
    ax_stats = fig.add_axes([0.02, 0.43, 0.96, 0.21])
    ax_stats.set_facecolor(BG); ax_stats.axis("off")
    ax_stats.set_xlim(0, 1); ax_stats.set_ylim(0, 1)
    n_cols = 6; n_rows = 2
    pad = 0.010
    cw = 1 / n_cols; ch = 1 / n_rows

    for idx, (label, val) in enumerate(STAT_BLOCKS):
        r = idx // n_cols; c = idx % n_cols
        x0 = c * cw + pad; y0 = 1 - (r + 1) * ch + pad
        ax_stats.add_patch(mpatches.FancyBboxPatch(
            (x0, y0), cw - 2 * pad, ch - 2 * pad,
            boxstyle="round,pad=0.01", facecolor=card_bg,
            edgecolor=card_edge, lw=1.2))
        cx = x0 + (cw - 2 * pad) / 2
        ax_stats.text(cx, y0 + (ch - 2 * pad) * 0.72, val,
                      fontsize=16, fontproperties=font, color=primary,
                      fontweight="bold", ha="center", va="center")
        ax_stats.text(cx, y0 + (ch - 2 * pad) * 0.28, label,
                      fontsize=7.5, fontproperties=font, color=TEXT_SUB,
                      ha="center", va="center")

    # ── Stats legend key ───────────────────────────────────────────────────────
    ax_key = fig.add_axes([0.02, 0.405, 0.96, 0.020])
    ax_key.set_facecolor(BG); ax_key.axis("off")
    ax_key.set_xlim(0, 1); ax_key.set_ylim(0, 1)
    KEY = ("W Wins  ·  D Draws  ·  L Losses  ·  GF Goals For  ·  GA Goals Against  ·  "
           "GD Goal Diff  ·  xG Exp. Goals  ·  xGA Exp. Goals Against  ·  "
           "xPts Exp. Points  ·  Pts Points  ·  CS Clean Sheets  ·  Pos Final Position")
    ax_key.text(0.5, 0.5, KEY, fontsize=6.5, fontproperties=font,
                color="#4B5563", ha="center", va="center")

    # ── Top scorers bar ────────────────────────────────────────────────────────
    ax_score = fig.add_axes([0.10, 0.07, 0.86, 0.30])
    ax_score.set_facecolor(BG)
    for sp in ax_score.spines.values():
        sp.set_edgecolor("#374151")

    if top_scorers:
        scorers = top_scorers[:8]
        names   = [s.get("player", "?")[:18] for s in scorers]
        goals_v = [float(s.get("goals", 0)) for s in scorers]
        xg_v    = [float(s.get("xG", 0)) for s in scorers]
        ys      = np.arange(len(scorers))[::-1]
        ax_score.barh(ys, goals_v, color=primary,  alpha=0.85, label="Goals", height=0.55, zorder=3)
        ax_score.barh(ys, xg_v,   color=card_edge, alpha=0.65, label="xG",   height=0.55, zorder=2)
        ax_score.set_yticks(ys)
        ax_score.set_yticklabels(names, fontsize=8, color=TEXT_SUB)
        ax_score.tick_params(colors=TEXT_SUB, labelsize=8)
        ax_score.set_xlabel("Goals / xG", color=TEXT_SUB, fontsize=8,
                            fontproperties=font, labelpad=6)
        ax_score.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8)
        ax_score.grid(axis="x", color="#1F2937", lw=0.6)
        ax_score.set_title("Top Scorers", fontsize=10, color=TEXT_SUB,
                           fontproperties=font, loc="left", pad=8)
    else:
        ax_score.text(0.5, 0.5, "No scorer data", color=TEXT_SUB,
                      ha="center", va="center", transform=ax_score.transAxes,
                      fontproperties=font)

    # ── Footer ─────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.015, "Data: FBref / Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)
