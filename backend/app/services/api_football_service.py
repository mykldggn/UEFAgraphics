"""
API-Football (api-football.com) — free tier, 100 req/day.
Used for match lineup + formation data to power Most Played XI.

Free key: register at api-football.com, set env var API_FOOTBALL_KEY.
Headers: x-apisports-key: {key}
Base URL: https://v3.football.api-sports.io

All past-match data is cached indefinitely (matches don't change).
Team IDs cached 30 days. Fixture lists cached 6h.
"""
from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from typing import Any

import requests

from app.core import cache

logger = logging.getLogger(__name__)

BASE    = "https://v3.football.api-sports.io"
API_KEY = os.environ.get("API_FOOTBALL_KEY", "")

# Internal league ID → API-Football league ID
API_FOOTBALL_LEAGUES: dict[str, int] = {
    "ENG-1":    39,   # Premier League
    "ENG-2":    40,   # Championship
    "ENG-3":    41,   # League One
    "ESP-1":    140,  # La Liga
    "DEU-1":    78,   # Bundesliga
    "ITA-1":    135,  # Serie A
    "FRA-1":    61,   # Ligue 1
    "NED-1":    88,   # Eredivisie
    "PRT-1":    94,   # Primeira Liga
    "SCO-1":    179,  # Scottish Premiership
    "BEL-1":    144,  # Belgian Pro League
    "TUR-1":    203,  # Süper Lig
    "UEFA-CL":  2,    # Champions League
    "UEFA-EL":  3,    # Europa League
    "UEFA-ECL": 848,  # Conference League
}

# API-Football position code → our token
_POS_MAP = {
    "G":  "GK",
    "D":  "DEF",
    "M":  "MID",
    "F":  "FWD",
}

_session: requests.Session | None = None


def _sess() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "x-apisports-key": API_KEY,
            "Accept":          "application/json",
        })
    return _session


