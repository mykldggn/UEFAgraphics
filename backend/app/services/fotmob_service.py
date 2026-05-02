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
    ck = {"fm_league": fm_league_id, "season": season_year or "current", "v": 5}
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

    # ── Also pull from topPlayers section (more reliable for xG/shots/kp) ───
    _TP_KEY_MAP: dict[str, str] = {
        "goals":            "goals",
        "assists":          "assists",
        "expectedGoals":    "xg",
        "xg":               "xg",
        "shots":            "shots",
        "keyPasses":        "key_passes",
        "keypasses":        "key_passes",
        "expectedAssists":  "xa",
        "xa":               "xa",
        "successfulDribbles": "dribbles",
        "minutesPlayed":    "minutes",
        "appearances":      "apps",
        "rating":           None,
    }
    top_players_section = raw.get("topPlayers") or {}
    for fm_key, our_key in _TP_KEY_MAP.items():
        if our_key is None:
            continue
        for entry in top_players_section.get(fm_key, []):
            pid = entry.get("id") or entry.get("participantId")
            if not pid:
                continue
            pid = int(pid)
            if pid not in pool:
                pos_raw = entry.get("position") or entry.get("role") or ""
                pool[pid] = {
                    "id":         str(pid),
                    "player":     entry.get("name", entry.get("fullName", "")),
                    "team":       entry.get("teamName", entry.get("teamShortName", "")),
                    "teamId":     entry.get("teamId"),
                    "position":   fotmob_pos_to_token(pos_raw),
                    "goals":      0.0, "assists":   0.0, "shots":     0.0,
                    "key_passes": 0.0, "xg":        0.0, "xa":        0.0,
                    "dribbles":   0.0, "minutes":   0.0, "apps":      0.0,
                }
            p = pool[pid]
            val = (entry.get("value") or entry.get("statValue") or
                   entry.get(fm_key) or 0)
            fv = _safe_float(val)
            if fv > p[our_key]:
                p[our_key] = fv
            # Update minutes from topPlayers if better
            mins_val = entry.get("minutesPlayed") or entry.get("minutePlayed")
            if mins_val:
                mv = _safe_float(mins_val)
                if mv > p["minutes"]:
                    p["minutes"] = mv

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
    Find the FotMob integer team ID for a named team.
    Scans allMatches first (guaranteed to contain team IDs), then falls back
    to FotMob team search.
    """
    raw = _get_league_raw(fm_league_id, season_year)
    name_lo = team_name.lower().strip()

    # Primary: scan allMatches — every team that played is in here with its ID
    all_matches = (raw.get("matches") or {}).get("allMatches", [])
    for m in all_matches:
        for side in ("home", "away"):
            t = m.get(side) or {}
            long_name  = (t.get("longName") or "").lower().strip()
            short_name = (t.get("name") or "").lower().strip()
            t_id = t.get("id")
            if t_id:
                for candidate in (long_name, short_name):
                    if candidate and (name_lo in candidate or candidate in name_lo):
                        return int(t_id)

    return None


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
    Tries three strategies in order:
      1. Parse the nested table structure (various FotMob response shapes)
      2. Reconstruct standings from allMatches (always works when matches exist)
    Returns list of dicts: rank, team, team_id, played, wins, draws, losses,
                           goals_for, goals_against, goal_diff, points.
    team_id is the FotMob integer team ID (as string).
    """
    ck = {"fm_league": fm_league_id, "season": season_year or "current", "v": 2}
    cached = cache.json_get("fotmob_league_table", ck, ttl_hours=2)
    if cached is not None:
        return cached

    raw = _get_league_raw(fm_league_id, season_year)
    if not raw:
        return []

    # ── Strategy 1: parse official table structure ───────────────────────────
    entries = _extract_fotmob_table_entries(raw)
    if entries:
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
                gf = int(entry.get("goalFor", entry.get("goalsFor", 0)) or 0)
                ga = int(entry.get("goalAgainst", entry.get("goalsAgainst", 0)) or 0)

            rank = int(entry.get("idx", entry.get("rank", i + 1)) or (i + 1))
            result.append({
                "rank":          rank,
                "team":          name,
                "team_id":       str(tid),
                "played":        int(entry.get("played", entry.get("matchesPlayed", 0)) or 0),
                "wins":          int(entry.get("wins", entry.get("won", 0)) or 0),
                "draws":         int(entry.get("draws", entry.get("draw", 0)) or 0),
                "losses":        int(entry.get("losses", entry.get("lost", 0)) or 0),
                "goals_for":     gf,
                "goals_against": ga,
                "goal_diff":     gf - ga,
                "points":        int(entry.get("pts", entry.get("points", 0)) or 0),
            })
        if result:
            result.sort(key=lambda r: (r["rank"], -r["points"]))
            cache.json_save("fotmob_league_table", ck, result)
            return result

    # ── Strategy 2: reconstruct from allMatches ───────────────────────────────
    result = _reconstruct_table_from_matches(raw)
    if result:
        cache.json_save("fotmob_league_table", ck, result)
    return result


