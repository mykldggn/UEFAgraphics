"""
Team Average Positions + Formation infographic.
Plots average x/y position per player, infers formation,
and adds a short style-of-play summary.

Expects a DataFrame with columns:
  player, x, y (0-100 Opta), position (GK/DF/MF/FW), minutes
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from mplsoccer import Pitch

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN,
    fig_to_png, get_font, team_color,
)

_ROLE_COLORS = {
    "GK": "#F59E0B",
    "DF": "#3B82F6",
    "MF": "#22C55E",
    "FW": "#EF4444",
}
_ROLE_ORDER = ["GK", "DF", "MF", "FW"]


def _infer_formation(pos_df: pd.DataFrame) -> str:
    """Rough formation string from position counts (GK excluded from string)."""
    counts = pos_df[pos_df["role"] != "GK"]["role"].value_counts()
    # Order: DF → MF → FW
    parts = []
    for role in ["DF", "MF", "FW"]:
        n = counts.get(role, 0)
        if n:
            parts.append(str(n))
    return "-".join(parts) if parts else "?"


def _style_summary(
    avg_width: float,
    avg_depth: float,
    xg_per_game: float | None = None,
    xga_per_game: float | None = None,
) -> str:
    """Return a one-line style description based on spatial metrics."""
    lines = []
    if avg_depth > 60:
        lines.append("High-pressing, compact shape")
    elif avg_depth < 45:
        lines.append("Deep defensive block")
    else:
        lines.append("Balanced mid-block")
    if avg_width > 55:
        lines.append("wide attacking width")
    elif avg_width < 40:
        lines.append("narrow / central focus")
    if xg_per_game:
        if xg_per_game > 2.0:
            lines.append("high attacking output")
        elif xg_per_game < 1.0:
            lines.append("low attacking output")
    if xga_per_game:
        if xga_per_game < 1.0:
            lines.append("solid defensively")
        elif xga_per_game > 1.8:
            lines.append("defensively vulnerable")
    return "  ·  ".join(lines).capitalize() + "."


def render(
    df: pd.DataFrame,
    team_name: str,
    season_label: str,
    xg_per_game: float | None = None,
    xga_per_game: float | None = None,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    if df.empty:
        return _no_data_png(team_name, season_label, font)

    df = df.copy()
    for col in ("x", "y"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["x", "y", "player"])

    # Normalise position to role bucket
    def _role(pos: str) -> str:
        pos = str(pos).upper()
        if "GK" in pos:              return "GK"
        if any(p in pos for p in ["CB", "LB", "RB", "WB", "DF"]): return "DF"
        if any(p in pos for p in ["CM", "DM", "AM", "MF"]):        return "MF"
        return "FW"

    df["role"] = df["position"].apply(_role) if "position" in df.columns else "MF"

    formation   = _infer_formation(df)
    avg_width   = float(df["y"].std() * 2)   # proxy for width spread
    avg_depth   = float(df["x"].mean())
    style_text  = _style_summary(avg_width, avg_depth, xg_per_game, xga_per_game)

    # ── Figure ─────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(9, 11), facecolor=BG)

    # Title
    fig.text(0.5, 0.97, team_name, fontsize=18, fontproperties=font,
             color=TEXT, ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.953, f"{season_label}  ·  Formation {formation}",
             fontsize=11, fontproperties=font, color=TEXT_SUB, ha="center", va="top")

    # Pitch
    pitch = Pitch(
        pitch_type="opta",
        pitch_color=BG,
        line_color="#4B5563",
        linewidth=0.9,
        goal_type="box",
    )
    ax_pitch = fig.add_axes([0.04, 0.16, 0.92, 0.76])
    pitch.draw(ax=ax_pitch)

    for _, row in df.iterrows():
        role  = row["role"]
        color = _ROLE_COLORS.get(role, ACCENT)
        ax_pitch.scatter(
            row["x"], row["y"],
            s=250, color=color, edgecolors=BG, lw=1.5, zorder=5,
        )
        ax_pitch.text(
            row["x"], row["y"] + 3.5,
            str(row["player"]).split()[-1][:10],   # surname
            fontsize=7, color=TEXT, ha="center", fontproperties=font, zorder=6,
        )

    # Convex hull per role (show team shape)
    from scipy.spatial import ConvexHull
    for role in ["DF", "MF", "FW"]:
        sub = df[df["role"] == role][["x", "y"]].values
        if len(sub) >= 3:
            try:
                hull  = ConvexHull(sub)
                hull_pts = np.append(hull.vertices, hull.vertices[0])
                ax_pitch.fill(
                    sub[hull_pts, 0], sub[hull_pts, 1],
                    color=_ROLE_COLORS[role], alpha=0.08, zorder=2,
                )
                ax_pitch.plot(
                    sub[hull_pts, 0], sub[hull_pts, 1],
                    color=_ROLE_COLORS[role], alpha=0.30, lw=1, zorder=3,
                )
            except Exception:
                pass

    # Legend
    legend_items = [
        mpatches.Patch(facecolor=_ROLE_COLORS["GK"], label="GK"),
        mpatches.Patch(facecolor=_ROLE_COLORS["DF"], label="Defenders"),
        mpatches.Patch(facecolor=_ROLE_COLORS["MF"], label="Midfielders"),
        mpatches.Patch(facecolor=_ROLE_COLORS["FW"], label="Forwards"),
    ]
    ax_pitch.legend(handles=legend_items, loc="lower left", frameon=False,
                    labelcolor=TEXT, prop=font, fontsize=8)

    # Style summary
    fig.text(0.5, 0.135, style_text,
             fontsize=9, fontproperties=font, color=TEXT_SUB, ha="center", va="top",
             style="italic")

    # Footer
    fig.text(0.5, 0.015, "Avg positions based on min-weighted centroids  ·  Data: FBref  ·  UEFAgraphics",
             fontsize=7.5, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(team_name: str, season_label: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=BG)
    ax.set_facecolor(BG); ax.axis("off")
    ax.text(0.5, 0.6, team_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, f"No position data for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
