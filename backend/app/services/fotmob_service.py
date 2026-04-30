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
    "PRT-1":  61,   # Primeira Liga
    "SCO-1":  58,   # Scottish Premiership
    "BEL-1":  59,   # Pro League
    "TUR-1":  71,   # Süper Lig
    # Europe
    "UEFA-CL": 42,  # Champions League
    "UEFA-EL": 73,  # Europa League
    "UEFA-ECL": 10478,  # Conference League
}


# FotMob position string → Understat-style token(s) (for lineup classification)
_FOTMOB_POS_TOKEN: dict[str, str] = {
    "goalkeeper":            "GK",
    "centre-back":           "D",
    "central defender":      "D",
    "defender":              "D",
    "right back":            "D M",
    "left back":             "D M",
    "full back":             "D M",
    "fullback":              "D M",
    "wing back":             "D M",
    "right wing back":       "D M",
    "left wing back":        "D M",
    "wing-back":             "D M",
    "right wing-back":       "D M",
    "left wing-back":        "D M",
    "defensive midfielder":  "M D",
    "defensive midfield":    "M D",
    "holding midfielder":    "M D",
    "central midfielder":    "M",
    "midfielder":            "M",
    "right midfield":        "M",
    "left midfield":         "M",
    "right midfielder":      "M",
    "left midfielder":       "M",
    "box-to-box midfielder": "M",
    "attacking midfielder":  "F M",
    "attacking midfield":    "F M",
    "second striker":        "F M",
    "right winger":          "F M",
    "left winger":           "F M",
    "winger":                "F M",
    "right wing":            "F M",
    "left wing":             "F M",
    "striker":               "F",
    "centre-forward":        "F",
    "center-forward":        "F",
    "centre forward":        "F",
    "center forward":        "F",
    "forward":               "F",
    "attacker":              "F",
}


def fotmob_pos_to_token(pos_str: str) -> str:
    """Map FotMob position string to Understat-style token(s). Defaults to 'M'."""
    return _FOTMOB_POS_TOKEN.get(pos_str.lower().strip(), "M")


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


# ── Full league data (cached, used by multiple functions) ──────────────────────

def _get_league_raw(fm_league_id: int, season_year: int | None = None) -> dict:
    """
    Fetch and cache the FotMob leagues endpoint response.
    Contains: table, allMatches, stats.players, topPlayers.
    TTL 2h so stats stay fresh.
    """
    ck = {"fm_league": fm_league_id, "season": season_year or "current"}
    cached = cache.json_get("fotmob_league_raw", ck, ttl_hours=2)
    if cached is not None:
        return cached
    params: dict = {"id": fm_league_id, "ccode3": "ENG"}
    if season_year:
        params["season"] = str(season_year)
    raw = _get("leagues", params)
    if not raw:
        return {}
    cache.json_save("fotmob_league_raw", ck, raw)
    return raw


# ── Full league player stats pool (for radar percentiles + leaders) ────────────

