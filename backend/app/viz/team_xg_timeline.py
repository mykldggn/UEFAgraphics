"""
Team xG / xPts timeline across a season.
Shows per-match xG for/against bars plus cumulative lines.
Uses data from understat_service.get_team_xg_history().
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from app.viz.common import (
    BG, BG_CARD, TEXT, TEXT_SUB, ACCENT, GREEN, RED, AMBER,
    fig_to_png, get_font, team_color,
)

logger = logging.getLogger(__name__)


def _fetch_crest(url: str) -> Optional[np.ndarray]:
    """Download a crest PNG and return it as a numpy RGBA array (or None)."""
    if not url:
        return None
    try:
        from curl_cffi import requests as cffi_requests
        from PIL import Image
        resp = cffi_requests.get(url, timeout=5, impersonate="chrome")
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA").resize((22, 22))
        return np.array(img)
    except Exception as exc:
        logger.debug("crest fetch failed %s: %s", url, exc)
        return None


def render(
    team_name: str,
    season_label: str,
    history: list[dict],
    # Optional per-match enrichment from FotMob
    opponents: list[dict] | None = None,
    # When False (non-top-5 leagues), skip xG lines and show cumulative goals instead
    has_xg: bool = True,
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
    results       = [str(h.get("result", "")).lower() for h in history]
    h_a           = [str(h.get("h_a", "")).upper() for h in history]

    # Opponent enrichment — align by index
    opp_names: list[str] = []
    opp_crests: list[str] = []
    if opponents and len(opponents) == len(history):
        opp_names  = [o.get("name", "")[:3].upper() for o in opponents]
        opp_crests = [o.get("crest_url", "") for o in opponents]
    else:
        opp_names  = [h.get("opponent", "")[:3].upper() for h in history]
        opp_crests = [h.get("opponent_crest", "") for h in history]

    # Pre-fetch crest images (best-effort, non-blocking via list comprehension)
    use_logos = any(opp_crests)
    crest_imgs: list[Optional[np.ndarray]] = []
    if use_logos:
        crest_imgs = [_fetch_crest(u) for u in opp_crests]
        use_logos  = any(img is not None for img in crest_imgs)

    # Per-match bar color by result
    _bar_color = {"w": "#22C55E", "d": "#F59E0B", "l": "#EF4444"}
    bar_colors = [_bar_color.get(r, GREEN) for r in results]

    # Extra bottom margin when showing logos
    bottom_margin = 0.18 if use_logos else 0.10
    fig = plt.figure(figsize=(12, 9), facecolor=BG)

    # ── Title ──────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.975, team_name, fontsize=18, fontproperties=font,
             color=TEXT, ha="center", va="top", fontweight="bold")
    fig.text(0.5, 0.948, f"{season_label}  ·  xG Timeline",
             fontsize=11, fontproperties=font, color=TEXT_SUB, ha="center", va="top")

    xs = np.array(matches)

    # ── Top panel: cumulative xG (or goals when xG unavailable) ───────────────
    ax_cum = fig.add_axes([0.08, 0.51, 0.88, 0.40])
    ax_cum.set_facecolor(BG)
    for sp in ax_cum.spines.values():
        sp.set_edgecolor("#374151")

    if has_xg:
        ax_cum.plot(xs, cum_xg,  color=GREEN, lw=2.2, label="Cumulative xG",  zorder=3)
        ax_cum.plot(xs, cum_xga, color=RED,   lw=2.2, label="Cumulative xGA", zorder=3)
        ax_cum.fill_between(xs, cum_xg, cum_xga,
                            where=np.array(cum_xg) >= np.array(cum_xga),
                            alpha=0.12, color=GREEN, interpolate=True)
        ax_cum.fill_between(xs, cum_xg, cum_xga,
                            where=np.array(cum_xg) < np.array(cum_xga),
                            alpha=0.12, color=RED, interpolate=True)
        ax_cum.scatter(xs, np.cumsum(goals),         s=30, color=GREEN, zorder=5,
                       alpha=0.7, label="Actual Goals")
        ax_cum.scatter(xs, np.cumsum(goals_against),  s=30, color=RED,   zorder=5,
                       alpha=0.7, marker="v", label="Goals Conceded")
        ax_cum.set_ylabel("Cumulative xG", color=TEXT_SUB, fontsize=9, fontproperties=font)
    else:
        # No xG available — show cumulative goals/conceded lines
        cum_g  = np.cumsum(goals)
        cum_ga = np.cumsum(goals_against)
        ax_cum.plot(xs, cum_g,  color=GREEN, lw=2.2, label="Goals Scored",   zorder=3)
        ax_cum.plot(xs, cum_ga, color=RED,   lw=2.2, label="Goals Conceded", zorder=3)
        ax_cum.fill_between(xs, cum_g, cum_ga,
                            where=cum_g >= cum_ga,
                            alpha=0.12, color=GREEN, interpolate=True)
        ax_cum.fill_between(xs, cum_g, cum_ga,
                            where=cum_g < cum_ga,
                            alpha=0.12, color=RED, interpolate=True)
        ax_cum.set_ylabel("Cumulative Goals", color=TEXT_SUB, fontsize=9, fontproperties=font)
        ax_cum.text(0.5, 0.96, "xG data not available for this league",
                    transform=ax_cum.transAxes, fontsize=8, color=TEXT_SUB,
                    ha="center", va="top", fontproperties=font, alpha=0.7)

    ax_cum.tick_params(colors=TEXT_SUB, labelsize=8)
    ax_cum.legend(frameon=False, labelcolor=TEXT, prop=font, fontsize=8,
                  loc="upper left", ncol=2)
    ax_cum.grid(axis="y", color="#1F2937", lw=0.6)
    ax_cum.set_xlim(0.5, max(matches) + 0.5)

    # ── Bottom panel: per-match xG bars ────────────────────────────────────────
    ax_bar = fig.add_axes([0.08, bottom_margin, 0.88, 0.36])
    ax_bar.set_facecolor(BG)
    for sp in ax_bar.spines.values():
        sp.set_edgecolor("#374151")

    bar_w = 0.38
    for i, (xi, xg_v, col) in enumerate(zip(xs, xg_per, bar_colors)):
        ax_bar.bar(xi - bar_w / 2, xg_v, width=bar_w, color=col, alpha=0.85, zorder=3,
                   label="xG For" if i == 0 else "")
    ax_bar.bar(xs + bar_w / 2, xga_per, width=bar_w, color="#6B7280", alpha=0.60,
               label="xG Against", zorder=3)

    # Actual goal annotations on top of bars
    for i, (g, ga) in enumerate(zip(goals, goals_against)):
        ax_bar.text(xs[i] - bar_w / 2, xg_per[i] + 0.04, str(g),
                    ha="center", fontsize=6, color=TEXT, fontproperties=font, fontweight="bold")
        ax_bar.text(xs[i] + bar_w / 2, xga_per[i] + 0.04, str(ga),
                    ha="center", fontsize=6, color=TEXT_SUB, fontproperties=font)

    # X-axis labels — show H/A + crests when available; otherwise use opponent abbrevs.
    n    = len(matches)
    step = 1 if n <= 20 or use_logos else 2
    tick_idx = list(range(0, n, step))
    ax_bar.set_xticks([xs[i] for i in tick_idx])

    if use_logos:
        labels = [
            (
                h_a[i]
                if i < len(crest_imgs) and crest_imgs[i] is not None
                else f"{h_a[i]}\n{opp_names[i]}" if i < len(opp_names) else h_a[i]
            )
            for i in tick_idx
        ]
    elif opp_names:
        labels = [
            f"{h_a[i]}\n{opp_names[i]}" if i < len(opp_names) else h_a[i]
            for i in tick_idx
        ]
    else:
        labels = [h_a[i] if i < len(h_a) else "" for i in tick_idx]

    ax_bar.set_xticklabels(labels, fontsize=6.5, color=TEXT_SUB,
                           fontproperties=font, linespacing=1.4)
    ax_bar.tick_params(colors=TEXT_SUB, labelsize=7, length=0)
    ax_bar.set_ylabel("Per Match", color=TEXT_SUB, fontsize=9, fontproperties=font)

    # Custom legend
    from matplotlib.patches import Patch
    if has_xg:
        legend_els = [
            Patch(facecolor="#22C55E", alpha=0.85, label="W · xG For"),
            Patch(facecolor="#F59E0B", alpha=0.85, label="D · xG For"),
            Patch(facecolor="#EF4444", alpha=0.85, label="L · xG For"),
            Patch(facecolor="#6B7280", alpha=0.60, label="xG Against"),
        ]
    else:
        legend_els = [
            Patch(facecolor="#22C55E", alpha=0.85, label="W · Goals Scored"),
            Patch(facecolor="#F59E0B", alpha=0.85, label="D · Goals Scored"),
            Patch(facecolor="#EF4444", alpha=0.85, label="L · Goals Scored"),
            Patch(facecolor="#6B7280", alpha=0.60, label="Goals Conceded"),
        ]
    ax_bar.legend(handles=legend_els, frameon=False, labelcolor=TEXT, prop=font,
                  fontsize=7, ncol=4, loc="upper right")
    ax_bar.grid(axis="y", color="#1F2937", lw=0.6)
    ax_bar.set_xlim(0.5, max(matches) + 0.5)

    # ── Opponent crest logos below x-axis ──────────────────────────────────────
    if use_logos and crest_imgs:
        from matplotlib.offsetbox import OffsetImage, AnnotationBbox
        for i, img_arr in enumerate(crest_imgs):
            if img_arr is None or i not in tick_idx:
                continue
            oi = OffsetImage(img_arr, zoom=0.58)
            oi.image.axes = ax_bar
            ab = AnnotationBbox(
                oi,
                (xs[i], 0),
                xybox=(0, -24),
                xycoords=("data", "axes fraction"),
                boxcoords="offset points",
                frameon=False,
                pad=0,
                annotation_clip=False,
            )
            ab.set_clip_on(False)
            ax_bar.add_artist(ab)

    # ── Season summary footer ──────────────────────────────────────────────────
    total_xg  = cum_xg[-1]
    total_xga = cum_xga[-1]
    total_g   = sum(goals)
    total_ga  = sum(goals_against)

    if has_xg:
        footer = (f"xG: {total_xg:.1f}   xGA: {total_xga:.1f}   "
                  f"Goals: {total_g}   Goals Against: {total_ga}"
                  f"   Data: Understat  ·  UEFAgraphics")
    else:
        wins  = sum(1 for r in results if r.lower() == "w")
        draws = sum(1 for r in results if r.lower() == "d")
        losses = sum(1 for r in results if r.lower() == "l")
        footer = (f"W {wins}  D {draws}  L {losses}   "
                  f"Goals: {total_g}   Goals Against: {total_ga}   GD: {total_g - total_ga:+d}"
                  f"   Data: football-data.org  ·  UEFAgraphics")

    fig.text(0.5, 0.015, footer,
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
