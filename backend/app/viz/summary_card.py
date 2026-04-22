"""
Player Season Summary Card.
A compact infographic with key stats, a mini xG bar, and position context.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)


def render(
    player_name: str,
    position: str,
    team: str,
    season_label: str,
    stats: dict[str, float | str | int],
    # Expected keys (use what's available):
    # goals, assists, xG, xA, npxG, minutes, apps,
    # pass_cmp_pct, key_passes, prog_passes,
    # tackles, interceptions, pressures,
    # dribbles, fouls_won, aerials_won_pct
    league_label: str = "",
    nationality: str = "",
    age: str = "",
) -> bytes:
    primary = team_color(team)
    font    = get_font()

    fig = plt.figure(figsize=(8, 10), facecolor=BG)

    # ── Header band ────────────────────────────────────────────────────────────
    ax_hdr = fig.add_axes([0, 0.86, 1, 0.14])
    ax_hdr.set_facecolor(BG_CARD); ax_hdr.axis("off")
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)

    # Accent bar on left edge
    ax_hdr.axvline(x=0.008, color=primary, lw=8, alpha=0.9)

    ax_hdr.text(0.04, 0.78, player_name, fontsize=22, fontproperties=font,
                color=TEXT, fontweight="bold", va="top")

    meta_parts = [p for p in [position, team, league_label, season_label] if p]
    ax_hdr.text(0.04, 0.40, "  ·  ".join(meta_parts),
                fontsize=10, fontproperties=font, color=TEXT_SUB, va="top")

    if nationality or age:
        bio = "  ·  ".join(p for p in [nationality, f"Age {age}" if age else ""] if p)
        ax_hdr.text(0.04, 0.16, bio,
                    fontsize=9, fontproperties=font, color=TEXT_SUB, va="top")

    # ── Stat grid ──────────────────────────────────────────────────────────────
    # Define which blocks to show, with fallback
    def s(key, fmt=".2f", default=None):
        val = stats.get(key, default)
        if val is None:
            return "—"
        try:
            return format(float(val), fmt)
        except (ValueError, TypeError):
            return str(val)

    def pct_bar(ax, rect, value, max_val, color):
        """Draw a small horizontal fill-bar inside rect (left, bottom, w, h)."""
        l, b, w, h = rect
        ax.add_patch(mpatches.FancyBboxPatch(
            (l, b), w, h, boxstyle="round,pad=0.002",
            facecolor="#1F2937", edgecolor="none"))
        fill = min(float(value) / max_val, 1.0) if max_val else 0
        ax.add_patch(mpatches.FancyBboxPatch(
            (l, b), w * fill, h, boxstyle="round,pad=0.002",
            facecolor=color, edgecolor="none", alpha=0.85))

    ALL_BLOCKS = [
        # (label, value_str, bar_value, bar_max, bar_color)
        ("Goals",         s("goals", ".0f"),        stats.get("goals"),        30,  primary),
        ("Assists",       s("assists", ".0f"),       stats.get("assists"),      20,  primary),
        ("xG",            s("xG"),                   stats.get("xG"),           25,  primary),
        ("xA",            s("xA"),                   stats.get("xA"),           20,  primary),
        ("npxG",          s("npxG"),                 stats.get("npxG"),         25,  primary),
        ("Key Passes",    s("key_passes", ".0f"),    stats.get("key_passes"),   100, primary),
        ("Prog Passes",   s("prog_passes", ".0f"),   stats.get("prog_passes"),  200, primary),
        ("Pass Cmp%",     s("pass_cmp_pct", ".1f"),  stats.get("pass_cmp_pct"), 100, primary),
        ("Tackles",       s("tackles", ".0f"),       stats.get("tackles"),      100, primary),
        ("Interceptions", s("interceptions", ".0f"), stats.get("interceptions"), 60, primary),
        ("Pressures",     s("pressures", ".0f"),     stats.get("pressures"),    400, primary),
        ("Dribbles",      s("dribbles", ".0f"),      stats.get("dribbles"),      80, primary),
    ]
    # Only render blocks where data is actually available
    BLOCKS = [(lbl, val, bv, bm, bc) for (lbl, val, bv, bm, bc) in ALL_BLOCKS if val != "—"]

    n_cols = 3
    n_rows = max(1, -(-len(BLOCKS) // n_cols))  # ceiling division

    ax_cards = fig.add_axes([0, 0.18, 1, 0.66])
    ax_cards.set_facecolor(BG); ax_cards.axis("off")
    ax_cards.set_xlim(0, 1); ax_cards.set_ylim(0, 1)

    pad = 0.012
    card_h_norm = 1 / n_rows - pad * 2
    card_w_norm = 1 / n_cols - pad * 2

    for idx, (label, val_str, bar_val, bar_max, bar_col) in enumerate(BLOCKS):
        row = idx // n_cols
        col = idx % n_cols
        x0 = col * (1 / n_cols) + pad
        y0 = 1 - (row + 1) * (1 / n_rows) + pad

        # Card background
        ax_cards.add_patch(mpatches.FancyBboxPatch(
            (x0, y0), card_w_norm, card_h_norm,
            boxstyle="round,pad=0.01", facecolor=BG_CARD, edgecolor="#1F2937", lw=0.8))

        cx = x0 + card_w_norm / 2
        # Stat value
        ax_cards.text(cx, y0 + card_h_norm * 0.72, val_str,
                      fontsize=18, fontproperties=font, color=primary,
                      fontweight="bold", ha="center", va="center")
        # Label
        ax_cards.text(cx, y0 + card_h_norm * 0.40, label,
                      fontsize=8, fontproperties=font, color=TEXT_SUB,
                      ha="center", va="center")
        # Mini bar
        bar_rect = (x0 + 0.01, y0 + 0.01, card_w_norm - 0.02, 0.018)
        try:
            bv = float(bar_val) if bar_val else 0
        except (TypeError, ValueError):
            bv = 0
        pct_bar(ax_cards, bar_rect, bv, bar_max, bar_col)

    # ── Appearances / Minutes row ──────────────────────────────────────────────
    ax_meta = fig.add_axes([0, 0.09, 1, 0.09])
    ax_meta.set_facecolor(BG); ax_meta.axis("off")
    ax_meta.set_xlim(0, 1); ax_meta.set_ylim(0, 1)

    apps    = s("apps", ".0f")
    minutes = s("minutes", ".0f")
    mins_90 = f"{float(stats.get('minutes', 0)) / 90:.1f}" if stats.get("minutes") else "—"

    for xp, lbl, val in [
        (0.17, "Appearances",  apps),
        (0.50, "Minutes",      minutes),
        (0.83, "90s Played",   mins_90),
    ]:
        ax_meta.text(xp, 0.80, lbl, fontsize=9, color=TEXT_SUB, ha="center",
                     fontproperties=font, va="top")
        ax_meta.text(xp, 0.28, val, fontsize=16, color=primary, ha="center",
                     fontproperties=font, fontweight="bold", va="top")

    # ── Footer ─────────────────────────────────────────────────────────────────
    ax_foot = fig.add_axes([0, 0, 1, 0.07])
    ax_foot.set_facecolor(BG); ax_foot.axis("off")
    ax_foot.text(0.5, 0.5, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="center",
                 fontproperties=font)

    return fig_to_png(fig, dpi=150)
