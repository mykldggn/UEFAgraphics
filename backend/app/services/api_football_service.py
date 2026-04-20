"""
API-Football (api-sports.io) data layer.
Replaces soccerdata/FBref for league tables, team lists, and player stats.
Free tier: 100 req/day — all responses are aggressively cached.

Sign up at https://api-sports.io to get a free API key.
Set API_FOOTBALL_KEY in your .env file.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import settings
from app.core import cache

logger = logging.getLogger(__name__)

API_BASE = "https://v3.football.api-sports.io"

# ── League ID mapping: our internal ID → API-Football league ID ───────────────
LEAGUE_IDS: dict[str, int] = {
    "ENG-1":    39,   # Premier League
    "ENG-2":    40,   # Championship
    "ENG-3":    41,   # League One
    "ENG-4":    42,   # League Two
    "ESP-1":    140,  # La Liga
    "DEU-1":    78,   # Bundesliga
    "ITA-1":    135,  # Serie A
    "FRA-1":    61,   # Ligue 1
    "NED-1":    88,   # Eredivisie
    "PRT-1":    94,   # Primeira Liga
    "BEL-1":    144,  # First Division A
    "SCO-1":    179,  # Scottish Premiership
    "TUR-1":    203,  # Süper Lig
    "GRC-1":    197,  # Super League Greece
    "AUT-1":    218,  # Austrian Bundesliga
    "CHE-1":    207,  # Super League Switzerland
    "UEFA-CL":  2,    # Champions League
    "UEFA-EL":  3,    # Europa League
    "UEFA-ECL": 848,  # Conference League
}

LEAGUE_LABELS: dict[str, str] = {
    "ENG-1": "Premier League",   "ENG-2": "Championship",
    "ENG-3": "League One",       "ENG-4": "League Two",
    "ESP-1": "La Liga",          "DEU-1": "Bundesliga",
    "ITA-1": "Serie A",          "FRA-1": "Ligue 1",
    "NED-1": "Eredivisie",       "PRT-1": "Primeira Liga",
    "BEL-1": "First Division A", "SCO-1": "Scottish Premiership",
    "TUR-1": "Süper Lig",        "GRC-1": "Super League Greece",
    "AUT-1": "Austrian Bundesliga", "CHE-1": "Super League Switzerland",
    "UEFA-CL": "Champions League",  "UEFA-EL": "Europa League",
    "UEFA-ECL": "Conference League",
    # International (no API-Football ID — Understat-only)
    "INT-EUROS": "European Championship", "INT-WC": "World Cup",
    "INT-NL": "UEFA Nations League",      "INT-AFCON": "AFCON",
    "INT-COPA": "Copa América",
}

LEAGUE_COUNTRY: dict[str, str] = {
    "ENG-1": "England", "ENG-2": "England", "ENG-3": "England", "ENG-4": "England",
    "ESP-1": "Spain",   "DEU-1": "Germany", "ITA-1": "Italy",   "FRA-1": "France",
    "NED-1": "Netherlands", "PRT-1": "Portugal", "BEL-1": "Belgium",
    "SCO-1": "Scotland",    "TUR-1": "Turkey",   "GRC-1": "Greece",
    "AUT-1": "Austria",     "CHE-1": "Switzerland",
    "UEFA-CL": "Europe",    "UEFA-EL": "Europe",  "UEFA-ECL": "Europe",
    "INT-EUROS": "International", "INT-WC": "International",
    "INT-NL": "International",    "INT-AFCON": "International",
    "INT-COPA": "International",
}


def _headers() -> dict[str, str]:
    return {"x-apisports-key": settings.API_FOOTBALL_KEY}


def _get(endpoint: str, params: dict[str, Any]) -> dict | None:
    """Make a GET request, return parsed JSON or None on failure."""
    if not settings.API_FOOTBALL_KEY:
        logger.warning("API_FOOTBALL_KEY not set — skipping API-Football request")
        return None
    try:
        resp = requests.get(
            f"{API_BASE}/{endpoint.lstrip('/')}",
            headers=_headers(),
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors", {})
        if errors:
            logger.error(f"API-Football errors for {endpoint}: {errors}")
            return None
        return data
    except Exception as exc:
        logger.error(f"API-Football {endpoint}: {exc}")
        return None


# ── Teams ─────────────────────────────────────────────────────────────────────

def get_teams(league_id: str, season: int) -> list[dict]:
    key = {"src": "apifootball", "league": league_id, "season": season}
    cached = cache.json_get("teams", key, ttl_hours=48)
    if cached is not None:
        return cached

    api_id = LEAGUE_IDS.get(league_id)
    if not api_id:
        return []

    data = _get("teams", {"league": api_id, "season": season})
    if not data:
        return []

    teams = [
        {"id": str(t["team"]["id"]), "name": t["team"]["name"]}
        for t in data.get("response", [])
    ]
    cache.json_save("teams", key, teams)
    return teams


# ── League table / standings ──────────────────────────────────────────────────

def get_league_table(league_id: str, season: int) -> list[dict]:
    """Return standings as a list of dicts, sorted by rank."""
    key = {"src": "apifootball", "league": league_id, "season": season, "type": "standings"}
    cached = cache.json_get("standings", key, ttl_hours=6)
    if cached is not None:
        return cached

    api_id = LEAGUE_IDS.get(league_id)
    if not api_id:
        return []

    data = _get("standings", {"league": api_id, "season": season})
    if not data:
        return []

    try:
        standings_groups = data["response"][0]["league"]["standings"]
        # standings_groups is a list of groups (e.g. group stage has multiple)
        standings = standings_groups[0]
    except (KeyError, IndexError):
        return []

    rows = []
    for entry in standings:
        all_stats = entry.get("all", {})
        goals     = all_stats.get("goals", {})
        rows.append({
            "rank":           entry.get("rank"),
            "team":           entry.get("team", {}).get("name", ""),
            "team_id":        str(entry.get("team", {}).get("id", "")),
            "played":         all_stats.get("played", 0),
            "wins":           all_stats.get("win", 0),
            "draws":          all_stats.get("draw", 0),
            "losses":         all_stats.get("lose", 0),
            "goals_for":      goals.get("for", 0),
            "goals_against":  goals.get("against", 0),
            "goal_diff":      entry.get("goalsDiff", 0),
            "points":         entry.get("points", 0),
            "form":           entry.get("form", ""),
        })

    cache.json_save("standings", key, rows)
    return rows


# ── Player search ─────────────────────────────────────────────────────────────

def search_players(query: str, league_id: str, season: int) -> list[dict]:
    key = {"src": "apifootball", "q": query.lower(), "league": league_id, "season": season}
    cached = cache.json_get("player_search", key, ttl_hours=24)
    if cached is not None:
        return cached

    api_id = LEAGUE_IDS.get(league_id)
    if not api_id:
        return []

    data = _get("players", {"search": query, "league": api_id, "season": season})
    if not data:
        return []

    results = []
    for item in data.get("response", [])[:20]:
        p    = item.get("player", {})
        stat = (item.get("statistics") or [{}])[0]
        results.append({
            "id":   str(p.get("id", "")),
            "name": p.get("name", ""),
            "team": stat.get("team", {}).get("name", ""),
            "pos":  stat.get("games", {}).get("position", ""),
        })

    cache.json_save("player_search", key, results)
    return results


# ── Player season stats ───────────────────────────────────────────────────────

def get_player_stats(player_id: str, season: int) -> dict | None:
    """Return raw API-Football stats dict for one player+season."""
    key = {"src": "apifootball", "player_id": player_id, "season": season}
    cached = cache.json_get("player_stats", key, ttl_hours=12)
    if cached is not None:
        return cached

    data = _get("players", {"id": player_id, "season": season})
    if not data or not data.get("response"):
        return None

    item = data["response"][0]
    stats = _flatten_player_stats(item)
    cache.json_save("player_stats", key, stats)
    return stats


def get_league_player_stats(league_id: str, season: int) -> list[dict]:
    """
    Fetch all player stats for a league+season (paginated).
    Cached aggressively — this costs ~5-20 API calls.
    """
    key = {"src": "apifootball", "league": league_id, "season": season, "type": "all_players"}
    cached = cache.json_get("league_players", key, ttl_hours=48)
    if cached is not None:
        return cached

    api_id = LEAGUE_IDS.get(league_id)
    if not api_id:
        return []

    all_players: list[dict] = []
    page = 1
    while True:
        data = _get("players", {"league": api_id, "season": season, "page": page})
        if not data:
            break
        response = data.get("response", [])
        if not response:
            break
        for item in response:
            all_players.append(_flatten_player_stats(item))
        paging    = data.get("paging", {})
        total_p   = paging.get("total", 1)
        if page >= total_p or page >= 20:   # cap at 20 pages (~500 players)
            break
        page += 1

    cache.json_save("league_players", key, all_players)
    return all_players


def _flatten_player_stats(item: dict) -> dict:
    """Flatten API-Football player+statistics response into a flat dict."""
    p    = item.get("player", {})
    stat = (item.get("statistics") or [{}])[0]

    games      = stat.get("games", {})
    goals      = stat.get("goals", {})
    shots      = stat.get("shots", {})
    passes     = stat.get("passes", {})
    tackles    = stat.get("tackles", {})
    duels      = stat.get("duels", {})
    dribbles   = stat.get("dribbles", {})
    fouls      = stat.get("fouls", {})
    cards      = stat.get("cards", {})

    minutes    = games.get("minutes") or 0
    nineties   = minutes / 90 if minutes else 1   # avoid /0

    def per90(val) -> float:
        try:
            return round(float(val or 0) / nineties, 2)
        except (TypeError, ValueError):
            return 0.0

    def pct(num, denom) -> float:
        try:
            n, d = float(num or 0), float(denom or 0)
            return round(n / d * 100, 1) if d else 0.0
        except (TypeError, ValueError):
            return 0.0

    goals_total   = goals.get("total") or 0
    assists_total = goals.get("assists") or 0
    shots_total   = shots.get("total") or 0
    shots_on      = shots.get("on") or 0
    passes_total  = passes.get("total") or 0
    passes_acc    = passes.get("accuracy") or 0   # already a %
    tackles_total = tackles.get("total") or 0
    blocks_total  = tackles.get("blocks") or 0
    ints_total    = tackles.get("interceptions") or 0
    duels_total   = duels.get("total") or 0
    duels_won     = duels.get("won") or 0
    drib_att      = dribbles.get("attempts") or 0
    drib_suc      = dribbles.get("success") or 0
    fouls_drawn   = fouls.get("drawn") or 0
    fouls_comm    = fouls.get("committed") or 0

    return {
        # identity
        "player_id":      str(p.get("id", "")),
        "player":         p.get("name", ""),
        "age":            str(p.get("age", "")),
        "nationality":    p.get("nationality", ""),
        "team":           stat.get("team", {}).get("name", ""),
        "pos":            games.get("position", ""),
        # raw totals
        "apps":           games.get("appearences") or 0,
        "minutes":        minutes,
        "goals":          goals_total,
        "assists":        assists_total,
        "shots":          shots_total,
        "shots_on":       shots_on,
        "passes":         passes_total,
        "pass_cmp_pct":   float(passes_acc),
        "tackles":        tackles_total,
        "blocks":         blocks_total,
        "interceptions":  ints_total,
        "duels":          duels_total,
        "duels_won":      duels_won,
        "dribbles":       drib_suc,
        "dribble_attempts": drib_att,
        "fouls_won":      fouls_drawn,
        "fouls":          fouls_comm,
        "yellow_cards":   cards.get("yellow") or 0,
        "red_cards":      cards.get("red") or 0,
        "rating":         float(games.get("rating") or 0),
        # per-90
        "goals_p90":      per90(goals_total),
        "assists_p90":    per90(assists_total),
        "shots_p90":      per90(shots_total),
        "shots_on_p90":   per90(shots_on),
        "passes_p90":     per90(passes_total),
        "tackles_p90":    per90(tackles_total),
        "blocks_p90":     per90(blocks_total),
        "ints_p90":       per90(ints_total),
        "dribbles_p90":   per90(drib_suc),
        "fouls_won_p90":  per90(fouls_drawn),
        "fouls_p90":      per90(fouls_comm),
        # derived percentages
        "shot_accuracy":  pct(shots_on, shots_total),
        "dribble_success": pct(drib_suc, drib_att),
        "duel_win_pct":   pct(duels_won, duels_total),
    }
