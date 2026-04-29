"""
FotMob data service.
Uses curl_cffi (Chrome TLS fingerprint) — no API key required.

Covers:
  - Today's live/finished matches across all competitions (G4 ticker)
  - Team fixture list with opponent names + crests (T4 xG timeline enrichment)
  - Match lineup with formation grid positions incl. L/R column (T1 Most-Played XI)
  - League player stats for non-top-5 leagues (G3)
"""
from __future__ import annotations

import logging
from typing import Any

from curl_cffi import requests as cffi_requests

from app.core import cache

logger = logging.getLogger(__name__)

BASE = "https://api.fotmob.com"

# FotMob league IDs for the major competitions we care about
FOTMOB_LEAGUES: dict[str, int] = {
    # Top 5
    "ENG-1":  47,   # Premier League
    "ESP-1":  87,   # La Liga
    "DEU-1":  54,   # Bundesliga
    "ITA-1":  55,   # Serie A
    "FRA-1":  53,   # Ligue 1
    # Others
    "ENG-2":  48,   # Championship
    "ENG-3":  49,   # League One
    "NED-1":  57,   # Eredivisie
    "POR-1":  61,   # Primeira Liga
    "SCO-1":  58,   # Scottish Premiership
    "BEL-1":  59,   # Pro League
    "TUR-1":  71,   # Süper Lig
    # Europe
    "UEFA-CL": 42,  # Champions League
    "UEFA-EL": 73,  # Europa League
    "UEFA-ECL": 10478,  # Conference League
}


_session: cffi_requests.Session | None = None


def _sess() -> cffi_requests.Session:
    global _session
    if _session is None:
        _session = cffi_requests.Session(impersonate="chrome")
    return _session


