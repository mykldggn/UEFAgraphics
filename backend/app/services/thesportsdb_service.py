"""
TheSportsDB v1 — free, no API key, works from any host including Railway.
Used as a Railway-safe fallback for player search when FotMob is unreachable.

Docs: https://www.thesportsdb.com/api.php
Free API key: "3" (public, rate-limited but sufficient)
"""
from __future__ import annotations

import logging
import requests

from app.core import cache

logger = logging.getLogger(__name__)

BASE = "https://www.thesportsdb.com/api/v1/json/3"

_session: requests.Session | None = None


def _sess() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": "Mozilla/5.0"})
    return _session


def _get(path: str, params: dict | None = None) -> dict | None:
    try:
        resp = _sess().get(f"{BASE}/{path.lstrip('/')}", params=params or {}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug("thesportsdb %s: %s", path, exc)
        return None


# League name mapping — TSDB uses league names, not IDs
# Map our internal ID → TSDB strLeague value
_TSDB_LEAGUE_NAME: dict[str, str] = {
    "ENG-1":    "English Premier League",
    "ENG-2":    "English League Championship",
    "ESP-1":    "Spanish La Liga",
    "DEU-1":    "German Bundesliga",
    "ITA-1":    "Italian Serie A",
    "FRA-1":    "French Ligue 1",
    "NED-1":    "Dutch Eredivisie",
    "PRT-1":    "Portuguese Primeira Liga",
    "BEL-1":    "Belgian First Division A",
    "SCO-1":    "Scottish Premier League",
    "TUR-1":    "Turkish Süper Lig",
    "AUS-1":    "Australian A-League",
    "UEFA-CL":  "UEFA Champions League",
    "UEFA-EL":  "UEFA Europa League",
}


def search_players(name: str, league_id: str | None = None) -> list[dict]:
    """
    Search TheSportsDB for players by name.
    Returns list of {id, name, team, pos, source='tsdb'}.
    Results cached 24 h.
    """
    ck = {"q": name.lower().strip(), "league": league_id or ""}
    cached = cache.json_get("tsdb_player_search", ck, ttl_hours=24)
    if cached is not None:
        return cached

    raw = _get("searchplayers.php", {"p": name})
    players_raw = (raw or {}).get("player") or []

    target_league = _TSDB_LEAGUE_NAME.get(league_id or "") if league_id else None
    results: list[dict] = []

    for p in players_raw:
        # Optional league filter — TSDB returns a strLeague field
        if target_league:
            p_league = p.get("strLeague", "") or ""
            if target_league.lower() not in p_league.lower() and p_league.lower() not in target_league.lower():
                continue  # skip players from other leagues
        results.append({
            "id":     str(p.get("idPlayer", "")),
            "name":   p.get("strPlayer", ""),
            "team":   p.get("strTeam", ""),
            "pos":    _map_position(p.get("strPosition", "")),
            "source": "tsdb",
        })

    cache.json_save("tsdb_player_search", ck, results)
    return results[:20]


def _map_position(tsdb_pos: str) -> str:
    """Normalise TSDB position string to a short label."""
    p = (tsdb_pos or "").lower()
    if "goalkeeper" in p or "keeper" in p:
        return "GK"
    if "defender" in p or "back" in p or "centre-back" in p:
        return "DEF"
    if "midfielder" in p or "midfield" in p:
        return "MID"
    if "forward" in p or "striker" in p or "winger" in p or "attacker" in p:
        return "FWD"
    return tsdb_pos[:3].upper() if tsdb_pos else ""
