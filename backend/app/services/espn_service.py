"""
ESPN public API — no key required, standard HTTPS, Railway-safe.
Used for current-season match lineup + formation data for Most Played XI.

Base URL: https://site.api.espn.com/apis/site/v2/sports/soccer

Returns real position labels (LB, RB, CD, CM, DM, LM, RM, LF, RF, F, G)
which correctly distinguish DMs like Rice from defenders like Timber.
"""
from __future__ import annotations

import html
import logging
from collections import Counter, defaultdict

import requests

from app.core import cache

logger = logging.getLogger(__name__)

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Internal league ID → ESPN league slug
ESPN_LEAGUES: dict[str, str] = {
    "ENG-1": "eng.1",
    "ENG-2": "eng.2",
    "ENG-3": "eng.3",
    "ENG-4": "eng.4",
    "ESP-1": "esp.1",
    "DEU-1": "ger.1",
    "DEU-2": "ger.2",
    "ITA-1": "ita.1",
    "FRA-1": "fra.1",
    "NED-1": "ned.1",
    "PRT-1": "por.1",
    "SCO-1": "sco.prem",
    "BEL-1": "bel.1",
    "TUR-1": "tur.1",
}

import unicodedata

def _normalize(s: str) -> str:
    """Normalize Unicode to ASCII for name matching (ø→o, é→e, ü→u etc.)"""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()

_session: requests.Session | None = None


def _sess() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    return _session


def _get(path: str, params: dict | None = None):
    try:
        resp = _sess().get(f"{BASE}/{path.lstrip('/')}", params=params or {}, timeout=12)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("espn GET %s: %s", path, exc)
        return None


def get_espn_team_id(team_name: str, league_slug: str) -> str | None:
    """
    Resolve ESPN team ID from team name. Cached 30 days.
    """
    ck = {"team": team_name.lower().strip(), "league": league_slug}
    cached = cache.json_get("espn_team_id", ck, ttl_hours=24 * 30)
    if cached is not None:
        return cached.get("team_id")

    data = _get(f"{league_slug}/teams")
    if not data:
        return None

    teams = (data.get("sports", [{}])[0]
                 .get("leagues", [{}])[0]
                 .get("teams", []))

    name_lo = team_name.lower().strip()
    best_id = None
    for entry in teams:
        t = entry.get("team", {})
        t_name = (t.get("displayName") or "").lower()
        t_short = (t.get("shortDisplayName") or "").lower()
        if name_lo in t_name or t_name in name_lo or name_lo in t_short or t_short in name_lo:
            best_id = str(t["id"])
            break

    if best_id:
        cache.json_save("espn_team_id", ck, {"team_id": best_id})
    return best_id


def get_recent_event_ids(espn_team_id: str, league_slug: str, last: int = 8) -> list[str]:
    """
    Get the most recent completed event IDs for a team.
    Cached 6 h.
    """
    ck = {"team_id": espn_team_id, "league": league_slug, "last": last}
    cached = cache.json_get("espn_fixtures", ck, ttl_hours=6)
    if cached is not None:
        return cached

    data = _get(f"{league_slug}/teams/{espn_team_id}/schedule")
    if not data:
        return []

    events = data.get("events", [])
    completed = [
        e for e in events
        if e.get("competitions", [{}])[0]
              .get("status", {})
              .get("type", {})
              .get("completed", False)
    ]
    ids = [e["id"] for e in completed[-last:] if e.get("id")]
    cache.json_save("espn_fixtures", ck, ids)
    return ids


