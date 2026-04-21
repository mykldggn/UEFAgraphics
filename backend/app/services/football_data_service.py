"""
football-data.org v4 API — standings, teams, top scorers.
Free tier: no daily limit, 10 req/min rate limit.
Register for a free key at https://www.football-data.org/client/register

Set FOOTBALL_DATA_KEY in your .env file.
"""
from __future__ import annotations

import logging

from curl_cffi import requests as cffi_requests

from app.config import settings
from app.core import cache

logger = logging.getLogger(__name__)

API_BASE = "https://api.football-data.org/v4"

# Our internal ID → football-data.org competition code
LEAGUE_CODES: dict[str, str] = {
    "ENG-1":    "PL",    # Premier League
    "ENG-2":    "ELC",   # Championship
    "ESP-1":    "PD",    # La Liga
    "DEU-1":    "BL1",   # Bundesliga
    "ITA-1":    "SA",    # Serie A
    "FRA-1":    "FL1",   # Ligue 1
    "PRT-1":    "PPL",   # Primeira Liga
    "NED-1":    "DED",   # Eredivisie
    "BEL-1":    "BSA",   # Belgian First Division A
    "UEFA-CL":  "CL",    # Champions League
    "UEFA-EL":  "EL",    # Europa League
}

LEAGUE_LABELS: dict[str, str] = {
    "ENG-1":    "Premier League",    "ENG-2":   "Championship",
    "ENG-3":    "League One",        "ENG-4":   "League Two",
    "ESP-1":    "La Liga",           "DEU-1":   "Bundesliga",
    "ITA-1":    "Serie A",           "FRA-1":   "Ligue 1",
    "NED-1":    "Eredivisie",        "PRT-1":   "Primeira Liga",
    "BEL-1":    "First Division A",  "SCO-1":   "Scottish Premiership",
    "CHE-1":    "Super League",      "TUR-1":   "Süper Lig",
    "GRC-1":    "Super League Greece","AUT-1":  "Austrian Bundesliga",
    "RUS-1":    "Russian Premier League",
    "UEFA-CL":  "Champions League",  "UEFA-EL": "Europa League",
    "UEFA-ECL": "Conference League",
    "INT-EUROS":"European Championship", "INT-WC": "World Cup",
    "INT-NL":   "UEFA Nations League",
}

LEAGUE_COUNTRY: dict[str, str] = {
    "ENG-1": "England",  "ENG-2": "England",  "ENG-3": "England", "ENG-4": "England",
    "ESP-1": "Spain",    "DEU-1": "Germany",  "ITA-1": "Italy",   "FRA-1": "France",
    "NED-1": "Netherlands", "PRT-1": "Portugal", "BEL-1": "Belgium",
    "SCO-1": "Scotland", "CHE-1": "Switzerland", "TUR-1": "Turkey",
    "GRC-1": "Greece",   "AUT-1": "Austria",  "RUS-1": "Russia",
    "UEFA-CL": "Europe", "UEFA-EL": "Europe", "UEFA-ECL": "Europe",
    "INT-EUROS": "International", "INT-WC": "International",
    "INT-NL": "International",
}

_session: cffi_requests.Session | None = None


def _get_session() -> cffi_requests.Session:
    global _session
    if _session is None:
        _session = cffi_requests.Session(impersonate="chrome")
    return _session


def _get(path: str) -> dict | None:
    if not settings.FOOTBALL_DATA_KEY:
        logger.warning("FOOTBALL_DATA_KEY not set")
        return None
    try:
        resp = _get_session().get(
            f"{API_BASE}/{path.lstrip('/')}",
            headers={"X-Auth-Token": settings.FOOTBALL_DATA_KEY},
            timeout=15,
        )
        if resp.status_code == 429:
            logger.warning("football-data.org rate limited (10 req/min)")
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error(f"football-data {path}: {exc}")
        return None


def get_standings(league_id: str, season: int) -> list[dict]:
    """Return sorted standings table as list of dicts."""
    ck = {"src": "fdorg", "league": league_id, "season": season}
    cached = cache.json_get("fdorg_standings", ck, ttl_hours=6)
    if cached is not None:
        return cached

    code = LEAGUE_CODES.get(league_id)
    if not code:
        return []

    data = _get(f"competitions/{code}/standings?season={season}")
    if not data:
        return []

    try:
        table = next(
            (g["table"] for g in data.get("standings", []) if g.get("type") == "TOTAL"),
            data["standings"][0]["table"] if data.get("standings") else [],
        )
    except (KeyError, IndexError):
        return []

    rows = []
    for entry in table:
        rows.append({
            "rank":          entry.get("position"),
            "team":          entry.get("team", {}).get("name", ""),
            "team_id":       str(entry.get("team", {}).get("id", "")),
            "played":        entry.get("playedGames", 0),
            "wins":          entry.get("won", 0),
            "draws":         entry.get("draw", 0),
            "losses":        entry.get("lost", 0),
            "goals_for":     entry.get("goalsFor", 0),
            "goals_against": entry.get("goalsAgainst", 0),
            "goal_diff":     entry.get("goalDifference", 0),
            "points":        entry.get("points", 0),
            "form":          entry.get("form", ""),
        })

    cache.json_save("fdorg_standings", ck, rows)
    return rows


def get_teams(league_id: str, season: int) -> list[dict]:
    """Return team list for a league+season."""
    ck = {"src": "fdorg", "league": league_id, "season": season}
    cached = cache.json_get("fdorg_teams", ck, ttl_hours=48)
    if cached is not None:
        return cached

    code = LEAGUE_CODES.get(league_id)
    if not code:
        return []

    data = _get(f"competitions/{code}/teams?season={season}")
    if not data:
        return []

    teams = [
        {"id": str(t.get("id", "")), "name": t.get("name", "")}
        for t in data.get("teams", [])
    ]
    cache.json_save("fdorg_teams", ck, teams)
    return teams


def get_top_scorers(league_id: str, season: int, limit: int = 10) -> list[dict]:
    """Return top scorers for a league+season."""
    ck = {"src": "fdorg", "league": league_id, "season": season}
    cached = cache.json_get("fdorg_scorers", ck, ttl_hours=12)
    if cached is not None:
        return cached[:limit]

    code = LEAGUE_CODES.get(league_id)
    if not code:
        return []

    data = _get(f"competitions/{code}/scorers?season={season}&limit=20")
    if not data:
        return []

    scorers = [
        {
            "player":  s.get("player", {}).get("name", ""),
            "team":    s.get("team", {}).get("name", ""),
            "goals":   s.get("goals", 0),
            "assists": s.get("assists", 0) or 0,
        }
        for s in data.get("scorers", [])
    ]
    cache.json_save("fdorg_scorers", ck, scorers)
    return scorers[:limit]