def get_league_player_stats(fm_league_id: int, season_year: int | None = None) -> list[dict]:
    """
    Comprehensive per-player stats for a FotMob league, normalised to match the
    column names used by understat_service.get_league_player_stats().
    Columns: id, player, team, goals, assists, shots, key_passes, xg, xa,
             minutes, apps, goals_p90, assists_p90, shots_p90, key_passes_p90,
             xg_p90, xa_p90, dribbles, dribbles_p90.
    Missing Understat-only cols (npxg, xgchain, xgbuildup) are set to 0.
    """
    ck = {"fm_league": fm_league_id, "season": season_year or "current", "v": 4}
    cached = cache.json_get("fotmob_league_player_stats_v2", ck, ttl_hours=6)
    if cached is not None:
        return cached

    raw = _get_league_raw(fm_league_id, season_year)
    if not raw:
        return []

    # Merge all stat groups by participantId, collecting every numeric field
    pool: dict[int, dict] = {}

    def _safe_float(v) -> float:
        try:
            return float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0

    # Map group statKey/header → our column (for statValue extraction fallback)
    _GRP_KEY_MAP: dict[str, str | None] = {
        "goals": "goals", "topgoals": "goals", "goal": "goals",
        "assists": "assists", "topassists": "assists", "assist": "assists",
        "shots": "shots", "topshots": "shots",
        "keypasses": "key_passes", "keypass": "key_passes", "topkeypasses": "key_passes",
        "xg": "xg", "expectedgoals": "xg", "topxg": "xg",
        "xa": "xa", "expectedassists": "xa",
        "dribbles": "dribbles", "successfuldribbles": "dribbles",
        "minutesplayed": "minutes", "appearances": "apps",
        "rating": None, "toprating": None,
    }

    _KEY_MAP = {
        "goals": "goals", "assists": "assists", "shots": "shots",
        "keyPasses": "key_passes", "keypasses": "key_passes", "key_passes": "key_passes",
        "xg": "xg", "expectedGoals": "xg", "xGoal": "xg",
        "xa": "xa", "expectedAssists": "xa",
        "successfulDribbles": "dribbles", "dribbles": "dribbles",
        "minutesPlayed": "minutes", "minutes": "minutes",
        "matchesPlayed": "apps", "appearances": "apps", "apps": "apps",
    }

    for grp in raw.get("stats", {}).get("players", []):
        # Determine which stat this group represents (for statValue fallback)
        grp_key = str(grp.get("statKey") or grp.get("header") or "").lower()
        grp_key_norm = grp_key.replace(" ", "").replace("_", "").replace("-", "")
        dest_from_grp: str | None = _GRP_KEY_MAP.get(grp_key_norm)

        for entry in grp.get("statsData", []):
            pid = entry.get("participantId")
            if not pid:
                continue
            if pid not in pool:
                pos_raw = entry.get("position") or entry.get("pos") or ""
                pool[pid] = {
                    "id":           str(pid),
                    "player":       entry.get("name", ""),
                    "team":         entry.get("teamName", ""),
                    "teamId":       entry.get("teamId"),
                    "position":     fotmob_pos_to_token(pos_raw),
                    "goals":        0.0, "assists":    0.0, "shots":      0.0,
                    "key_passes":   0.0, "xg":         0.0, "xa":         0.0,
                    "dribbles":     0.0, "minutes":    0.0, "apps":       0.0,
                }
            p = pool[pid]
            # Update position if we get a non-empty value
            pos_raw = entry.get("position") or entry.get("pos") or ""
            if pos_raw and p["position"] == "M":  # only override the default
                p["position"] = fotmob_pos_to_token(pos_raw)

            # Collect every numeric field, keeping the maximum observed value
            for raw_key, our_key in _KEY_MAP.items():
                val = entry.get(raw_key)
                if val is not None:
                    fv = _safe_float(val)
                    if fv > p[our_key]:
                        p[our_key] = fv

            # statValue fallback: use group's statKey to identify what it represents
            if dest_from_grp:
                sv = entry.get("statValue") or entry.get("value")
                if sv is not None:
                    fv = _safe_float(sv)
                    if fv > p[dest_from_grp]:
                        p[dest_from_grp] = fv

    # Build final list with per-90 stats
    result: list[dict] = []
    for pid, p in pool.items():
        mins = max(p["minutes"], 1.0)
        n90  = mins / 90

        def p90(v: float) -> float:
            return round(v / n90, 3)

        result.append({
            **p,
            "goals_p90":     p90(p["goals"]),
            "assists_p90":   p90(p["assists"]),
            "shots_p90":     p90(p["shots"]),
            "key_passes_p90": p90(p["key_passes"]),
            "xg_p90":        p90(p["xg"]),
            "xa_p90":        p90(p["xa"]),
            "dribbles_p90":  p90(p["dribbles"]),
            # Understat-only — set 0 so percentile code degrades gracefully
            "npxg": 0.0, "npxg_p90": 0.0,
            "xgchain": 0.0, "xgchain_p90": 0.0,
            "xgbuildup": 0.0, "xgbuildup_p90": 0.0,
        })

    result.sort(key=lambda r: r["goals"], reverse=True)
    cache.json_save("fotmob_league_player_stats_v2", ck, result)
    return result


