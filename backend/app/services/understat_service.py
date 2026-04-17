"""
Understat scraper — ported from EPL_Player_ShotChart notebook.
Covers: EPL, La Liga, Bundesliga, Serie A, Ligue 1, RFPL (Russian Premier League).
Shot data includes coordinates, xG, result, situation, shotType.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

from app.core import cache

logger = logging.getLogger(__name__)

API_BASE = "https://understat.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# Leagues Understat covers
UNDERSTAT_LEAGUES = {
    "EPL":   "Premier League",
    "La_liga": "La Liga",
    "Bundesliga": "Bundesliga",
    "Serie_A": "Serie A",
    "Ligue_1": "Ligue 1",
    "RFPL": "Russian Premier League",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get_player_shots(player_id: str) -> pd.DataFrame:
    """Return all career shots for an Understat player ID."""
    cached = cache.json_get("understat_shots", {"player_id": player_id}, ttl_hours=12)
    if cached is not None:
        return pd.DataFrame(cached)

    session = _session()
    session.get(f"{API_BASE}/player/{player_id}", timeout=30)
    resp = session.get(
        f"{API_BASE}/getPlayerData/{player_id}",
        headers={"Referer": f"{API_BASE}/player/{player_id}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    shots = data.get("shots", [])
    df = _build_shot_df(shots)
    cache.json_save("understat_shots", {"player_id": player_id}, df.to_dict(orient="records"))
    return df


def get_player_meta(player_id: str) -> dict:
    """Return name, position, team, season stats summary for a player."""
    cached = cache.json_get("understat_player_meta", {"player_id": player_id}, ttl_hours=12)
    if cached is not None:
        return cached

    session = _session()
    session.get(f"{API_BASE}/player/{player_id}", timeout=30)
    resp = session.get(
        f"{API_BASE}/getPlayerData/{player_id}",
        headers={"Referer": f"{API_BASE}/player/{player_id}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    meta = {
        "name": data.get("player", {}).get("name", "Unknown"),
        "player_id": player_id,
        "season_stats": data.get("groupsData", {}).get("season", []),
    }
    cache.json_save("understat_player_meta", {"player_id": player_id}, meta)
    return meta


def search_players(query: str) -> list[dict]:
    """Search Understat for players by name."""
    cached = cache.json_get("understat_search", {"q": query.lower()}, ttl_hours=24)
    if cached is not None:
        return cached

    session = _session()
    resp = session.get(
        f"{API_BASE}/main/search/{query}",
        timeout=20,
    )
    if not resp.ok:
        return []
    results = resp.json() or []
    out = [
        {"id": str(p.get("id")), "name": p.get("name", ""), "team": p.get("team_title", "")}
        for p in results
        if p.get("id") and p.get("name")
    ]
    cache.json_save("understat_search", {"q": query.lower()}, out)
    return out


def get_league_players(league: str, season: int) -> list[dict]:
    """Return player list for a league+season (for search/dropdown)."""
    cached = cache.json_get("understat_league_players", {"league": league, "season": season}, ttl_hours=24)
    if cached is not None:
        return cached

    session = _session()
    session.get(f"{API_BASE}/league/{league}/{season}", timeout=30)
    resp = session.get(
        f"{API_BASE}/getLeaguePlayers/{league}/{season}",
        headers={"Referer": f"{API_BASE}/league/{league}/{season}"},
        timeout=30,
    )
    resp.raise_for_status()
    players = resp.json() or []
    out = [
        {"id": str(p.get("id")), "name": p.get("player_name", ""), "team": p.get("team_title", "")}
        for p in players
        if p.get("id")
    ]
    cache.json_save("understat_league_players", {"league": league, "season": season}, out)
    return out


def get_league_teams(league: str, season: int) -> list[dict]:
    """Return team list + stats for a league+season."""
    cached = cache.json_get("understat_league_teams", {"league": league, "season": season}, ttl_hours=24)
    if cached is not None:
        return cached

    session = _session()
    session.get(f"{API_BASE}/league/{league}/{season}", timeout=30)
    resp = session.get(
        f"{API_BASE}/getLeagueTeams/{league}/{season}",
        headers={"Referer": f"{API_BASE}/league/{league}/{season}"},
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json() or {}
    teams = [
        {
            "id": str(tid),
            "name": info.get("title", ""),
            "xG": float(info.get("xG", 0)),
            "xGA": float(info.get("xGA", 0)),
            "xPts": float(info.get("xpts", 0)),
            "pts": int(info.get("pts", 0)),
            "wins": int(info.get("wins", 0)),
            "draws": int(info.get("draws", 0)),
            "loses": int(info.get("loses", 0)),
        }
        for tid, info in raw.items()
    ]
    cache.json_save("understat_league_teams", {"league": league, "season": season}, teams)
    return teams


def get_team_shots(team_id: str, season: int) -> pd.DataFrame:
    """Return all shots for a team in a given season."""
    cached = cache.json_get("understat_team_shots", {"team_id": team_id, "season": season}, ttl_hours=12)
    if cached is not None:
        return pd.DataFrame(cached)

    session = _session()
    session.get(f"{API_BASE}/team/{team_id}/{season}", timeout=30)
    resp = session.get(
        f"{API_BASE}/getTeamPlayers/{team_id}/{season}",
        headers={"Referer": f"{API_BASE}/team/{team_id}/{season}"},
        timeout=30,
    )
    resp.raise_for_status()
    players = resp.json() or []
    all_shots = []
    for p in players[:25]:  # cap to avoid rate-limiting
        try:
            pid = str(p.get("id"))
            sub_df = get_player_shots(pid)
            sub_df = sub_df[sub_df["season"] == season]
            all_shots.append(sub_df)
        except Exception as exc:
            logger.warning(f"Shots for player {p.get('id')} failed: {exc}")
    if not all_shots:
        return pd.DataFrame()
    df = pd.concat(all_shots, ignore_index=True)
    cache.json_save("understat_team_shots", {"team_id": team_id, "season": season}, df.to_dict(orient="records"))
    return df


def get_team_xg_history(team_id: str, season: int) -> list[dict]:
    """Return per-match xG for/against for a team in a season."""
    cached = cache.json_get("understat_team_xg_history", {"team_id": team_id, "season": season}, ttl_hours=12)
    if cached is not None:
        return cached

    session = _session()
    session.get(f"{API_BASE}/team/{team_id}/{season}", timeout=30)
    resp = session.get(
        f"{API_BASE}/getTeamResults/{team_id}/{season}",
        headers={"Referer": f"{API_BASE}/team/{team_id}/{season}"},
        timeout=30,
    )
    resp.raise_for_status()
    matches = resp.json() or []
    history = []
    cumulative_xG = 0.0
    cumulative_xGA = 0.0
    for i, m in enumerate(matches, 1):
        home = m.get("h", {})
        away = m.get("a", {})
        is_home = str(home.get("id")) == str(team_id)
        xG = float(m.get("xG", {}).get("h" if is_home else "a", 0))
        xGA = float(m.get("xG", {}).get("a" if is_home else "h", 0))
        cumulative_xG += xG
        cumulative_xGA += xGA
        history.append({
            "match": i,
            "date": m.get("datetime", ""),
            "opponent": away.get("title") if is_home else home.get("title"),
            "xG": round(xG, 3),
            "xGA": round(xGA, 3),
            "cumulative_xG": round(cumulative_xG, 3),
            "cumulative_xGA": round(cumulative_xGA, 3),
            "goals": int(m.get("goals", {}).get("h" if is_home else "a", 0)),
            "goals_against": int(m.get("goals", {}).get("a" if is_home else "h", 0)),
        })
    cache.json_save("understat_team_xg_history", {"team_id": team_id, "season": season}, history)
    return history


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_shot_df(shots: list) -> pd.DataFrame:
    if not shots:
        return pd.DataFrame()
    df = pd.DataFrame(shots)
    for col in ["X", "Y", "xG"]:
        df[col] = pd.to_numeric(df.get(col, pd.Series()), errors="coerce")
    df["season"] = pd.to_numeric(df.get("season", pd.Series()), errors="coerce")
    df = df.dropna(subset=["X", "Y", "xG", "season"])
    df["X"] = df["X"] * 100
    df["Y"] = df["Y"] * 100
    df["season"] = df["season"].astype(int)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "h_a" in df.columns and "h_team" in df.columns and "a_team" in df.columns:
        df["team"] = df.apply(lambda r: r["h_team"] if r["h_a"] == "h" else r["a_team"], axis=1)
    return df.reset_index(drop=True)
