"""
Transfermarkt community API — no auth, free.
Primary position source for Most Played XI (more reliable than Understat/ESPN
for correct GK/DEF/MID/FWD classification and sub-position labels).

Search returns top-level `position` string (e.g. "Defensive Midfield").
Profile returns `position.main` — only fetched when search gives a vague label.
Results are cached 30 days; positions don't change mid-season.
"""
from __future__ import annotations

import logging
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from app.core import cache

logger = logging.getLogger(__name__)

BASE = "https://transfermarkt-api.fly.dev"

# Transfermarkt position label → ESPN-compatible abbreviation (matches _ESPN_CAT in lineup_card)
TM_TO_ABBR: dict[str, str] = {
    "Goalkeeper":          "GK",
    "Centre-Back":         "CB",
    "Left-Back":           "LB",
    "Right-Back":          "RB",
    "Left Wing-Back":      "LWB",
    "Right Wing-Back":     "RWB",
    "Sweeper":             "CB",
    "Defensive Midfield":  "CDM",
    "Central Midfield":    "CM",
    "Right Midfield":      "RM",
    "Left Midfield":       "LM",
    "Attacking Midfield":  "CAM",
    "Left Winger":         "LW",
    "Right Winger":        "RW",
    "Second Striker":      "SS",
    "Centre-Forward":      "CF",
    # Generic labels — only returned when TM can't determine sub-position
    "Midfield":            "CM",
    "Midfielder":          "CM",
    "Defence":             "CB",
    "Defender":            "CB",
    "Attack":              "CF",
    "Attacker":            "CF",
    "Forward":             "CF",
}

_VAGUE = {"Midfield", "Midfielder", "Defence", "Defender", "Attack", "Attacker", "Forward"}

_session: requests.Session | None = None


def _sess() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })
    return _session


def _norm(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()


def _get(path: str) -> dict | None:
    try:
        resp = _sess().get(f"{BASE}/{path.lstrip('/')}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug("transfermarkt_api %s: %s", path, exc)
        return None


def _best_result(results: list[dict], name: str) -> dict | None:
    if not results:
        return None
    name_lo = _norm(name)
    last    = name_lo.split()[-1] if name_lo else ""
    for r in results:
        r_name = _norm(str(r.get("name", "")))
        r_last = r_name.split()[-1] if r_name else ""
        if name_lo == r_name or last == r_last:
            return r
        if name_lo in r_name or r_name in name_lo:
            return r
    return results[0]


def _fetch_position(name: str) -> str | None:
    """
    Return a Transfermarkt position label for a player name.
    Tries search first; fetches profile only when search returns a vague label.
    """
    import urllib.parse
    data = _get(f"players/search/{urllib.parse.quote(name)}")
    if not data:
        return None

    result = _best_result(data.get("results", []), name)
    if not result:
        return None

    pos = str(result.get("position") or "").strip()

    if pos in _VAGUE and result.get("id"):
        profile = _get(f"players/{result['id']}/profile")
        if profile:
            pos_obj = profile.get("position") or {}
            pos = str(pos_obj.get("main") or pos).strip()

    return pos or None


def get_player_abbr(name: str) -> str | None:
    """
    Return ESPN-compatible position abbreviation for a player name.
    E.g. "Martin Zubimendi" → "CDM", "Gabriel Magalhaes" → "CB".
    Cached 30 days per player.
    """
    ck = {"type": "tm_pos", "name": name.lower().strip(), "v": 1}
    cached = cache.json_get("transfermarkt", ck, ttl_hours=24 * 30)
    if cached is not None:
        return cached.get("abbr")

    pos = _fetch_position(name)
    abbr = TM_TO_ABBR.get(pos) if pos else None

    cache.json_save("transfermarkt", ck, {"abbr": abbr})
    return abbr


def get_team_position_hints(player_names: list[str]) -> dict[str, str] | None:
    """
    Batch-lookup positions for a list of player names (parallelised).
    Returns {last_name_lower: abbr} in the same format as ESPN pos_hints,
    or None if no results at all.
    """
    hints: dict[str, str] = {}

    def _lookup(name: str) -> tuple[str, str | None]:
        return name, get_player_abbr(name)

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_lookup, n): n for n in player_names if n}
        for fut in as_completed(futures):
            name, abbr = fut.result()
            if abbr:
                full = _norm(name) if name else ""
                last = _norm(name.split()[-1]) if name else ""
                if full:
                    hints[full] = abbr
                if last:
                    hints[last] = abbr

    return hints or None