# ── Player profile data ────────────────────────────────────────────────────────

def get_player_data(fm_player_id: int | str) -> dict:
    """Raw player profile from FotMob playerData endpoint (cached 6 h)."""
    pid = int(fm_player_id)
    ck = {"pid": pid}
    cached = cache.json_get("fotmob_player_data", ck, ttl_hours=6)
    if cached is not None:
        return cached
    raw = _get("playerData", {"id": pid})
    if not raw:
        return {}
    cache.json_save("fotmob_player_data", ck, raw)
    return raw


def _parse_fm_stats(stat_list: list[dict]) -> dict:
    """Convert FotMob stat array [{title, value, type}] to flat float dict."""
    out: dict[str, float] = {}
    for s in stat_list:
        key = str(s.get("type", s.get("title", ""))).lower().replace(" ", "_")
        try:
            out[key] = float(str(s.get("value", "0")).replace(",", ""))
        except (ValueError, TypeError):
            pass
    return out


def _parse_season_year(s: str) -> int | None:
    """Extract start year from '2024/2025' → 2024."""
    try:
        return int(str(s).split("/")[0].split("-")[0][:4])
    except (ValueError, IndexError):
        return None


def get_player_season_stats(
    fm_player_id: int | str,
    season_year: int,
    fm_league_id: int | None = None,
) -> dict:
    """
    Per-season stats for a FotMob player — normalised to the same keys as
    understat_service._parse_season_stats().
    Returns {} when not found.
    """
    raw = get_player_data(fm_player_id)
    if not raw:
        return {}

    seasons = (raw.get("careerStatistics") or {}).get("seasons", [])
    best: dict = {}
    for entry in seasons:
        yr = _parse_season_year(entry.get("seasonId") or entry.get("season") or "")
        if yr != season_year:
            continue
        if fm_league_id and entry.get("tournamentId") != fm_league_id:
            continue
        parsed = _parse_fm_stats(entry.get("stat", []))

        goals   = parsed.get("goals", parsed.get("goal", 0))
        assists = parsed.get("assists", parsed.get("assist", 0))
        shots   = parsed.get("shots", 0)
        kp      = parsed.get("keypasses", parsed.get("key_passes", 0))
        xg      = parsed.get("xg", parsed.get("expected_goals", 0))
        xa      = parsed.get("xa", parsed.get("expected_assists", 0))
        mins    = parsed.get("minutesplayed", parsed.get("minutes_played", parsed.get("minutes", 0)))
        apps    = parsed.get("appearances", parsed.get("matchesplayed", 0))
        n90     = max(mins / 90, 0.1)

        def p90(v: float) -> float:
            return round(v / n90, 3)

        best = {
            "season": season_year,
            "team":   entry.get("teamName", ""),
            "league": entry.get("tournamentName", ""),
            "apps":   int(apps), "minutes": int(mins),
            "goals":  goals,  "assists":    assists,
            "shots":  shots,  "key_passes": kp,
            "xg":     xg,     "xa":         xa,
            "npxg":   0.0,    "npxg_p90":   0.0,
            "xgchain": 0.0,   "xgchain_p90": 0.0,
            "xgbuildup": 0.0, "xgbuildup_p90": 0.0,
            "goals_p90":     p90(goals),   "assists_p90":    p90(assists),
            "shots_p90":     p90(shots),   "key_passes_p90": p90(kp),
            "xg_p90":        p90(xg),      "xa_p90":         p90(xa),
        }
        # If we also matched the league, this is ideal — stop
        if fm_league_id and entry.get("tournamentId") == fm_league_id:
            break
    return best


