"""
ESPN public API — no key required, standard HTTPS, Railway-safe.
Used for current-season match lineup + formation data for Most Played XI.

Base URL: https://site.api.espn.com/apis/site/v2/sports/soccer

Returns real position labels (LB, RB, CD, CM, DM, LM, RM, LF, RF, F, G)
which correctly distinguish DMs like Rice from defenders like Timber.
"""
from __future__ import annotations

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

# ESPN position abbreviation → our position category
# Detailed positions let us correctly classify DM, LM, RM as MID etc.
_POS_MAP: dict[str, str] = {
    "G":    "GK",
    "GK":   "GK",
    # Defenders
    "D":    "DEF",
    "CB":   "DEF",
    "CD":   "DEF",
    "CD-L": "DEF",
    "CD-R": "DEF",
    "LB":   "DEF",
    "RB":   "DEF",
    "LWB":  "DEF",
    "RWB":  "DEF",
    "SW":   "DEF",
    # Midfielders — all mid variants go here
    "M":    "MID",
    "CM":   "MID",
    "DM":   "MID",
    "LM":   "MID",
    "RM":   "MID",
    "AM":   "MID",
    "CAM":  "MID",
    "CDM":  "MID",
    # Forwards
    "F":    "FWD",
    "LF":   "FWD",
    "RF":   "FWD",
    "CF":   "FWD",
    "ST":   "FWD",
    "LW":   "FWD",
    "RW":   "FWD",
    "SS":   "FWD",
}

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


def get_event_lineup(event_id: str, team_name: str, league_slug: str) -> dict | None:
    """
    Return lineup for one team in a match.
    Shape: {"formation": "4-3-3", "players": [{"name": "Rice", "pos": "MID"}, ...]}
    Cached indefinitely (past matches don't change).
    """
    ck = {"event_id": event_id}
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
        name = p.get("athlete", {}).get("displayName", "")
        pos_abbr = p.get("position", {}).get("abbreviation", "")
        pos = _POS_MAP.get(pos_abbr, "MID")
        players.append({"name": name, "pos": pos})

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
        for p in lineup.get("players", []):
            name = p.get("name", "")
            last = name.split()[-1].lower() if name else ""
            pos  = p.get("pos", "")
            if last and pos:
                pos_votes[last].append(pos)

    if not pos_votes:
        return None, None

    pos_hints = {k: Counter(v).most_common(1)[0][0] for k, v in pos_votes.items()} or None
    formation = formations.most_common(1)[0][0] if formations else None

    return pos_hints, formation
