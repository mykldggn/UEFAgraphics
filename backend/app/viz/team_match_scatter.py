"""Per-match xG scatter — result-coloured dots on an xG-for vs xGA-against plane."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font,
)

_RESULT_COLORS = {"w": GREEN, "d": AMBER, "l": RED}


def render(
    history: list[dict],
    team_name: str,
    season_label: str,
    primary_color: str | None = None,
) -> bytes:
    font = get_font()

    if not history:
        fig, ax = plt.subplots(figsize=(8, 8), facecolor=BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.55, team_name, color=TEXT, fontsize=18, ha="center",
                va="center", transform=ax.transAxes, fontweight="bold",
                fontproperties=font)
        ax.text(0.5, 0.42, "No match data available", color=TEXT_SUB,
                fontsize=12, ha="center", va="center", transform=ax.transAxes,
                fontproperties=font)
        fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
                 fontsize=8, color="#374151", ha="center", va="bottom",
                 fontproperties=font)
        return fig_to_png(fig, dpi=150)

    xg_vals  = [float(h.get("xG", 0) or 0) for h in history]
    xga_vals = [float(h.get("xGA", 0) or 0) for h in history]
    results  = [str(h.get("result", "")).lower() for h in history]

    wins   = results.count("w")
    draws  = results.count("d")
    losses = results.count("l")
    avg_xg  = np.mean(xg_vals)  if xg_vals  else 0.0
    avg_xga = np.mean(xga_vals) if xga_vals else 0.0

    fig, ax = plt.subplots(figsize=(8, 8), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor("#374151")

    dot_colors = [_RESULT_COLORS.get(r, TEXT_SUB) for r in results]
    ax.scatter(xg_vals, xga_vals, c=dot_colors, s=120,
               edgecolors=BG, lw=1, zorder=4)

    for i, (x, y) in enumerate(zip(xg_vals, xga_vals)):
        ax.text(x, y, str(i + 1), fontsize=6, color=BG,
                ha="center", va="center", zorder=5, fontproperties=font)

    ax_lim_lo = min(min(xg_vals), min(xga_vals)) * 0.85 if xg_vals else 0
    ax_lim_hi = max(max(xg_vals), max(xga_vals)) * 1.15 if xg_vals else 4
    ax_lim_lo = max(ax_lim_lo, 0)

    diag = np.linspace(ax_lim_lo, ax_lim_hi, 100)
    ax.plot(diag, diag, color=TEXT, lw=1.0, ls="--", alpha=0.15, zorder=2)

    ax.axvline(avg_xg,  color=TEXT_SUB, lw=1.2, ls="--", alpha=0.5, zorder=2)
    ax.axhline(avg_xga, color=TEXT_SUB, lw=1.2, ls="--", alpha=0.5, zorder=2)

    mid_x = (ax_lim_lo + ax_lim_hi) / 2
    mid_y = (ax_lim_lo + ax_lim_hi) / 2

    quad_kwargs = dict(fontsize=8, color=TEXT_SUB, alpha=0.5,
                       fontproperties=font, zorder=1)
    ax.text(ax_lim_hi * 0.97, ax_lim_lo + 0.05, "Dominant",
            ha="right", va="bottom", **quad_kwargs)
    ax.text(ax_lim_hi * 0.97, ax_lim_hi * 0.97, "Open Game",
            ha="right", va="top", **quad_kwargs)
    ax.text(ax_lim_lo + 0.02, ax_lim_hi * 0.97, "Struggling",
            ha="left", va="top", **quad_kwargs)
    ax.text(ax_lim_lo + 0.02, ax_lim_lo + 0.05, "Resolute",
            ha="left", va="bottom", **quad_kwargs)

    ax.set_xlabel("xG For", color=TEXT_SUB, fontsize=10,
                  fontproperties=font, labelpad=6)
    ax.set_ylabel("xGA (Against)", color=TEXT_SUB, fontsize=10,
                  fontproperties=font, labelpad=6)
    ax.invert_yaxis()
    ax.tick_params(colors=TEXT_SUB, labelsize=8)
    ax.grid(color="#1F2937", lw=0.6)
    ax.set_xlim(ax_lim_lo, ax_lim_hi)
    ax.set_ylim(ax_lim_hi, ax_lim_lo)

    legend_patches = [
        mpatches.Patch(color=GREEN, label="W"),
        mpatches.Patch(color=AMBER, label="D"),
        mpatches.Patch(color=RED,   label="L"),
    ]
    ax.legend(handles=legend_patches, frameon=False, labelcolor=TEXT,
              prop=font, fontsize=9, loc="upper left")

    summary = (f"W{wins} D{draws} L{losses}  ·  "
               f"Avg xG: {avg_xg:.2f}  |  Avg xGA: {avg_xga:.2f}")
    fig.text(0.5, 0.94, f"{team_name}  ·  {season_label}  ·  Match xG Profile",
             fontsize=13, fontproperties=font, color=TEXT, ha="center",
             va="top", fontweight="bold")
    fig.text(0.5, 0.91, summary, fontsize=9, fontproperties=font,
             color=TEXT_SUB, ha="center", va="top")
    fig.text(0.5, 0.015, "Data: Understat  ·  UEFAgraphics",
             fontsize=8, color="#374151", ha="center", va="bottom",
             fontproperties=font)

    fig.subplots_adjust(left=0.10, right=0.96, top=0.88, bottom=0.08)
    return fig_to_png(fig, dpi=150)