def get_player_career_history(fm_player_id: int | str) -> list[dict]:
    """
    Career history for career-xg chart.
    Each entry: season_year, team, league, goals, xg, assists, xa, minutes.
    """
    raw = get_player_data(fm_player_id)
    if not raw:
        return []

    seasons = (raw.get("careerStatistics") or {}).get("seasons", [])
    history: list[dict] = []
    for entry in seasons:
        yr = _parse_season_year(entry.get("seasonId") or entry.get("season") or "")
        if not yr:
            continue
        parsed = _parse_fm_stats(entry.get("stat", []))
        history.append({
            "season_year": yr,
            "team":        entry.get("teamName", ""),
            "league":      entry.get("tournamentName", ""),
            "goals":       parsed.get("goals", 0),
            "xg":          parsed.get("xg", parsed.get("expected_goals", 0)),
            "assists":      parsed.get("assists", 0),
            "xa":           parsed.get("xa", parsed.get("expected_assists", 0)),
            "minutes":      parsed.get("minutesplayed", parsed.get("minutes", 0)),
        })
    return sorted(history, key=lambda e: e["season_year"])


# ── Shot data for shot map / career xG ────────────────────────────────────────

_FM_RESULT_MAP = {
    "Goal":          "Goal",
    "AttemptSaved":  "SavedShot",
    "Miss":          "MissedShots",
    "Post":          "MissedShots",
    "Block":         "BlockedShot",
    "Blocked":       "BlockedShot",
}
_FM_SIT_MAP = {
    "RegularPlay":    "OpenPlay",
    "FromCorner":     "FromCorner",
    "SetPiece":       "FromCorner",
    "DirectFreekick": "DirectFreekick",
    "Penalty":        "Penalty",
}


def get_match_shots_raw(match_id: int | str) -> list[dict]:
    """
    All shots from a single match's shotmap section (cached 48 h — matches don't change).
    Returns list of normalised dicts: playerId, teamId, X, Y, xG, result, situation, season=0.
    """
    mid = int(match_id)
    ck = {"mid": mid, "type": "shots"}
    cached = cache.json_get("fotmob_match_shots", ck, ttl_hours=48)
    if cached is not None:
        return cached

    raw = _get("matchDetails", {"matchId": mid})
    if not raw:
        return []

    shots_raw = (raw.get("content") or {}).get("shotmap", {}).get("shots", [])
    # Also try alternative path
    if not shots_raw:
        shots_raw = raw.get("shotmap", {}).get("shots", [])

    shots: list[dict] = []
    season_str = (raw.get("general") or {}).get("matchTimeUTCDate", "")[:4]
    try:
        season_int = int(season_str)
    except (ValueError, TypeError):
        season_int = 0

    for s in shots_raw:
        event_type = s.get("eventType", "")
        result = _FM_RESULT_MAP.get(event_type, "MissedShots")
        # FotMob x/y are 0-100; x=100 is attacking goal — same as Understat X
        x_raw = s.get("x", s.get("X", 50))
        y_raw = s.get("y", s.get("Y", 50))
        xg    = s.get("expectedGoals", s.get("xg", s.get("xG", 0))) or 0
        try:
            xg = float(xg)
        except (TypeError, ValueError):
            xg = 0.0
        shots.append({
            "playerId":  s.get("playerId"),
            "teamId":    s.get("teamId"),
            "X":         float(x_raw),
            "Y":         float(y_raw),
            "xG":        xg,
            "result":    result,
            "situation": _FM_SIT_MAP.get(s.get("situation", ""), "OpenPlay"),
            "season":    season_int,
            "minute":    s.get("min", 0),
        })

    cache.json_save("fotmob_match_shots", ck, shots)
    return shots


