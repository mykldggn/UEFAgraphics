"""
Shot map infographic — ported from EPL_Player_ShotChart notebook.
Works for any player in any Understat-covered league, plus FBref shooting data.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib.patches import Arc
from mplsoccer import VerticalPitch

from app.viz.common import (
    BG, TEXT, TEXT_SUB, ACCENT,
    fig_to_png, get_font, team_color,
)


def render(
    df: pd.DataFrame,
    player_name: str,
    season_label: str,
    color: str | None = None,
) -> bytes:
    """
    df columns expected: X (0-100), Y (0-100), xG, result, team (optional)
    Returns PNG bytes.
    """
    if df.empty:
        return _no_data_png(player_name, season_label)

    primary = color or (team_color(df["team"].iloc[0]) if "team" in df.columns else ACCENT)
    font = get_font()

    total_shots = len(df)
    total_goals = int((df["result"] == "Goal").sum())
    total_xG    = float(df["xG"].sum())
    xg_per_shot = total_xG / total_shots if total_shots else 0

    avg_x = float(df["X"].mean())
    # Average distance in yards (pitch 105m ≈ 114.8yd; Understat X is 0-100 from left)
    # Shooting end is X≈100; distance = (100-X)/100 * 57.5 (half-pitch yards, ~52m)
    avg_dist_yd = (100 - avg_x) / 100 * 57.5

    # ── Layout ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(8, 11), facecolor=BG)

    # Title block
    ax_title = fig.add_axes([0, 0.78, 1, 0.20])
    ax_title.set_facecolor(BG)
    ax_title.set_xlim(0, 1); ax_title.set_ylim(0, 1); ax_title.axis("off")
    ax_title.text(0.5, 0.88, player_name, fontsize=22, fontproperties=font,
                  fontweight="bold", color=TEXT, ha="center")
    ax_title.text(0.5, 0.70, season_label, fontsize=13, fontproperties=font,
                  color=primary, ha="center")

    # Legend row
    for dot_x, dot_s in zip([0.38, 0.43, 0.49, 0.55, 0.61], [60, 130, 220, 330, 460]):
        ax_title.scatter(dot_x, 0.45, s=dot_s, color=BG, edgecolors=TEXT, lw=0.8)
    ax_title.text(0.25, 0.43, "Low xG chance", fontsize=9, color=TEXT_SUB,
                  ha="center", fontproperties=font)
    ax_title.text(0.75, 0.43, "High xG chance", fontsize=9, color=TEXT_SUB,
                  ha="center", fontproperties=font)
    ax_title.scatter(0.47, 0.20, s=120, color=primary, edgecolors=TEXT, lw=0.8, alpha=0.85)
    ax_title.text(0.45, 0.18, "Goal", fontsize=9, color=TEXT, ha="right", fontproperties=font)
    ax_title.scatter(0.53, 0.20, s=120, color=BG, edgecolors=TEXT, lw=0.8)
    ax_title.text(0.55, 0.18, "No Goal", fontsize=9, color=TEXT, ha="left", fontproperties=font)

    # Pitch (vertical half)
    pitch = VerticalPitch(
        pitch_type="opta",
        pitch_color=BG,
        line_color="#4B5563",
        linewidth=0.9,
        goal_type="box",
        half=True,
    )
    ax_pitch = fig.add_axes([0.05, 0.22, 0.90, 0.56])
    pitch.draw(ax=ax_pitch)

    for _, shot in df.iterrows():
        ax_pitch.scatter(
            shot["Y"], shot["X"],
            s=max(40, 300 * float(shot["xG"])),
            color=primary if shot["result"] == "Goal" else BG,
            edgecolors=TEXT,
            linewidth=0.8,
            alpha=0.82,
            zorder=3,
        )

    # Average distance annotation
    ax_pitch.scatter(50, avg_x, s=80, color=TEXT, zorder=5, marker="D")
    ax_pitch.plot([50, 50], [100, avg_x], color=TEXT, lw=1.5, ls="--")
    ax_pitch.text(52, avg_x - 3,
                  f"Avg dist\n{avg_dist_yd:.1f} yds",
                  fontsize=8, color=TEXT, ha="left", fontproperties=font)

    # Stats bar
    ax_stats = fig.add_axes([0, 0.15, 1, 0.06])
    ax_stats.set_facecolor(BG); ax_stats.set_xlim(0, 1); ax_stats.set_ylim(0, 1)
    ax_stats.axis("off")
    for xp, lbl, val in [
        (0.10, "Shots",    str(total_shots)),
        (0.33, "Goals",    str(total_goals)),
        (0.57, "xG",       f"{total_xG:.2f}"),
        (0.79, "xG/Shot",  f"{xg_per_shot:.2f}"),
    ]:
        ax_stats.text(xp, 0.75, lbl, fontsize=10, color=TEXT_SUB, ha="center",
                      fontproperties=font)
        ax_stats.text(xp, 0.15, val, fontsize=16, color=primary, ha="center",
                      fontproperties=font, fontweight="bold")

    # Footer
    ax_foot = fig.add_axes([0, 0, 1, 0.08])
    ax_foot.set_facecolor(BG); ax_foot.axis("off")
    ax_foot.text(0.5, 0.5, "Data: Understat · UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="center",
                 fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(player_name: str, season_label: str) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 4), facecolor=BG)
    ax.set_facecolor(BG); ax.axis("off")
    ax.text(0.5, 0.6, player_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold")
    ax.text(0.5, 0.4, f"No shot data for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes)
    return fig_to_png(fig)
