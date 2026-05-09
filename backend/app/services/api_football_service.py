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
import unicodedata
from collections import Counter, defaultdict
from typing import Any

import requests

from app.config import settings
from app.core import cache

logger = logging.getLogger(__name__)

BASE    = "https://v3.football.api-sports.io"
API_KEY = settings.API_FOOTBALL_KEY.strip()
if API_KEY.lower() in {"your_key_here", "changeme"}:
    API_KEY = ""

# Internal league ID → API-Football league ID
API_FOOTBALL_LEAGUES: dict[str, int] = {
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
    "SCO-1":    179,  # Scottish Premiership
    "BEL-1":    144,  # Belgian Pro League
    "CHE-1":    207,  # Swiss Super League
    "TUR-1":    203,  # Süper Lig
    "GRC-1":    197,  # Super League Greece
    "AUT-1":    218,  # Austrian Bundesliga
    "AUS-1":    188,  # Australian A-League
    "RUS-1":    235,  # Russian Premier League
    "UEFA-CL":  2,    # Champions League
    "UEFA-EL":  3,    # Europa League
    "UEFA-ECL": 848,  # Conference League
}

# API-Football position code → our token
_POS_MAP = {
    "G":  "GK",
    "D":  "D",
    "M":  "M",
    "F":  "F",
}

_session: requests.Session | None = None