def get_player_season_shots(
    fm_player_id: int | str,
    fm_team_id: int | str,
    season_year: int,
) -> "pd.DataFrame":
    """
    Aggregate all shots for a player across their team's season matches.
    Returns a DataFrame with columns: X, Y, xG, result, situation, season, team.
    (Potentially slow on first call; each match is individually cached.)
    """
    import pandas as pd

    pid = int(fm_player_id)
    tid = int(fm_team_id)
    ck  = {"pid": pid, "tid": tid, "season": season_year, "type": "season_shots"}
    cached = cache.json_get("fotmob_player_shots", ck, ttl_hours=12)
    if cached is not None:
        return pd.DataFrame(cached) if cached else pd.DataFrame()

    fixtures = get_team_fixtures(tid)
    # Filter to this season
    fixtures = [f for f in fixtures
                if _parse_season_year(f.get("date", "")[:4] + "/00") == season_year
                or str(season_year) in f.get("date", "")]

    all_shots: list[dict] = []
    for f in fixtures:
        mid = f.get("matchId")
        if not mid:
            continue
        for shot in get_match_shots_raw(mid):
            if shot.get("playerId") == pid:
                all_shots.append({**shot, "team": f.get("opponent", "")})

    cache.json_save("fotmob_player_shots", ck, all_shots)
    return pd.DataFrame(all_shots) if all_shots else pd.DataFrame()


# ── Team season xG (per-match, with REAL xG from FotMob) ─────────────────────

def get_team_season_xg(
    fm_team_id: int | str,
    fm_league_id: int,
    season_year: int | None = None,
) -> list[dict]:
    """
    Per-match xG history for a team — same output format as
    understat_service.get_team_xg_history() so team_xg_timeline render works
    with has_xg=True.

    Each dict: match, date, goals, goals_against, result, h_a, opponent,
               xG, xGA, cumulative_xG, cumulative_xGA,
               cumulative_goals, cumulative_goals_against.
    """
    tid  = int(fm_team_id)
    ck   = {"tid": tid, "fm_league": fm_league_id, "season": season_year or "current"}
    cached = cache.json_get("fotmob_team_season_xg", ck, ttl_hours=3)
    if cached is not None:
        return cached

    raw = _get_league_raw(fm_league_id, season_year)
    all_matches = (raw.get("matches") or {}).get("allMatches", [])

    team_matches: list[dict] = []
    for m in all_matches:
        status = m.get("status") or {}
        if not status.get("finished"):
            continue
        home = m.get("home") or {}
        away = m.get("away") or {}
        home_id = home.get("id")
        away_id = away.get("id")
        if home_id != tid and away_id != tid:
            continue

        is_home  = home_id == tid
        opp      = away if is_home else home
        opp_name = opp.get("longName") or opp.get("name", "")

        try:
            gf = int(home.get("score", 0) if is_home else away.get("score", 0))
            ga = int(away.get("score", 0) if is_home else home.get("score", 0))
        except (TypeError, ValueError):
            continue

        xg_for  = float(home.get("xg", 0) or 0) if is_home else float(away.get("xg", 0) or 0)
        xg_agt  = float(away.get("xg", 0) or 0) if is_home else float(home.get("xg", 0) or 0)

        if gf > ga:   result = "w"
        elif gf == ga: result = "d"
        else:          result = "l"

        date = str(status.get("utcTime", ""))[:10]
        team_matches.append({
            "date":          date,
            "opponent":      opp_name,
            "goals":         gf,
            "goals_against": ga,
            "result":        result,
            "h_a":           "H" if is_home else "A",
            "xG":            round(xg_for, 2),
            "xGA":           round(xg_agt, 2),
        })

    team_matches.sort(key=lambda m: m["date"])
    cum_xg = cum_xga = cum_g = cum_ga = 0.0
    history: list[dict] = []
    for i, m in enumerate(team_matches, 1):
        cum_xg  += m["xG"];   cum_xga += m["xGA"]
        cum_g   += m["goals"]; cum_ga  += m["goals_against"]
        history.append({
            **m,
            "match":                 i,
            "cumulative_xG":         round(cum_xg, 2),
            "cumulative_xGA":        round(cum_xga, 2),
            "cumulative_goals":      int(cum_g),
            "cumulative_goals_against": int(cum_ga),
        })

    cache.json_save("fotmob_team_season_xg", ck, history)
    return history


# ── League position history ────────────────────────────────────────────────────

