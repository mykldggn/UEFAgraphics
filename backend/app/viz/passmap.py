"""
Pass Map infographic.
Shows pass start/end positions on pitch with progressive pass highlighting,
plus summary analytics (completion %, progressive %, key passes).

Expects a DataFrame with columns:
  x, y          — start position (0-100 Opta scale)
  end_x, end_y  — end position (0-100 Opta scale)
  progressive   — bool / 0-1 (pass is progressive)
  key_pass      — bool / 0-1 (pass leads to shot)
  complete      — bool / 0-1 (pass completed)
  distance      — float (metres, optional, computed if missing)
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from mplsoccer import Pitch

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)

# Pitch is 105m × 68m; Opta coords 0-100 each axis
_PITCH_LENGTH_M = 105.0
_PITCH_WIDTH_M  = 68.0

# Progressive pass: end is at least 25% closer to opponent goal than start
#  (simplified — FBref uses 32m/10m thresholds; here we use proportional)
_PROG_THRESHOLD = 0.25


def _is_progressive(row: pd.Series) -> bool:
    """Return True if pass advances the ball meaningfully toward goal."""
    sx, ex = row["x"], row.get("end_x", np.nan)
    if np.isnan(sx) or np.isnan(ex):
        return False
    dist_from_goal_start = 100 - sx
    dist_from_goal_end   = 100 - ex
    if dist_from_goal_start == 0:
        return False
    return (dist_from_goal_start - dist_from_goal_end) / dist_from_goal_start >= _PROG_THRESHOLD


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Ensure bool columns exist
    if "complete" not in df.columns:
        df["complete"] = 1
    if "progressive" not in df.columns:
        df["progressive"] = df.apply(_is_progressive, axis=1).astype(int)
    if "key_pass" not in df.columns:
        df["key_pass"] = 0
    if "distance" not in df.columns and "end_x" in df.columns:
        dx = (df["end_x"] - df["x"]) / 100 * _PITCH_LENGTH_M
        dy = (df["end_y"] - df["y"]) / 100 * _PITCH_WIDTH_M
        df["distance"] = np.sqrt(dx**2 + dy**2)
    for col in ("complete", "progressive", "key_pass"):
        df[col] = df[col].fillna(0).astype(int)
    return df


def render(
    df: pd.DataFrame,
    player_name: str,
    season_label: str,
    team: str = "",
) -> bytes:
    font    = get_font()
    primary = team_color(team)

    if df.empty:
        return _no_data_png(player_name, season_label, font)

    df = _enrich(df)
    required = {"x", "y", "end_x", "end_y"}
    if not required.issubset(df.columns):
        return _no_data_png(player_name, season_label, font)

    total      = len(df)
    completed  = int(df["complete"].sum())
    cmp_pct    = completed / total * 100 if total else 0
    prog       = df[df["progressive"] == 1]
    key        = df[df["key_pass"] == 1]
    prog_pct   = len(prog) / total * 100 if total else 0
    avg_dist   = float(df["distance"].mean()) if "distance" in df.columns else 0.0

    fig = plt.figure(figsize=(10, 11), facecolor=BG)

    # ── Title ──────────────────────────────────────────────────────────────────
    ax_title = fig.add_axes([0, 0.90, 1, 0.10])
    ax_title.set_facecolor(BG); ax_title.axis("off")
    ax_title.text(0.5, 0.85, player_name, fontsize=20, fontproperties=font,
                  color=TEXT, ha="center", va="top", fontweight="bold")
    ax_title.text(0.5, 0.42, season_label, fontsize=11, fontproperties=font,
                  color=primary, ha="center", va="top")

    # ── Pitch ──────────────────────────────────────────────────────────────────
    pitch = Pitch(
        pitch_type="opta",
        pitch_color=BG,
        line_color="#4B5563",
        linewidth=0.9,
        goal_type="box",
    )
    ax_pitch = fig.add_axes([0.04, 0.22, 0.92, 0.68])
    pitch.draw(ax=ax_pitch)

    # All completed passes (thin, muted)
    completed_df = df[df["complete"] == 1]
    incomplete_df = df[df["complete"] == 0]

    for _, p in completed_df.iterrows():
        ax_pitch.annotate(
            "", xy=(p["end_x"], p["end_y"]), xytext=(p["x"], p["y"]),
            arrowprops=dict(
                arrowstyle="-|>", color="#4B5563", lw=0.5,
                mutation_scale=5, alpha=0.45
            ),
            zorder=2,
        )

    for _, p in incomplete_df.iterrows():
        ax_pitch.plot([p["x"], p["end_x"]], [p["y"], p["end_y"]],
                      color=RED, lw=0.6, alpha=0.5, zorder=2)

    # Progressive passes (highlighted)
    for _, p in prog.iterrows():
        ax_pitch.annotate(
            "", xy=(p["end_x"], p["end_y"]), xytext=(p["x"], p["y"]),
            arrowprops=dict(
                arrowstyle="-|>", color=ACCENT, lw=1.2,
                mutation_scale=8, alpha=0.85
            ),
            zorder=3,
        )

    # Key passes (star at end)
    for _, p in key.iterrows():
        ax_pitch.scatter(p["end_x"], p["end_y"], s=80, color=AMBER,
                         marker="*", zorder=5, edgecolors=BG, lw=0.4)

    # Start dots
    ax_pitch.scatter(df["x"], df["y"], s=15, color=TEXT_SUB,
                     alpha=0.5, zorder=4, edgecolors="none")

    # ── Legend ─────────────────────────────────────────────────────────────────
    ax_leg = fig.add_axes([0.04, 0.17, 0.92, 0.04])
    ax_leg.set_facecolor(BG); ax_leg.axis("off")
    ax_leg.set_xlim(0, 1); ax_leg.set_ylim(0, 1)
    items = [
        ("#4B5563", "Completed"),
        (RED,       "Incomplete"),
        (ACCENT,    "Progressive"),
        (AMBER,     "Key Pass"),
    ]
    for xi, (col, lbl) in enumerate(items):
        px = 0.10 + xi * 0.22
        ax_leg.plot([px - 0.03, px + 0.00], [0.5, 0.5], color=col, lw=2)
        if lbl == "Key Pass":
            ax_leg.scatter(px - 0.015, 0.5, s=50, color=AMBER, marker="*")
        ax_leg.text(px + 0.02, 0.5, lbl, fontsize=8, color=TEXT_SUB,
                    fontproperties=font, va="center")

    # ── Stats bar ──────────────────────────────────────────────────────────────
    ax_stats = fig.add_axes([0, 0.07, 1, 0.09])
    ax_stats.set_facecolor(BG); ax_stats.axis("off")
    ax_stats.set_xlim(0, 1); ax_stats.set_ylim(0, 1)

    for xp, lbl, val in [
        (0.12, "Passes",      str(total)),
        (0.33, "Cmp%",        f"{cmp_pct:.1f}%"),
        (0.54, "Progressive", f"{len(prog)} ({prog_pct:.0f}%)"),
        (0.75, "Key Passes",  str(len(key))),
        (0.92, "Avg Dist",    f"{avg_dist:.1f}m"),
    ]:
        ax_stats.text(xp, 0.82, lbl, fontsize=9, color=TEXT_SUB, ha="center",
                      fontproperties=font, va="top")
        ax_stats.text(xp, 0.32, val, fontsize=13, color=primary, ha="center",
                      fontproperties=font, fontweight="bold", va="top")

    # ── Footer ─────────────────────────────────────────────────────────────────
    ax_foot = fig.add_axes([0, 0, 1, 0.06])
    ax_foot.set_facecolor(BG); ax_foot.axis("off")
    ax_foot.text(0.5, 0.5, "Data: FBref  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="center",
                 fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(player_name: str, season_label: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=BG)
    ax.set_facecolor(BG); ax.axis("off")
    ax.text(0.5, 0.6, player_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, f"No pass data for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