def _norm(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()


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


def _af_league_id(internal_league_id: str) -> int | None:
    return API_FOOTBALL_LEAGUES.get(internal_league_id)


def get_teams(internal_league_id: str, season: int) -> list[dict]:
    """Return teams for a league/season, normalised to the app's league endpoint shape."""
    af_league_id = _af_league_id(internal_league_id)
    if not af_league_id:
        return []

    ck = {"league": internal_league_id, "season": season, "v": 1}
    cached = cache.json_get("apifootball_teams", ck, ttl_hours=24)
    if cached is not None:
        return cached

    resp = _get("teams", {"league": af_league_id, "season": season})
    if not resp:
        return []

    teams: list[dict] = []
    for entry in resp:
        team = entry.get("team") or {}
        venue = entry.get("venue") or {}
        if not team.get("id") or not team.get("name"):
            continue
        teams.append({
            "id":      str(team.get("id", "")),
            "name":    team.get("name", ""),
            "short":   team.get("code") or "",
            "tla":     team.get("code") or "",
            "crest":   team.get("logo") or "",
            "venue":   venue.get("name") or "",
            "founded": team.get("founded"),
            "address": venue.get("address") or "",
        })

    cache.json_save("apifootball_teams", ck, teams)
    return teams


def get_standings(internal_league_id: str, season: int) -> list[dict]:
    """Return standings table rows in the same normalised shape as football_data_service."""
    af_league_id = _af_league_id(internal_league_id)
    if not af_league_id:
        return []

    ck = {"league": internal_league_id, "season": season, "v": 1}
    cached = cache.json_get("apifootball_standings", ck, ttl_hours=2)
    if cached is not None:
        return cached

    resp = _get("standings", {"league": af_league_id, "season": season})
    if not resp:
        return []

    groups = (((resp[0] or {}).get("league") or {}).get("standings") or [])
    table = groups[0] if groups else []
    rows: list[dict] = []
    for entry in table:
        team = entry.get("team") or {}
        all_stats = entry.get("all") or {}
        goals = all_stats.get("goals") or {}
        rows.append({
            "rank":          entry.get("rank"),
            "team":          team.get("name", ""),
            "team_id":       str(team.get("id", "")),
            "played":        all_stats.get("played", 0),
            "wins":          all_stats.get("win", 0),
            "draws":         all_stats.get("draw", 0),
            "losses":        all_stats.get("lose", 0),
            "goals_for":     goals.get("for", 0),
            "goals_against": goals.get("against", 0),
            "goal_diff":     entry.get("goalsDiff", 0),
            "points":        entry.get("points", 0),
            "form":          entry.get("form", "") or "",
        })

    rows = [r for r in rows if r["team"]]
    cache.json_save("apifootball_standings", ck, rows)
    return rows


def get_top_scorers(internal_league_id: str, season: int, limit: int = 10) -> list[dict]:
    """Return top scorer rows: player, team, goals, assists."""
    af_league_id = _af_league_id(internal_league_id)
    if not af_league_id:
        return []

    ck = {"league": internal_league_id, "season": season, "limit": limit, "v": 1}
    cached = cache.json_get("apifootball_top_scorers", ck, ttl_hours=6)
    if cached is not None:
        return cached

    resp = _get("players/topscorers", {"league": af_league_id, "season": season})
    if not resp:
        return []

    rows: list[dict] = []
    for entry in resp[:limit]:
        player = entry.get("player") or {}
        stats = (entry.get("statistics") or [{}])[0] or {}
        team = stats.get("team") or {}
        goals = stats.get("goals") or {}
        rows.append({
            "player":  player.get("name", ""),
            "team":    team.get("name", ""),
            "goals":   int(goals.get("total") or 0),
            "assists": int(goals.get("assists") or 0),
        })

    rows = [r for r in rows if r["player"]]
    cache.json_save("apifootball_top_scorers", ck, rows)
    return rows


def search_players(query: str, internal_league_id: str, season: int, limit: int = 20) -> list[dict]:
    """Search players within a league/season for autocomplete fallback."""
    af_league_id = _af_league_id(internal_league_id)
    if not af_league_id or len(query.strip()) < 3:
        return []

    ck = {"q": query.lower().strip(), "league": internal_league_id, "season": season, "v": 1}
    cached = cache.json_get("apifootball_player_search", ck, ttl_hours=24)
    if cached is not None:
        return cached[:limit]

    resp = _get("players", {"league": af_league_id, "season": season, "search": query})
    if not resp:
        return []

    rows: list[dict] = []
    for entry in resp[:limit]:
        player = entry.get("player") or {}
        stats = (entry.get("statistics") or [{}])[0] or {}
        team = stats.get("team") or {}
        games = stats.get("games") or {}
        rows.append({
            "id":     str(player.get("id", "")),
            "name":   player.get("name", ""),
            "team":   team.get("name", ""),
            "pos":    games.get("position", ""),
            "source": "api-football",
        })

    rows = [r for r in rows if r["name"]]
    cache.json_save("apifootball_player_search", ck, rows)
    return rows[:limit]


def get_team_id(team_name: str, internal_league_id: str, season: int) -> int | None:
    """
    Resolve API-Football team ID from team name + league.
    Free plan only supports up to season 2024 — falls back to season-1 automatically.
    Cached 30 days (team IDs don't change).
    """
    ck = {"q": team_name.lower().strip(), "league": internal_league_id, "season": season}
    cached = cache.json_get("apifootball_team_id", ck, ttl_hours=24 * 30)
    if cached is not None:
        return cached.get("team_id")

    af_league_id = API_FOOTBALL_LEAGUES.get(internal_league_id)
    if not af_league_id:
        return None

    # Try requested season first, then recent seasons; team IDs are stable across seasons.
    for s in [season, season - 1, season - 2]:
        resp = _get("teams", {"name": team_name, "league": af_league_id, "season": s})
        if resp:
            break
    if not resp:
        # Broad search without season filter as last resort
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
    Falls back to season-1 if free plan blocks the requested season.
    Does NOT use the `last` API parameter (paid-only) — fetches all FT fixtures
    for the season and slices the most recent N locally.
    Cached 6 h.
    """
    for s in [season, season - 1]:
        ck = {"team_id": af_team_id, "season": s, "last": last}
        cached = cache.json_get("apifootball_fixtures", ck, ttl_hours=6)
        if cached is not None:
            return cached

        # Free plan: no `last` param — fetch all FT fixtures, sort by date, take last N
        resp = _get("fixtures", {"team": af_team_id, "season": s, "status": "FT"})
        if resp:
            # Sort by date ascending, take last N
            sorted_fixtures = sorted(
                resp,
                key=lambda f: f.get("fixture", {}).get("date", ""),
            )
            ids = [
                f["fixture"]["id"]
                for f in sorted_fixtures[-last:]
                if f.get("fixture", {}).get("id")
            ]
            cache.json_save("apifootball_fixtures", ck, ids)
            return ids

    return []


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


def _grid_to_place(formation: str, row: int, col: int) -> float | None:
    """Convert API-Football row:col grid to an ESPN-like formationPlace."""
    if row <= 0 or col <= 0:
        return None
    try:
        parts = [int(x) for x in formation.split("-") if x.strip().isdigit()]
    except (AttributeError, ValueError):
        return None
    line_counts = [1] + parts
    if row > len(line_counts):
        return None
    col = min(col, line_counts[row - 1])
    return float(sum(line_counts[:row - 1]) + col)


def get_team_lineup_hints(
    team_name: str,
    internal_league_id: str,
    season: int,
    num_matches: int = 8,
) -> tuple[dict[str, str] | None, str | None, dict[str, float] | None]:
    """
    Aggregate lineup data across recent matches.
    Returns (pos_hints, formation_str, place_hints).

    pos_hints   — {last_name_lower: most_common position "GK"/"D"/"M"/"F"}
    formation  — most common formation string e.g. "4-3-3"
    place_hints — {last_name_lower: avg_formation_place}, where 1=GK, then each
                  row left-to-right from API-Football's player.grid.

    pos_hints is the most reliable signal — it's the actual position API-Football
    listed each player at, not an inferred value.

    Returns (None, None, None) if API key not set or no data available.
    """
    if not API_KEY:
        return None, None, None

    af_team_id = get_team_id(team_name, internal_league_id, season)
    if not af_team_id:
        logger.debug("api-football: could not resolve team ID for %s", team_name)
        return None, None, None

    fixture_ids = get_recent_fixture_ids(af_team_id, season, last=num_matches)
    if not fixture_ids:
        return None, None, None

    pos_votes: dict[str, list[str]]                    = defaultdict(list)
    place_votes: dict[str, list[tuple[str, float]]]    = defaultdict(list)
    formations: Counter                                = Counter()

    for fid in fixture_ids:
        lineup = get_fixture_lineup(fid, team_name)
        if not lineup:
            continue
        match_formation = lineup.get("formation") or ""
        if match_formation:
            formations[match_formation] += 1
        for p in lineup.get("players", []):
            name = p.get("name", "")
            full = _norm(name) if name else ""
            last = _norm(name.split()[-1]) if name else ""
            row  = p.get("row", 0)
            col  = p.get("col", 0)
            pos  = p.get("pos", "")
            keys = {k for k in (full, last) if k}
            for key in keys:
                if pos:
                    pos_votes[key].append(pos)
            place = _grid_to_place(match_formation, row, col)
            if keys and place is not None and match_formation:
                for key in keys:
                    place_votes[key].append((match_formation, place))

    if not pos_votes and not place_votes:
        return None, None, None

    pos_hints = {k: Counter(v).most_common(1)[0][0] for k, v in pos_votes.items()} or None
    formation = formations.most_common(1)[0][0] if formations else None

    place_hints: dict[str, float] | None = None
    if place_votes and formation:
        filtered = {
            k: [pl for fm, pl in v if fm == formation]
            for k, v in place_votes.items()
        }
        filtered = {k: v for k, v in filtered.items() if v}
        place_hints = {k: sum(v) / len(v) for k, v in filtered.items()} if filtered else None

    return pos_hints, formation, place_hints


def get_goalkeeper_candidates(
    team_name: str,
    internal_league_id: str,
    season: int,
    num_matches: int = 8,
) -> list[dict]:
    """Return recent starting goalkeepers as synthetic player rows for lineup fallback."""
    if not API_KEY:
        return []

    af_team_id = get_team_id(team_name, internal_league_id, season)
    if not af_team_id:
        return []

    fixture_ids = get_recent_fixture_ids(af_team_id, season, last=num_matches)
    if not fixture_ids:
        return []

    starts: Counter = Counter()
    display: dict[str, str] = {}
    for fid in fixture_ids:
        lineup = get_fixture_lineup(fid, team_name)
        if not lineup:
            continue
        for p in lineup.get("players", []):
            pos = str(p.get("pos", "")).upper()
            row = p.get("row", 0)
            if pos != "GK" and row != 1:
                continue
            name = p.get("name", "")
            key = _norm(name)
            if key:
                starts[key] += 1
                display[key] = name

    candidates = []
    for key, count in starts.most_common():
        name = display[key]
        candidates.append({
            "player": name,
            "player_name": name,
            "position": "GK",
            "pos": "GK",
            "minutes": count * 90,
            "apps": count,
            "id": f"apifootball-gk-{key}",
            "source": "api-football",
        })
    return candidates