def _reconstruct_table_from_matches(raw: dict) -> list[dict]:
    """Reconstruct league standings by replaying all finished matches."""
    from collections import defaultdict

    all_matches = (raw.get("matches") or {}).get("allMatches", [])
    teams: dict[str, dict] = {}
    team_ids: dict[str, str] = {}

    for m in all_matches:
        if not (m.get("status") or {}).get("finished"):
            continue
        home = m.get("home") or {}
        away = m.get("away") or {}
        hn = home.get("longName") or home.get("name") or ""
        an = away.get("longName") or away.get("name") or ""
        try:
            hg = int(home.get("score", 0))
            ag = int(away.get("score", 0))
        except (TypeError, ValueError):
            continue

        for name, gf, ga, is_home in [(hn, hg, ag, True), (an, ag, hg, False)]:
            if not name:
                continue
            if name not in teams:
                teams[name] = {"played": 0, "wins": 0, "draws": 0, "losses": 0,
                               "gf": 0, "ga": 0, "pts": 0}
            t = teams[name]
            t["played"] += 1
            t["gf"] += gf
            t["ga"] += ga
            side = home if is_home else away
            team_ids[name] = str(side.get("id", ""))
            if gf > ga:
                t["wins"] += 1; t["pts"] += 3
            elif gf == ga:
                t["draws"] += 1; t["pts"] += 1
            else:
                t["losses"] += 1

    if not teams:
        return []

    sorted_teams = sorted(
        teams.items(),
        key=lambda x: (x[1]["pts"], x[1]["gf"] - x[1]["ga"], x[1]["gf"]),
        reverse=True,
    )
    return [
        {
            "rank":          i + 1,
            "team":          name,
            "team_id":       team_ids.get(name, ""),
            "played":        t["played"],
            "wins":          t["wins"],
            "draws":         t["draws"],
            "losses":        t["losses"],
            "goals_for":     t["gf"],
            "goals_against": t["ga"],
            "goal_diff":     t["gf"] - t["ga"],
            "points":        t["pts"],
        }
        for i, (name, t) in enumerate(sorted_teams)
    ]


def search_players_fotmob(name: str, fm_league_id: int | None = None) -> list[dict]:
    """
    Search FotMob league player pool by name.
    If fm_league_id given, searches that league's stat pool.
    Returns list of {id, name, team, teamId, leagueId}.
    """
    if not fm_league_id:
        return []
    pool = get_league_player_stats(fm_league_id)
    q_lo = name.lower()
    return [
        {"id": p["id"], "name": p["player"], "team": p["team"],
         "teamId": p.get("teamId"), "leagueId": fm_league_id}
        for p in pool if q_lo in p["player"].lower()
    ][:20]
