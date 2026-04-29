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
    "Arsenal": "#EF0107", "Bournemouth": "#C8102E", "Brentford": "#E30613",
    "Brighton": "#0057B8", "Burnley": "#8B1A4A", "Chelsea": "#2A5FBF",
    "Crystal Palace": "#1B458F", "Everton": "#3A5FCC", "Fulham": "#E4CCAA",
    "Ipswich": "#3A64A3", "Leicester": "#3060C0", "Liverpool": "#C8102E",
    "Luton": "#F78F1E", "Man City": "#6CABDD", "Manchester City": "#6CABDD",
    "Man United": "#DA291C", "Manchester United": "#DA291C",
    "Newcastle": "#241F20", "Nottm Forest": "#DD0000", "Nottingham Forest": "#DD0000",
    "Sheffield United": "#EE2737", "Southampton": "#D71920",
    "Tottenham": "#8AABCC", "West Ham": "#7A263A",
    "Wolves": "#FDB913", "Wolverhampton": "#FDB913",
    "Aston Villa": "#95BFE5", "Leeds": "#FFCD00", "Watford": "#FBEE23",
    # Championship / lower
    "Middlesbrough": "#E00000", "Sunderland": "#EB172B",
    # Spain — La Liga
    "Real Madrid": "#FEBE10", "Barcelona": "#A50044", "Atletico Madrid": "#CB3524",
    "Sevilla": "#D4021D", "Valencia": "#F7A21B", "Athletic Club": "#EE2523",
    "Athletic Bilbao": "#EE2523",
    "Real Sociedad": "#0057A8", "Real Betis": "#00954C", "Villarreal": "#FFE135",
    "Getafe": "#004A99", "Getafe CF": "#004A99",
    "Osasuna": "#CC0000", "CA Osasuna": "#CC0000",
    "Rayo Vallecano": "#CC0000",
    "Celta Vigo": "#7EBFDD", "RC Celta": "#7EBFDD",
    "Mallorca": "#CC0000", "RCD Mallorca": "#CC0000",
    "Girona": "#CC0000", "Girona FC": "#CC0000",
    "Las Palmas": "#FFD700", "UD Las Palmas": "#FFD700",
    "Espanyol": "#003DA5", "RCD Espanyol": "#003DA5",
    "Alavés": "#0057B8", "Deportivo Alavés": "#0057B8",
    "Almería": "#CC0000", "UD Almería": "#CC0000",
    "Cádiz": "#FFD700", "Cádiz CF": "#FFD700",
    "Granada": "#CC0000", "Granada CF": "#CC0000",
    "Leganés": "#003DA5", "CD Leganés": "#003DA5",
    "Valladolid": "#6B1F8F", "Real Valladolid": "#6B1F8F",
    # Germany — Bundesliga
    "Bayern Munich": "#DC052D", "FC Bayern München": "#DC052D", "Bayern": "#DC052D",
    "Borussia Dortmund": "#FDE100", "Dortmund": "#FDE100",
    "RB Leipzig": "#DD0741",
    "Bayer Leverkusen": "#E32221", "Leverkusen": "#E32221",
    "Borussia M'gladbach": "#009A44", "Gladbach": "#009A44",
    "Eintracht Frankfurt": "#E1000F", "Frankfurt": "#E1000F",
    "Wolfsburg": "#009E4E", "VfL Wolfsburg": "#009E4E",
    "Schalke": "#004D9D", "FC Schalke 04": "#004D9D",
    "Stuttgart": "#CC0000", "VfB Stuttgart": "#CC0000",
    "Freiburg": "#CC0000", "SC Freiburg": "#CC0000",
    "Hoffenheim": "#1565C0", "TSG Hoffenheim": "#1565C0",
    "Mainz": "#CC0000", "1. FSV Mainz 05": "#CC0000", "Mainz 05": "#CC0000",
    "Augsburg": "#CC0000", "FC Augsburg": "#CC0000",
    "Union Berlin": "#CC0000", "1. FC Union Berlin": "#CC0000",
    "Bochum": "#004FA3", "VfL Bochum": "#004FA3",
    "Cologne": "#CC0000", "FC Köln": "#CC0000", "Köln": "#CC0000",
    "Hertha Berlin": "#004FA3", "Hertha BSC": "#004FA3",
    "Darmstadt": "#005CA9", "SV Darmstadt 98": "#005CA9",
    "Werder Bremen": "#1D9648", "SV Werder Bremen": "#1D9648",
    "Heidenheim": "#CC0000", "1. FC Heidenheim": "#CC0000",
    "Holstein Kiel": "#003DA5",
    "FC St. Pauli": "#7B3F00",
    # Italy — Serie A
    "Juventus": "#000000",
    "Inter": "#010E80", "Internazionale": "#010E80", "FC Internazionale": "#010E80",
    "AC Milan": "#FB090B", "Milan": "#FB090B",
    "Napoli": "#087DC2", "SSC Napoli": "#087DC2",
    "Roma": "#9B1E1E", "AS Roma": "#9B1E1E",
    "Lazio": "#87CEEB", "SS Lazio": "#87CEEB",
    "Atalanta": "#1C78BF",
    "Fiorentina": "#5B2D8E", "ACF Fiorentina": "#5B2D8E",
    "Torino": "#8B0000", "Torino FC": "#8B0000",
    "Bologna": "#CC0000", "Bologna FC": "#CC0000",
    "Udinese": "#000000", "Udinese Calcio": "#000000",
    "Sassuolo": "#008C45", "US Sassuolo": "#008C45",
    "Empoli": "#004FA3", "Empoli FC": "#004FA3",
    "Lecce": "#FFD700", "US Lecce": "#FFD700",
    "Monza": "#CC0000", "AC Monza": "#CC0000",
    "Verona": "#FFD700", "Hellas Verona": "#FFD700",
    "Salernitana": "#8B0000", "US Salernitana": "#8B0000",
    "Cagliari": "#CC0000", "Cagliari Calcio": "#CC0000",
    "Genoa": "#CC0000", "Genoa CFC": "#CC0000",
    "Frosinone": "#FFD700", "Frosinone Calcio": "#FFD700",
    "Como": "#004FA3", "Como 1907": "#004FA3",
    "Parma": "#FFD700", "Parma Calcio": "#FFD700",
    "Venezia": "#1C4F9C", "Venezia FC": "#1C4F9C",
    "Sampdoria": "#003DA5", "UC Sampdoria": "#003DA5",
    # France — Ligue 1
    "PSG": "#004170", "Paris Saint-Germain": "#004170",
    "Marseille": "#00AFDB", "Olympique de Marseille": "#00AFDB",
    "Lyon": "#0033A0", "Olympique Lyonnais": "#0033A0",
    "Monaco": "#DA020E", "AS Monaco": "#DA020E",
    "Lille": "#DD1A22", "LOSC Lille": "#DD1A22",
    "Rennes": "#E02020", "Stade Rennais": "#E02020",
    "Nice": "#000000", "OGC Nice": "#000000",
    "Lens": "#E03A1A", "RC Lens": "#E03A1A",
    "Strasbourg": "#00529F", "RC Strasbourg": "#00529F",
    "Nantes": "#FBCC20", "FC Nantes": "#FBCC20",
    "Reims": "#DB0039", "Stade de Reims": "#DB0039",
    "Brest": "#E30613", "Stade Brestois": "#E30613",
    "Toulouse": "#6236FF", "FC Toulouse": "#6236FF",
    "Montpellier": "#E87722", "Montpellier HSC": "#E87722",
    "Le Havre": "#003F8F", "HAC Le Havre": "#003F8F",
    "Saint-Étienne": "#2E7D32", "AS Saint-Étienne": "#2E7D32",
    "Angers": "#000000", "SCO Angers": "#000000",
    "Auxerre": "#DC002B", "AJ Auxerre": "#DC002B",
    "Metz": "#7A0024", "FC Metz": "#7A0024",
    "Lorient": "#E2621B", "FC Lorient": "#E2621B",
    "Clermont": "#E4002B", "Clermont Foot": "#E4002B",
    # Portugal
    "Benfica": "#E2001A", "SL Benfica": "#E2001A",
    "Porto": "#003DA5", "FC Porto": "#003DA5",
    "Sporting CP": "#005E2F", "Sporting": "#005E2F",
    "Braga": "#C8102E", "SC Braga": "#C8102E",
    "Guimarães": "#1E4E98", "Vitória SC": "#1E4E98",
    # Netherlands
    "Ajax": "#CB1215", "AFC Ajax": "#CB1215",
    "PSV": "#CC0000", "PSV Eindhoven": "#CC0000",
    "Feyenoord": "#C8102E",
    "AZ": "#CC0000", "AZ Alkmaar": "#CC0000",
    "Utrecht": "#FFC200", "FC Utrecht": "#FFC200",
    "Twente": "#E30613", "FC Twente": "#E30613",
    # Scotland
    "Celtic": "#16A34A", "Rangers": "#003B99",
    "Aberdeen": "#CF0A2C", "Hearts": "#A50024", "Heart of Midlothian": "#A50024",
    "Hibernian": "#007B40",
    # Belgium
    "Club Brugge": "#1B3F87", "Anderlecht": "#7C0082", "RSC Anderlecht": "#7C0082",
    "Genk": "#1B4F92", "KRC Genk": "#1B4F92",
    "Gent": "#1B4B82", "KAA Gent": "#1B4B82",
    # Turkey
    "Galatasaray": "#E30A17", "Fenerbahçe": "#004B96",
    "Beşiktaş": "#000000", "Trabzonspor": "#990000",
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