def _get(path: str, params: dict | None = None) -> Any:
    if not API_KEY:
        logger.debug("API_FOOTBALL_KEY not set — skipping call to %s", path)
        return None
    try:
        resp = _sess().get(f"{BASE}/{path.lstrip('/')}", params=params or {}, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors", {})
        if errors:
            logger.warning("api-football %s errors: %s", path, errors)
            return None
        return data.get("response")
    except Exception as exc:
        logger.error("api-football GET %s: %s", path, exc)
        return None


def get_team_id(team_name: str, internal_league_id: str, season: int) -> int | None:
    """
    Resolve API-Football team ID from team name + league.
    Cached 30 days (team IDs don't change).
    """
    ck = {"q": team_name.lower().strip(), "league": internal_league_id, "season": season}
    cached = cache.json_get("apifootball_team_id", ck, ttl_hours=24 * 30)
    if cached is not None:
        return cached.get("team_id")

    af_league_id = API_FOOTBALL_LEAGUES.get(internal_league_id)
    if not af_league_id:
        return None

    resp = _get("teams", {"name": team_name, "league": af_league_id, "season": season})
    if not resp:
        # Try broader name search
        resp = _get("teams", {"search": team_name[:6]})

    if not resp:
        return None

    name_lo = team_name.lower().strip()
    best = None
    for entry in resp:
        t = entry.get("team", {})
        t_name = (t.get("name") or "").lower()
        if name_lo in t_name or t_name in name_lo:
            best = t.get("id")
            break
    if best is None and resp:
        best = resp[0].get("team", {}).get("id")

    if best:
        cache.json_save("apifootball_team_id", ck, {"team_id": best})
    return best


def get_recent_fixture_ids(af_team_id: int, season: int, last: int = 8) -> list[int]:
    """
    Get the `last` most recent completed fixture IDs for a team in a season.
    Cached 6 h (list changes as season progresses).
    """
    ck = {"team_id": af_team_id, "season": season, "last": last}
    cached = cache.json_get("apifootball_fixtures", ck, ttl_hours=6)
    if cached is not None:
        return cached

    resp = _get("fixtures", {"team": af_team_id, "season": season,
                              "last": last, "status": "FT"})
    if not resp:
        return []

    ids = [f["fixture"]["id"] for f in resp if f.get("fixture", {}).get("id")]
    cache.json_save("apifootball_fixtures", ck, ids)
    return ids


def get_fixture_lineup(fixture_id: int, team_name: str) -> dict | None:
    """
    Return lineup data for one team in a fixture.
    Shape: {"formation": "4-3-3", "players": [{"name": "Saka", "row": 2, "col": 3, "pos": "FWD"}, ...]}
    Row is 1-based (1=GK, 2=DEF, ...).  Col is 1-based within the row (1=Left).
    Cached indefinitely (past matches don't change).
    """
    ck = {"fixture_id": fixture_id}
    cached = cache.json_get("apifootball_lineup", ck, ttl_hours=24 * 365)
    if cached is not None:
        # Find the matching team
        return _pick_team(cached, team_name)

    resp = _get("fixtures/lineups", {"fixture": fixture_id})
    if not resp:
        return None

    # Save raw response for both teams
    cache.json_save("apifootball_lineup", ck, resp)
    return _pick_team(resp, team_name)


def _pick_team(resp: list[dict], team_name: str) -> dict | None:
    """Select the matching team from a fixture lineup response."""
    name_lo = team_name.lower().strip()
    best = None
    for entry in resp:
        t_name = (entry.get("team", {}).get("name") or "").lower()
        if name_lo in t_name or t_name in name_lo:
            best = entry
            break
    if best is None and resp:
        best = resp[0]
    if not best:
        return None

    formation = best.get("formation") or ""
    start_xi  = best.get("startXI") or []

    players: list[dict] = []
    for entry in start_xi:
        p     = entry.get("player", {})
        grid  = p.get("grid") or ""   # "row:col" e.g. "2:3"
        pos   = p.get("pos") or ""    # G / D / M / F
        name  = p.get("name") or ""
        row, col = _parse_grid(grid)
        players.append({
            "name": name,
            "row":  row,
            "col":  col,
            "pos":  _POS_MAP.get(pos, "MID"),
        })

    return {"formation": formation, "players": players}


def _parse_grid(grid: str) -> tuple[int, int]:
    """Parse "row:col" string → (row, col), both 1-based. Returns (0,0) on failure."""
    try:
        parts = grid.split(":")
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return 0, 0


def get_team_lineup_hints(
    team_name: str,
    internal_league_id: str,
    season: int,
    num_matches: int = 8,
) -> tuple[dict[str, int] | None, dict[str, int] | None, dict[str, str] | None, str | None]:
    """
    Aggregate lineup data across recent matches.
    Returns (col_hints, row_hints, pos_hints, formation_str).

    col_hints  — {last_name_lower: most_common_col_number}
    row_hints  — {last_name_lower: most_common_row_number}
    pos_hints  — {last_name_lower: most_common_position "GK"/"DEF"/"MID"/"FWD"}
    formation  — most common formation string e.g. "4-3-3"

    pos_hints is the most reliable signal — it's the actual position API-Football
    listed each player at, not an inferred value.

    Returns (None, None, None, None) if API key not set or no data available.
    """
    if not API_KEY:
        return None, None, None, None

    af_team_id = get_team_id(team_name, internal_league_id, season)
    if not af_team_id:
        logger.debug("api-football: could not resolve team ID for %s", team_name)
        return None, None, None, None

    fixture_ids = get_recent_fixture_ids(af_team_id, season, last=num_matches)
    if not fixture_ids:
        return None, None, None, None

    col_votes: dict[str, list[int]]  = defaultdict(list)
    row_votes: dict[str, list[int]]  = defaultdict(list)
    pos_votes: dict[str, list[str]]  = defaultdict(list)
    formations: Counter              = Counter()

    for fid in fixture_ids:
        lineup = get_fixture_lineup(fid, team_name)
        if not lineup:
            continue
        if lineup.get("formation"):
            formations[lineup["formation"]] += 1
        for p in lineup.get("players", []):
            name = p.get("name", "")
            last = name.split()[-1].lower() if name else ""
            row  = p.get("row", 0)
            col  = p.get("col", 0)
            pos  = p.get("pos", "")   # already mapped to GK/DEF/MID/FWD
            if last and row:
                row_votes[last].append(row)
            if last and col:
                col_votes[last].append(col)
            if last and pos:
                pos_votes[last].append(pos)

    if not row_votes:
        return None, None, None, None

    col_hints = {k: Counter(v).most_common(1)[0][0] for k, v in col_votes.items()} or None
    row_hints = {k: Counter(v).most_common(1)[0][0] for k, v in row_votes.items()} or None
    pos_hints = {k: Counter(v).most_common(1)[0][0] for k, v in pos_votes.items()} or None
    formation = formations.most_common(1)[0][0] if formations else None

    return col_hints, row_hints, pos_hints, formation
