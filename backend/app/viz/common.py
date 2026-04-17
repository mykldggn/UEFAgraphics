"""
Shared pitch drawing, colour palette, font helpers, and PNG serialisation.
All viz modules import from here.
"""
from __future__ import annotations

import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from matplotlib.figure import Figure
from mplsoccer import Pitch, VerticalPitch

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#0C0D0E"
BG_CARD  = "#12151C"
TEXT     = "#FFFFFF"
TEXT_SUB = "#9CA3AF"
ACCENT   = "#3B82F6"   # blue
GREEN    = "#22C55E"
RED      = "#EF4444"
AMBER    = "#F59E0B"

# ── Team colour registry (Understat names + common variants) ──────────────────
TEAM_COLORS: dict[str, str] = {
    # England
    "Arsenal": "#EF0107", "Bournemouth": "#DA291C", "Brentford": "#E30613",
    "Brighton": "#0057B8", "Burnley": "#8B1A4A", "Chelsea": "#2A5FBF",
    "Crystal Palace": "#1B458F", "Everton": "#3A5FCC", "Fulham": "#CC0000",
    "Ipswich": "#3A64A3", "Leicester": "#3060C0", "Liverpool": "#C8102E",
    "Luton": "#F78F1E", "Man City": "#6CABDD", "Manchester City": "#6CABDD",
    "Man United": "#DA291C", "Manchester United": "#DA291C",
    "Newcastle": "#41B6E6", "Nottm Forest": "#DD0000", "Nottingham Forest": "#DD0000",
    "Sheffield United": "#EE2737", "Southampton": "#D71920",
    "Tottenham": "#8AABCC", "West Ham": "#7A263A",
    "Wolves": "#FDB913", "Wolverhampton": "#FDB913",
    "Aston Villa": "#95BFE5", "Leeds": "#FFCD00", "Watford": "#FBEE23",
    # Championship / lower
    "Middlesbrough": "#E00000", "Sunderland": "#EB172B",
    # Spain
    "Real Madrid": "#FFFFFF", "Barcelona": "#A50044", "Atletico Madrid": "#CB3524",
    "Sevilla": "#D4021D", "Valencia": "#F7A21B", "Athletic Club": "#EE2523",
    "Real Sociedad": "#0057A8", "Real Betis": "#00954C", "Villarreal": "#FFE135",
    # Germany
    "Bayern Munich": "#DC052D", "Borussia Dortmund": "#FDE100",
    "RB Leipzig": "#DD0741", "Bayer Leverkusen": "#E32221",
    "Borussia M'gladbach": "#009A44", "Eintracht Frankfurt": "#E1000F",
    "Wolfsburg": "#009E4E", "Schalke": "#004D9D",
    # Italy
    "Juventus": "#000000", "Inter": "#010E80", "AC Milan": "#FB090B",
    "Napoli": "#087DC2", "Roma": "#9B1E1E", "Lazio": "#87CEEB",
    "Atalanta": "#1C78BF", "Fiorentina": "#5B2D8E",
    # France
    "PSG": "#004170", "Paris Saint-Germain": "#004170",
    "Marseille": "#00AFDB", "Lyon": "#0033A0", "Monaco": "#DA020E",
    "Lille": "#DD1A22", "Rennes": "#E02020",
    # Portugal
    "Benfica": "#E2001A", "Porto": "#003DA5", "Sporting CP": "#005E2F",
    # Netherlands
    "Ajax": "#CB1215", "PSV": "#CC0000", "Feyenoord": "#C8102E",
    # Scotland
    "Celtic": "#16A34A", "Rangers": "#003B99",
    # Default
    "_default": ACCENT,
}


def team_color(name: str) -> str:
    return TEAM_COLORS.get(name, TEAM_COLORS["_default"])


# ── Font helpers ──────────────────────────────────────────────────────────────
_font_cache: dict[str, fm.FontProperties] = {}

def get_font(path: str | None = None) -> fm.FontProperties:
    key = path or "__default__"
    if key not in _font_cache:
        if path and Path(path).exists():
            _font_cache[key] = fm.FontProperties(fname=path)
        else:
            _font_cache[key] = fm.FontProperties(family="DejaVu Sans")
    return _font_cache[key]


# ── PNG serialisation ─────────────────────────────────────────────────────────
def fig_to_png(fig: Figure, dpi: int = 150) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data


# ── Shared pitch factories ────────────────────────────────────────────────────
def make_pitch(pitch_type: str = "opta", orientation: str = "horizontal",
               half: bool = False) -> Pitch | VerticalPitch:
    kwargs = dict(
        pitch_type=pitch_type,
        pitch_color=BG,
        line_color="#4B5563",
        linewidth=0.9,
        goal_type="box",
        half=half,
    )
    if orientation == "vertical":
        return VerticalPitch(**kwargs)
    return Pitch(**kwargs)


# ── Shared stat annotation helper ─────────────────────────────────────────────
def stat_row(ax, x: float, y: float, label: str, value: str,
             font: fm.FontProperties, label_size: int = 10, value_size: int = 14,
             value_color: str = TEXT, label_color: str = TEXT_SUB):
    ax.text(x, y + 0.015, label, fontsize=label_size, fontproperties=font,
            color=label_color, ha="center", va="bottom", transform=ax.transAxes)
    ax.text(x, y - 0.01, value, fontsize=value_size, fontproperties=font,
            color=value_color, ha="center", va="top", fontweight="bold",
            transform=ax.transAxes)