def _derive_pos(formation: str, place: int | None, espn_abbr: str) -> str:
    """
    Combine ESPN formationPlace (1-11) + formation string to produce a precise
    position label for multi-layer formations.

    - GK / DEF / FWD layers: return espn_abbr unchanged (keep LB/RB/CB/LW/CF/RW).
    - First mid layer in a multi-layer formation (4-2-3-1, 4-1-4-1, 3-4-3 etc.):
      always return "DM" regardless of what ESPN generically calls it.
    - Subsequent mid layers: return ESPN lateral tag (LM/RM/CAM/AM) when specific,
      otherwise "AM".
    - Single-layer formations (4-3-3, 3-5-2): return espn_abbr unchanged.
    """
    if not place or not formation:
        return espn_abbr
    try:
        parts = [int(x) for x in formation.split("-") if x.strip().isdigit()]
    except (ValueError, AttributeError):
        return espn_abbr
    if not parts or sum(parts) != 10:
        return espn_abbr

    if place == 1:
        return espn_abbr  # GK

    idx = place - 2  # 0-based among outfield players

    if idx < parts[0]:
        return espn_abbr  # DEF layer: keep LB/RB/CB etc.
    idx -= parts[0]

    mid_parts = parts[1:-1] if len(parts) > 2 else []
    if not mid_parts:
        return espn_abbr  # Single mid layer (4-3-3): keep as-is

    # Multi-layer mid: first layer = DM, rest = AM
    if idx < mid_parts[0]:
        return "DM"
    idx -= mid_parts[0]

    _lateral = {"LM", "RM", "CAM", "AM", "LW", "RW"}
    for layer_count in mid_parts[1:]:
        if idx < layer_count:
            return espn_abbr if espn_abbr in _lateral else "AM"
        idx -= layer_count

    return espn_abbr  # FWD layer: keep LW/CF/RW


def get_event_lineup(event_id: str, team_name: str, league_slug: str) -> dict | None:
    """
    Return lineup for one team in a match.
    Shape: {"formation": "4-3-3", "players": [{"name": "Rice", "pos": "MID"}, ...]}
    Cached indefinitely (past matches don't change).
    """
    ck = {"event_id": event_id, "v": 3}
    cached = cache.json_get("espn_lineup", ck, ttl_hours=24 * 365)
    if cached is not None:
        return _pick_team(cached, team_name)

    data = _get(f"{league_slug}/summary", {"event": event_id})
    if not data:
        return None

    rosters = data.get("rosters", [])
    cache.json_save("espn_lineup", ck, rosters)
    return _pick_team(rosters, team_name)


def _pick_team(rosters: list, team_name: str) -> dict | None:
    name_lo = team_name.lower().strip()
    best = None
    for r in rosters:
        t_name = (r.get("team", {}).get("displayName") or "").lower()
        if name_lo in t_name or t_name in name_lo:
            best = r
            break
    if best is None and rosters:
        best = rosters[0]
    if not best:
        return None

    formation = best.get("formation") or ""
    players = []
    for p in best.get("roster", []):
        if not p.get("starter"):
            continue
        name = html.unescape(p.get("athlete", {}).get("displayName", ""))
        pos_abbr = p.get("position", {}).get("abbreviation", "")
        place = p.get("formationPlace")
        players.append({"name": name, "pos": pos_abbr, "place": place})

    return {"formation": formation, "players": players}


def get_team_lineup_hints(
    team_name: str,
    internal_league_id: str,
    season: int,
    num_matches: int = 8,
) -> tuple[dict[str, str] | None, str | None]:
    """
    Aggregate lineup data across recent matches.
    Returns (pos_hints, formation_str).

    pos_hints — {last_name_lower: most_common_position "GK"/"DEF"/"MID"/"FWD"}
    formation — most common formation string e.g. "4-3-3"

    Returns (None, None) if no ESPN data available for this league.
    """
    league_slug = ESPN_LEAGUES.get(internal_league_id)
    if not league_slug:
        return None, None

    espn_team_id = get_espn_team_id(team_name, league_slug)
    if not espn_team_id:
        logger.debug("espn: could not resolve team ID for %s", team_name)
        return None, None

    event_ids = get_recent_event_ids(espn_team_id, league_slug, last=num_matches)
    if not event_ids:
        return None, None

    pos_votes: dict[str, list[str]] = defaultdict(list)
    formations: Counter = Counter()

    for eid in event_ids:
        lineup = get_event_lineup(eid, team_name, league_slug)
        if not lineup:
            continue
        if lineup.get("formation"):
            formations[lineup["formation"]] += 1
        match_formation = lineup.get("formation", "")
        for p in lineup.get("players", []):
            name = p.get("name", "")
            # Normalize to ASCII so "Ødegaard" → "odegaard" matches Understat "Odegaard"
            last = _normalize(name.split()[-1]) if name else ""
            pos  = _derive_pos(match_formation, p.get("place"), p.get("pos", ""))
            if last and pos:
                pos_votes[last].append(pos)

    if not pos_votes:
        return None, None

    pos_hints = {k: Counter(v).most_common(1)[0][0] for k, v in pos_votes.items()} or None
    formation = formations.most_common(1)[0][0] if formations else None

    return pos_hints, formation
