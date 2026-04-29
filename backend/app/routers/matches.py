"""
Today's football matches.
Tries FotMob first (200+ leagues, live minute, crests).
Falls back to football-data.org if FotMob returns nothing.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from fastapi import APIRouter, Query

from app.services import fotmob_service as fotmob
from app.services import football_data_service as fdorg
from app.core import cache

router = APIRouter(prefix="/matches", tags=["matches"])

FDORG_LEAGUES = ["UEFA-CL", "UEFA-EL", "ENG-1", "ESP-1", "ITA-1", "DEU-1", "FRA-1"]


def _fdorg_matches(today_iso: str) -> list[dict]:
    """Fallback: pull today's matches from football-data.org."""
    all_matches: list[dict] = []
    for league_id in FDORG_LEAGUES:
        code = fdorg.LEAGUE_CODES.get(league_id)
        if not code:
            continue
        data = fdorg._get(f"competitions/{code}/matches?dateFrom={today_iso}&dateTo={today_iso}")
        if not data:
            continue
        for m in data.get("matches", []):
            score    = m.get("score", {})
            ft       = score.get("fullTime", {})
            home_s   = ft.get("home")
            away_s   = ft.get("away")
            if home_s is None:
                home_s = (score.get("regularTime", {}) or {}).get("home")
            if away_s is None:
                away_s = (score.get("regularTime", {}) or {}).get("away")
            status_raw = m.get("status", "")
            is_live    = status_raw in ("IN_PLAY", "PAUSED", "HALFTIME")
            is_done    = status_raw == "FINISHED"
            minute     = m.get("minute")

            try:
                utc = m.get("utcDate", "")
                ko  = datetime.fromisoformat(utc.replace("Z", "+00:00")).strftime("%H:%M") if utc else ""
            except Exception:
                ko = ""

            home = m.get("homeTeam", {})
            away = m.get("awayTeam", {})
            all_matches.append({
                "id":            m.get("id"),
                "leagueName":    fdorg.LEAGUE_LABELS.get(league_id, league_id),
                "leagueId":      0,
                "leagueShort":   league_id,
                "homeTeam":      home.get("name", ""),
                "awayTeam":      away.get("name", ""),
                "homeTeamId":    home.get("id"),
                "awayTeamId":    away.get("id"),
                "homeTeamCrest": home.get("crest", ""),
                "awayTeamCrest": away.get("crest", ""),
                "homeScore":     home_s,
                "awayScore":     away_s,
                "status":        f"{minute}'" if is_live and minute else ("FT" if is_done else ko),
                "minute":        f"{minute}'" if minute else "",
                "isLive":        is_live,
                "isFinished":    is_done,
                "scorers":       [],
            })

    def _sort(m: dict) -> int:
        if m["isLive"]:     return 0
        if m["isFinished"]: return 2
        return 1
    all_matches.sort(key=_sort)
    return all_matches


@router.get("/today")
def matches_today(match_date: str = Query(None, description="YYYYMMDD or YYYY-MM-DD")):
    # Normalise formats
    raw      = match_date or date.today().isoformat()
    today_fm = raw.replace("-", "")                              # YYYYMMDD for FotMob
    today_iso = f"{today_fm[:4]}-{today_fm[4:6]}-{today_fm[6:]}"  # YYYY-MM-DD for fdorg

    ck = {"src": "matches_today_v2", "date": today_fm}
    cached = cache.json_get("matches_today", ck, ttl_hours=0.033)  # 2-min cache
    if cached is not None:
        return cached

    # Try FotMob first
    matches = fotmob.get_today_matches(today_fm)

    # Fallback to football-data.org if FotMob returned nothing
    if not matches:
        matches = _fdorg_matches(today_iso)

    result = {"date": today_iso, "matches": matches}
    cache.json_save("matches_today", ck, result)
    return result