def _get(path: str, params: dict | None = None) -> Any:
    """Raw GET against FotMob API — returns parsed JSON or None on failure."""
    try:
        resp = _sess().get(
            f"{BASE}/{path.lstrip('/')}",
            params=params or {},
            headers={
                "Referer": "https://www.fotmob.com/",
                "Origin":  "https://www.fotmob.com",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("fotmob GET %s: %s", path, exc)
        return None


# ── Today's matches ────────────────────────────────────────────────────────────

def get_today_matches(date_str: str | None = None) -> list[dict]:
    """
    Returns a flat list of match dicts, one per match, sorted live-first.
    Each dict:
      id, status, minute, homeTeam, awayTeam, homeScore, awayScore,
      leagueName, leagueId, homeTeamId, awayTeamId, homeTeamCrest, awayTeamCrest,
      isLive, isFinished, scorers (list[str])
    """
    from datetime import date
    date_key = date_str or date.today().isoformat().replace("-", "")
    ck = {"date": date_key}
    cached = cache.json_get("fotmob_today", ck, ttl_hours=0)  # no file cache — always fresh
    # for live data we skip disk cache but keep a 2-min in-memory style via very short TTL
    # (TTL 0 means we always re-fetch; callers should throttle if needed)

    raw = _get("matches", {"date": date_key})
    if not raw:
        return []

    matches: list[dict] = []
    leagues = raw.get("leagues", [])
    for league in leagues:
        league_name = league.get("name", "")
        league_id   = league.get("id", 0)
        for m in league.get("matches", []):
            status_obj  = m.get("status", {})
            score_obj   = m.get("home", {}), m.get("away", {})
            home        = m.get("home", {})
            away        = m.get("away", {})
            is_live     = bool(status_obj.get("liveTime"))
            is_finished = status_obj.get("finished", False)
            minute      = status_obj.get("liveTime", {}).get("short", "") if is_live else ""

            # Goal scorers — FotMob puts them in m["status"]["scoreStr"] as "1 - 0"
            # and in m["home"/"away"]["shortName"]; detailed scorers need matchDetails
            scorers: list[str] = []

            matches.append({
                "id":             m.get("id"),
                "status":         _match_status_label(status_obj),
                "minute":         minute,
                "homeTeam":       home.get("longName", home.get("name", "")),
                "awayTeam":       away.get("longName", away.get("name", "")),
                "homeScore":      home.get("score"),
                "awayScore":      away.get("score"),
                "homeTeamId":     home.get("id"),
                "awayTeamId":     away.get("id"),
                "homeTeamCrest":  _crest_url(home.get("id")),
                "awayTeamCrest":  _crest_url(away.get("id")),
                "leagueName":     league_name,
                "leagueId":       league_id,
                "isLive":         is_live,
                "isFinished":     is_finished,
                "scorers":        scorers,
            })

    # Sort: live first, then not-started, then finished
    def _sort_key(m: dict) -> int:
        if m["isLive"]:      return 0
        if m["isFinished"]:  return 2
        return 1

    matches.sort(key=_sort_key)
    return matches


def _match_status_label(status: dict) -> str:
    if status.get("liveTime"):
        lt = status["liveTime"]
        return lt.get("short", "LIVE")
    if status.get("finished"):
        return "FT"
    if status.get("notStarted"):
        # kick-off time
        return status.get("utcTime", "")[:16].replace("T", " ")[11:16]  # HH:MM
    if status.get("cancelled"):
        return "CANC"
    if status.get("postponed"):
        return "PPD"
    return ""


def _crest_url(team_id: int | None) -> str:
    if not team_id:
        return ""
    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"


# ── Team fixtures ──────────────────────────────────────────────────────────────

def get_team_fixtures(fotmob_team_id: int, season: str | None = None) -> list[dict]:
    """
    Returns list of fixtures for a team, newest-first.
    Each dict: matchId, date, opponent, opponentId, opponentCrest,
               homeAway, goalsFor, goalsAgainst, result (W/D/L)
    Uses 6-hour cache.
    """
    ck = {"team_id": fotmob_team_id, "season": season or "current"}
    cached = cache.json_get("fotmob_fixtures", ck, ttl_hours=6)
    if cached is not None:
        return cached

    raw = _get("teams", {"id": fotmob_team_id})
    if not raw:
        return []

    fixtures: list[dict] = []
    for section in raw.get("fixtures", {}).get("allFixtures", {}).get("fixtures", []):
        status = section.get("status", {})
        if not status.get("finished"):
            continue  # only completed matches

        home     = section.get("home", {})
        away     = section.get("away", {})
        team_is_home = home.get("id") == fotmob_team_id

        opponent    = away if team_is_home else home
        gf          = home.get("score") if team_is_home else away.get("score")
        ga          = away.get("score") if team_is_home else home.get("score")
        try:
            gf_i = int(gf); ga_i = int(ga)
            result = "W" if gf_i > ga_i else ("D" if gf_i == ga_i else "L")
        except (TypeError, ValueError):
            result = "?"

        fixtures.append({
            "matchId":       section.get("id"),
            "date":          section.get("status", {}).get("utcTime", "")[:10],
            "opponent":      opponent.get("longName", opponent.get("name", "")),
            "opponentId":    opponent.get("id"),
            "opponentCrest": _crest_url(opponent.get("id")),
            "homeAway":      "H" if team_is_home else "A",
            "goalsFor":      gf,
            "goalsAgainst":  ga,
            "result":        result,
        })

    # Sort newest-first
    fixtures.sort(key=lambda x: x["date"], reverse=True)
    cache.json_save("fotmob_fixtures", ck, fixtures)
    return fixtures


# ── Match lineup ───────────────────────────────────────────────────────────────

def get_match_lineup(match_id: int) -> dict:
    """
    Returns formation + player grid positions for both teams.

    Shape:
    {
      "homeTeam": {
        "name": "Arsenal",
        "formation": "4-3-3",
        "players": [
          {"id": 123, "name": "Saka", "shirt": 7,
           "row": 3,   # 1=GK, 2=DEF, 3=MID, 4=FWD
           "col": 3,   # 1=Left, 2=Center, 3=Right  (within their row)
           "totalInRow": 3},  # total players in this row
          ...
        ]
      },
      "awayTeam": { ... }
    }
    """
    ck = {"match_id": match_id}
    cached = cache.json_get("fotmob_lineup", ck, ttl_hours=24)
    if cached is not None:
        return cached

    raw = _get("matchDetails", {"matchId": match_id})
    if not raw:
        return {}

    result = {}
    for side_key, team_key in [("home", "homeTeam"), ("away", "awayTeam")]:
        lineup_data = (raw.get("content", {})
                          .get("lineup", {})
                          .get(side_key, {}))
        if not lineup_data:
            continue

        formation = lineup_data.get("formation", "")
        players_raw = lineup_data.get("players", [])  # list of rows
        team_name = (raw.get("general", {})
                        .get(f"{side_key}Team", {})
                        .get("name", ""))

        players: list[dict] = []
        for row_idx, row in enumerate(players_raw):
            row_num = row_idx + 1  # 1-based (1=GK row)
            total_in_row = len(row)
            for col_idx, p in enumerate(row):
                players.append({
                    "id":          p.get("id"),
                    "name":        p.get("name", {}).get("fullName", p.get("name", "")),
                    "shirt":       p.get("shirt"),
                    "row":         row_num,
                    "col":         col_idx + 1,   # 1=Left, …, N=Right
                    "totalInRow":  total_in_row,
                    "isSub":       bool(p.get("isSub")),
                    "positionId":  p.get("positionId"),
                })

        result[team_key] = {
            "name":      team_name,
            "formation": formation,
            "players":   players,
        }

    if result:
        cache.json_save("fotmob_lineup", ck, result)
    return result


# ── League player stats (non-top-5) ───────────────────────────────────────────

def get_league_players(fotmob_league_id: int, season_year: int | None = None) -> list[dict]:
    """
    Returns top player stats for a FotMob league.
    Each dict: playerId, name, teamName, teamId, goals, assists, rating, minutesPlayed
    Uses 12-hour cache.
    """
    ck = {"league_id": fotmob_league_id, "season": season_year or "current"}
    cached = cache.json_get("fotmob_league_players", ck, ttl_hours=12)
    if cached is not None:
        return cached

    raw = _get("leagues", {"id": fotmob_league_id, "ccode3": "ENG"})
    if not raw:
        return []

    players: list[dict] = []
    stats_section = raw.get("stats", {}).get("players", [])
    seen: set[int] = set()

    for stat_group in stats_section:
        for entry in stat_group.get("statsData", []):
            pid = entry.get("participantId")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            players.append({
                "playerId":      pid,
                "name":          entry.get("name", ""),
                "teamName":      entry.get("teamName", ""),
                "teamId":        entry.get("teamId"),
                "goals":         entry.get("goals", 0),
                "assists":       entry.get("assists", 0),
                "rating":        entry.get("rating"),
                "minutesPlayed": entry.get("minutesPlayed", 0),
            })

    cache.json_save("fotmob_league_players", ck, players)
    return players


# ── Lookup helpers ─────────────────────────────────────────────────────────────

def league_id_to_fotmob(internal_id: str) -> int | None:
    """Convert our internal league ID (e.g. 'ENG-1') to FotMob integer ID."""
    return FOTMOB_LEAGUES.get(internal_id)


def search_team(team_name: str) -> int | None:
    """
    Search FotMob for a team by name — returns FotMob team ID or None.
    Results cached for 24 h.
    """
    ck = {"q": team_name.lower()}
    cached = cache.json_get("fotmob_team_search", ck, ttl_hours=24)
    if cached is not None:
        return cached.get("team_id")

    raw = _get("searchapi/suggest", {"term": team_name})
    if not raw:
        return None

    for hit in raw:
        if hit.get("type") == "team":
            tid = hit.get("id")
            cache.json_save("fotmob_team_search", ck, {"team_id": tid})
            return tid
    return None
