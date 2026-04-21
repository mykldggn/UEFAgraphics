"""
Understat data layer.
Uses curl_cffi (Chrome TLS fingerprint) so Cloudflare never blocks it.

Covers: EPL, La_liga, Bundesliga, Serie_A, Ligue_1, RFPL
Shot data + full player season stats (goals, assists, xG, xA, npxG,
xGChain, xGBuildup, shots, key_passes, minutes, games).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from curl_cffi import requests as cffi_requests

from app.core import cache

logger = logging.getLogger(__name__)

API_BASE = "https://understat.com"

UNDERSTAT_LEAGUES = {
    "EPL":        "Premier League",
    "La_liga":    "La Liga",
    "Bundesliga": "Bundesliga",
    "Serie_A":    "Serie A",
    "Ligue_1":    "Ligue 1",
    "RFPL":       "Russian Premier League",
}

# Map our internal league IDs → Understat league slug
LEAGUE_TO_US: dict[str, str] = {
    "ENG-1": "EPL",
    "ESP-1": "La_liga",
    "DEU-1": "Bundesliga",
    "ITA-1": "Serie_A",
    "FRA-1": "Ligue_1",
    "RUS-1": "RFPL",
}


# ── Session ────────────────────────────────────────────────────────────────────

_session: Optional[cffi_requests.Session] = None


def _get_session() -> cffi_requests.Session:
    global _session
    if _session is None:
        _session = cffi_requests.Session(impersonate="chrome")
    return _session


def _ajax(path: str, referer: str) -> dict | list | None:
    """GET a JSON endpoint with the correct Referer and XHR headers."""
    try:
        resp = _get_session().get(
            f"{API_BASE}/{path.lstrip('/')}",
            headers={
                "Referer":           f"{API_BASE}/{referer.lstrip('/')}",
                "X-Requested-With":  "XMLHttpRequest",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error(f"understat ajax {path}: {exc}")
        return None


# ── Player shots ───────────────────────────────────────────────────────────────

def get_player_shots(player_id: str) -> pd.DataFrame:
    ck = {"player_id": player_id}
    cached = cache.json_get("understat_shots", ck, ttl_hours=12)
    if cached is not None:
        return pd.DataFrame(cached)

    # Warm the session cookie
    _get_session().get(f"{API_BASE}/player/{player_id}", timeout=30)
    data = _ajax(f"getPlayerData/{player_id}", f"player/{player_id}")
    if not data:
        return pd.DataFrame()

    shots = data.get("shots", [])
    df    = _build_shot_df(shots)
    cache.json_save("understat_shots", ck, df.to_dict(orient="records"))
    return df


# ── Player meta + season stats ─────────────────────────────────────────────────

def get_player_meta(player_id: str) -> dict:
    ck = {"player_id": player_id}
    cached = cache.json_get("understat_player_meta", ck, ttl_hours=12)
    if cached is not None:
        return cached

    _get_session().get(f"{API_BASE}/player/{player_id}", timeout=30)
    data = _ajax(f"getPlayerData/{player_id}", f"player/{player_id}")
    if not data:
        return {"name": "Unknown", "player_id": player_id, "season_stats": []}

    meta = {
        "name":          data.get("player", {}).get("name", "Unknown"),
        "player_id":     player_id,
        "season_stats":  _parse_season_stats(data.get("groups", {}).get("season", [])),
    }
    cache.json_save("understat_player_meta", ck, meta)
    return meta


def get_player_season_stats(player_id: str, season: int) -> dict | None:
    """Return per-90 stats for a specific season."""
    meta = get_player_meta(player_id)
    for row in meta.get("season_stats", []):
        if int(row.get("season", -1)) == season:
            return row
    return None


def _parse_season_stats(seasons: list[dict]) -> list[dict]:
    """Normalise Understat season groups into flat dicts with per-90 columns."""
    out = []
    for s in seasons:
        minutes  = int(s.get("time", 0) or 0)
        nineties = minutes / 90 if minutes else 1

        def _f(key) -> float:
            try:
                return float(s.get(key, 0) or 0)
            except (ValueError, TypeError):
                return 0.0

        def p90(val: float) -> float:
            return round(val / nineties, 2)

        goals     = _f("goals");    assists  = _f("assists")
        shots     = _f("shots");    kp       = _f("key_passes")
        xg        = _f("xG");       xa       = _f("xA")
        npg       = _f("npg");      npxg     = _f("npxG")
        xgchain   = _f("xGChain"); xgbuild  = _f("xGBuildup")

        out.append({
            "season":        int(s.get("season", 0) or 0),
            "team":          s.get("team", ""),
            "position":      s.get("position", ""),
            "apps":          int(s.get("games", 0) or 0),
            "minutes":       minutes,
            # totals
            "goals":         goals,    "assists":    assists,
            "shots":         shots,    "key_passes": kp,
            "xg":            xg,       "xa":         xa,
            "npg":           npg,      "npxg":       npxg,
            "xgchain":       xgchain,  "xgbuildup":  xgbuild,
            "yellow":        int(s.get("yellow", 0) or 0),
            "red":           int(s.get("red", 0) or 0),
            # per-90
            "goals_p90":     p90(goals),   "assists_p90":    p90(assists),
            "shots_p90":     p90(shots),   "key_passes_p90": p90(kp),
            "xg_p90":        p90(xg),      "xa_p90":         p90(xa),
            "npxg_p90":      p90(npxg),    "xgchain_p90":    p90(xgchain),
            "xgbuildup_p90": p90(xgbuild),
        })
    return out


# ── League player stats (for radar percentiles) ────────────────────────────────

def get_league_player_stats(league: str, season: int) -> list[dict]:
    """
    Return per-season stats for all players in a league.
    Uses getLeaguePlayers endpoint — returns full stats including
    xG, xA, npxG, xGChain, xGBuildup, shots, key_passes.
    """
    ck = {"league": league, "season": season}
    cached = cache.json_get("understat_league_player_stats", ck, ttl_hours=24)
    if cached is not None:
        return cached

    _get_session().get(f"{API_BASE}/league/{league}/{season}", timeout=30)
    data = _ajax(f"getLeagueData/{league}/{season}", f"league/{league}/{season}")
    if not data:
        return []

    players = []
    for p in (data.get("players", []) if isinstance(data, dict) else []):
        if not p.get("id"):
            continue
        minutes  = int(p.get("time", 0) or 0)
        nineties = minutes / 90 if minutes else 1

        def _f(key) -> float:
            try:
                return float(p.get(key, 0) or 0)
            except (ValueError, TypeError):
                return 0.0

        def p90(val: float) -> float:
            return round(val / nineties, 2)

        goals    = _f("goals");   assists = _f("assists")
        shots    = _f("shots");   kp      = _f("key_passes")
        xg       = _f("xG");     xa      = _f("xA")
        npxg     = _f("npxG");   npg     = _f("npg")
        xgchain  = _f("xGChain"); xgbuild = _f("xGBuildup")

        players.append({
            "id":            str(p.get("id", "")),
            "player":        p.get("player_name", ""),
            "team":          p.get("team_title", ""),
            "pos":           p.get("position", ""),
            "apps":          int(p.get("games", 0) or 0),
            "minutes":       minutes,
            "goals":         goals,   "assists":    assists,
            "shots":         shots,   "key_passes": kp,
            "xg":            xg,      "xa":         xa,
            "npxg":          npxg,    "npg":        npg,
            "xgchain":       xgchain, "xgbuildup":  xgbuild,
            # per-90
            "goals_p90":     p90(goals),    "assists_p90":    p90(assists),
            "shots_p90":     p90(shots),    "key_passes_p90": p90(kp),
            "xg_p90":        p90(xg),       "xa_p90":         p90(xa),
            "npxg_p90":      p90(npxg),     "xgchain_p90":    p90(xgchain),
            "xgbuildup_p90": p90(xgbuild),
        })

    cache.json_save("understat_league_player_stats", ck, players)
    return players


# ── Player search ──────────────────────────────────────────────────────────────

def search_players(query: str) -> list[dict]:
    ck = {"q": query.lower()}
    cached = cache.json_get("understat_search", ck, ttl_hours=24)
    if cached is not None:
        return cached

    try:
        resp = _get_session().get(f"{API_BASE}/main/search/{query}", timeout=20)
        if not resp.ok:
            return []
        results = resp.json() or []
    except Exception as exc:
        logger.error(f"search_players {query}: {exc}")
        return []

    out = [
        {"id": str(p.get("id")), "name": p.get("name", ""), "team": p.get("team_title", "")}
        for p in results if p.get("id") and p.get("name")
    ]
    cache.json_save("understat_search", ck, out)
    return out


def get_league_players(league: str, season: int) -> list[dict]:
    """Lightweight player list for search/dropdown (id + name + team)."""
    stats = get_league_player_stats(league, season)
    return [{"id": p["id"], "name": p["player"], "team": p["team"]} for p in stats]


# ── Team data ──────────────────────────────────────────────────────────────────

def get_league_teams(league: str, season: int) -> list[dict]:
    ck = {"league": league, "season": season}
    cached = cache.json_get("understat_league_teams", ck, ttl_hours=24)
    if cached is not None:
        return cached

    _get_session().get(f"{API_BASE}/league/{league}/{season}", timeout=30)
    data = _ajax(f"getLeagueTeams/{league}/{season}", f"league/{league}/{season}")
    if not data:
        return []

    teams = [
        {
            "id":    str(tid),
            "name":  info.get("title", ""),
            "xG":    float(info.get("xG", 0)),
            "xGA":   float(info.get("xGA", 0)),
            "xPts":  float(info.get("xpts", 0)),
            "pts":   int(info.get("pts", 0)),
            "wins":  int(info.get("wins", 0)),
            "draws": int(info.get("draws", 0)),
            "loses": int(info.get("loses", 0)),
        }
        for tid, info in (data or {}).items()
    ]
    cache.json_save("understat_league_teams", ck, teams)
    return teams


def get_team_shots(team_id: str, season: int) -> pd.DataFrame:
    ck = {"team_id": team_id, "season": season}
    cached = cache.json_get("understat_team_shots", ck, ttl_hours=12)
    if cached is not None:
        return pd.DataFrame(cached)

    _get_session().get(f"{API_BASE}/team/{team_id}/{season}", timeout=30)
    data = _ajax(f"getTeamPlayers/{team_id}/{season}", f"team/{team_id}/{season}")
    if not data:
        return pd.DataFrame()

    all_shots = []
    for p in (data or [])[:25]:
        try:
            pid    = str(p.get("id"))
            sub_df = get_player_shots(pid)
            sub_df = sub_df[sub_df["season"] == season]
            all_shots.append(sub_df)
        except Exception as exc:
            logger.warning(f"shots for player {p.get('id')}: {exc}")

    if not all_shots:
        return pd.DataFrame()

    df = pd.concat(all_shots, ignore_index=True)
    cache.json_save("understat_team_shots", ck, df.to_dict(orient="records"))
    return df


def get_team_xg_history(team_id: str, season: int) -> list[dict]:
    ck = {"team_id": team_id, "season": season}
    cached = cache.json_get("understat_team_xg_history", ck, ttl_hours=12)
    if cached is not None:
        return cached

    _get_session().get(f"{API_BASE}/team/{team_id}/{season}", timeout=30)
    data = _ajax(f"getTeamResults/{team_id}/{season}", f"team/{team_id}/{season}")
    if not data:
        return []

    history      = []
    cum_xG       = 0.0
    cum_xGA      = 0.0
    for i, m in enumerate(data or [], 1):
        home    = m.get("h", {})
        away    = m.get("a", {})
        is_home = str(home.get("id")) == str(team_id)
        xG      = float(m.get("xG", {}).get("h" if is_home else "a", 0))
        xGA     = float(m.get("xG", {}).get("a" if is_home else "h", 0))
        cum_xG  += xG
        cum_xGA += xGA
        history.append({
            "match":          i,
            "date":           m.get("datetime", ""),
            "opponent":       away.get("title") if is_home else home.get("title"),
            "xG":             round(xG, 3),
            "xGA":            round(xGA, 3),
            "cumulative_xG":  round(cum_xG, 3),
            "cumulative_xGA": round(cum_xGA, 3),
            "goals":          int(m.get("goals", {}).get("h" if is_home else "a", 0)),
            "goals_against":  int(m.get("goals", {}).get("a" if is_home else "h", 0)),
        })

    cache.json_save("understat_team_xg_history", ck, history)
    return history


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_shot_df(shots: list) -> pd.DataFrame:
    if not shots:
        return pd.DataFrame()
    df = pd.DataFrame(shots)
    for col in ["X", "Y", "xG"]:
        df[col] = pd.to_numeric(df.get(col, pd.Series(dtype=float)), errors="coerce")
    df["season"] = pd.to_numeric(df.get("season", pd.Series(dtype=float)), errors="coerce")
    df = df.dropna(subset=["X", "Y", "xG", "season"])
    df["X"]      = df["X"] * 100
    df["Y"]      = df["Y"] * 100
    df["season"] = df["season"].astype(int)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "h_a" in df.columns and "h_team" in df.columns and "a_team" in df.columns:
        df["team"] = df.apply(lambda r: r["h_team"] if r["h_a"] == "h" else r["a_team"], axis=1)
    return df.reset_index(drop=True)