def get_league_position_history(
    fm_league_id: int,
    season_year: int | None = None,
) -> dict:
    """
    Reconstruct per-matchday league positions from FotMob match results.
    Output matches understat_service.get_league_position_history():
    {"teams": [...], "history": [{"match": 1, "Arsenal": 1, ...}, ...]}
    """
    ck = {"fm_league": fm_league_id, "season": season_year or "current", "v": 2}
    ttl = 2 if not season_year or season_year >= 2025 else 24 * 7
    cached = cache.json_get("fotmob_pos_history", ck, ttl_hours=ttl)
    if cached is not None:
        return cached

    raw = _get_league_raw(fm_league_id, season_year)
    all_matches = (raw.get("matches") or {}).get("allMatches", [])

    from collections import defaultdict

    # Group finished matches by roundId / matchday
    by_round: dict[int, list[dict]] = defaultdict(list)
    for m in all_matches:
        status = m.get("status") or {}
        if not status.get("finished"):
            continue
        rid = m.get("roundId") or m.get("round")
        if rid is not None:
            by_round[int(rid)].append(m)

    if not by_round:
        return {}

    # Running totals per team {name: {pts, gd, gf, played}}
    totals: dict[str, dict] = {}

    history_rows: list[dict] = []
    matchday_counter = 0

    for round_num in sorted(by_round.keys()):
        matchday_counter += 1
        for m in by_round[round_num]:
            home = m.get("home") or {}
            away = m.get("away") or {}
            home_name = home.get("longName") or home.get("name") or ""
            away_name = away.get("longName") or away.get("name") or ""
            try:
                hg = int(home.get("score", 0))
                ag = int(away.get("score", 0))
            except (TypeError, ValueError):
                continue

            for name in (home_name, away_name):
                if name and name not in totals:
                    totals[name] = {"pts": 0, "gd": 0, "gf": 0}

            if home_name:
                totals[home_name]["gf"] += hg
                totals[home_name]["gd"] += hg - ag
                totals[home_name]["pts"] += 3 if hg > ag else (1 if hg == ag else 0)
            if away_name:
                totals[away_name]["gf"] += ag
                totals[away_name]["gd"] += ag - hg
                totals[away_name]["pts"] += 3 if ag > hg else (1 if ag == hg else 0)

        # Rank after this matchday
        ranked = sorted(
            totals.items(),
            key=lambda kv: (-kv[1]["pts"], -kv[1]["gd"], -kv[1]["gf"]),
        )
        row: dict = {"match": matchday_counter}
        for pos, (name, _) in enumerate(ranked, 1):
            row[name] = pos
        history_rows.append(row)

    if not history_rows:
        return {}

    result = {
        "teams":   sorted(totals.keys()),
        "history": history_rows,
    }
    cache.json_save("fotmob_pos_history", ck, result)
    return result


# ── Player search ──────────────────────────────────────────────────────────────

def resolve_fotmob_team_id(
    team_name: str,
    fm_league_id: int,
    season_year: int | None = None,
) -> int | None:
    """
    Find the FotMob integer team ID for a named team by scanning the league's
    allMatches data.  Falls back to FotMob team search if not found.
    """
    raw = _get_league_raw(fm_league_id, season_year)
    all_matches = (raw.get("matches") or {}).get("allMatches", [])

    name_lo = team_name.lower().strip()
    # Build name → id from match participants
    for m in all_matches:
        for side in ("home", "away"):
            t = m.get(side) or {}
            t_name = (t.get("longName") or t.get("name") or "").lower().strip()
            t_id = t.get("id")
            if t_id and (name_lo in t_name or t_name in name_lo):
                return int(t_id)

    # Also try the table section
    table_entries = _extract_fotmob_table_entries(raw)
    for entry in table_entries:
        e_name = (entry.get("name") or entry.get("shortName") or "").lower().strip()
        if e_name and (name_lo in e_name or e_name in name_lo):
            tid = entry.get("id") or entry.get("teamId") or ""
            if isinstance(tid, str) and tid.startswith("team-"):
                tid = tid.split("-")[-1]
            try:
                return int(tid)
            except (ValueError, TypeError):
                pass

    return search_team(team_name)


def _extract_fotmob_table_entries(raw: dict) -> list[dict]:
    """
    Extract the standings table rows from a FotMob leagues raw response.
    Handles multiple known response shapes.
    """
    table_root = raw.get("table") or []

    # Shape 1: table = [{"data": {"table": {"all": [...]}}}]
    if isinstance(table_root, list):
        for section in table_root:
            if isinstance(section, dict):
                entries = (section.get("data") or {}).get("table", {}).get("all", [])
                if entries:
                    return entries
        # Shape 2: table = [{"all": [...]}]
        for section in table_root:
            if isinstance(section, dict):
                entries = section.get("all", [])
                if entries:
                    return entries

    # Shape 3: table = {"all": [...]}
    if isinstance(table_root, dict):
        entries = table_root.get("all", [])
        if entries:
            return entries

    return []


def get_league_table(fm_league_id: int, season_year: int | None = None) -> list[dict]:
    """
    Build a standings table from FotMob league raw data.
    Returns list of dicts: rank, team, team_id, played, wins, draws, losses,
                           goals_for, goals_against, goal_diff, points.
    team_id is the FotMob integer team ID (as string).
    """
    ck = {"fm_league": fm_league_id, "season": season_year or "current", "v": 1}
    cached = cache.json_get("fotmob_league_table", ck, ttl_hours=2)
    if cached is not None:
        return cached

    raw = _get_league_raw(fm_league_id, season_year)
    if not raw:
        return []

    entries = _extract_fotmob_table_entries(raw)
    if not entries:
        return []

    result: list[dict] = []
    for i, entry in enumerate(entries):
        name = entry.get("name") or entry.get("shortName") or ""
        tid  = entry.get("id") or entry.get("teamId") or ""
        if isinstance(tid, str) and tid.startswith("team-"):
            tid = tid.split("-")[-1]

        scores = entry.get("scoresStr", "0:0") or "0:0"
        try:
            gf, ga = map(int, str(scores).split(":"))
        except (ValueError, TypeError):
            gf, ga = 0, 0

        rank = int(entry.get("idx", i + 1) or (i + 1))
        result.append({
            "rank":          rank,
            "team":          name,
            "team_id":       str(tid),
            "played":        int(entry.get("played", 0) or 0),
            "wins":          int(entry.get("wins", 0) or 0),
            "draws":         int(entry.get("draws", 0) or 0),
            "losses":        int(entry.get("losses", 0) or 0),
            "goals_for":     gf,
            "goals_against": ga,
            "goal_diff":     gf - ga,
            "points":        int(entry.get("pts", 0) or 0),
        })

    result.sort(key=lambda r: r["rank"])
    cache.json_save("fotmob_league_table", ck, result)
    return result


def search_players_fotmob(name: str, fm_league_id: int | None = None) -> list[dict]:
    """
    Search FotMob for players by name.
    If fm_league_id given, filters to players in that league.
    Returns list of {id, name, team, teamId, leagueId}.
    Cached 24 h.
    """
    ck = {"q": name.lower(), "league": fm_league_id or 0}
    cached = cache.json_get("fotmob_player_search", ck, ttl_hours=24)
    if cached is not None:
        return cached

    raw = _get("searchapi/suggest", {"term": name})
    results: list[dict] = []
    if raw:
        for hit in (raw if isinstance(raw, list) else []):
            if hit.get("type") != "player":
                continue
            lid = hit.get("leagueId") or hit.get("teamLeagueId")
            if fm_league_id and lid != fm_league_id:
                continue
            results.append({
                "id":       str(hit.get("id", "")),
                "name":     hit.get("name", hit.get("title", "")),
                "team":     hit.get("teamName", ""),
                "teamId":   hit.get("teamId"),
                "leagueId": lid,
            })

    # Also filter league player pool if we have a league ID but results are empty
    if not results and fm_league_id:
        pool = get_league_player_stats(fm_league_id)
        q_lo = name.lower()
        results = [
            {"id": p["id"], "name": p["player"], "team": p["team"],
             "teamId": p.get("teamId"), "leagueId": fm_league_id}
            for p in pool if q_lo in p["player"].lower()
        ][:20]

    cache.json_save("fotmob_player_search", ck, results)
    return results
