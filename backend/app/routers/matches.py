"""
Today's football matches across top leagues.
Data from football-data.org free tier (10 req/min, competition-scoped).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from fastapi import APIRouter, Query

from app.services import football_data_service as fdorg
from app.core import cache

router = APIRouter(prefix="/matches", tags=["matches"])

# Top leagues to scan for today's matches (5 to stay within rate limits)
FEATURED = ["UEFA-CL", "UEFA-EL", "ENG-1", "ESP-1", "ITA-1", "DEU-1", "FRA-1"]


def _status_label(m: dict, user_date: str) -> str:
    raw = m.get("status", "")
    if raw in ("IN_PLAY", "PAUSED", "HALFTIME"):
        minute = m.get("minute")
        return f"{minute}'" if minute else "Live"
    if raw == "FINISHED":
        return "FT"
    if raw in ("TIMED", "SCHEDULED"):
        utc = m.get("utcDate", "")
        if utc:
            try:
                dt = datetime.fromisoformat(utc.replace("Z", "+00:00"))
                return dt.strftime("%-I:%M")  # e.g. "3:00"
            except Exception:
                pass
        return "TBD"
    return raw or "—"


@router.get("/today")
def matches_today(match_date: str = Query(None, description="YYYY-MM-DD in user local time")):
    today = match_date or date.today().isoformat()

    ck = {"src": "matches_today", "date": today}
    cached = cache.json_get("matches_today", ck, ttl_hours=0.083)  # 5-min cache
    if cached is not None:
        return cached

    all_matches: list[dict] = []
    for league_id in FEATURED:
        code = fdorg.LEAGUE_CODES.get(league_id)
        if not code:
            continue
        data = fdorg._get(f"competitions/{code}/matches?dateFrom={today}&dateTo={today}")
        if not data:
            continue
        for m in data.get("matches", []):
            score = m.get("score", {})
            ft    = score.get("fullTime", {})
            ht    = score.get("halfTime", {})
            home_s = ft.get("home")
            away_s = ft.get("away")
            # During live match, fullTime shows nulls; use current score from penalties/extra
            if home_s is None:
                home_s = score.get("regularTime", {}).get("home") or score.get("extraTime", {}).get("home")
            if away_s is None:
                away_s = score.get("regularTime", {}).get("away") or score.get("extraTime", {}).get("away")
            status_raw = m.get("status", "")
            all_matches.append({
                "competition":    fdorg.LEAGUE_LABELS.get(league_id, league_id),
                "competitionId":  league_id,
                "homeTeam":       m.get("homeTeam", {}).get("name", ""),
                "homeShort":      m.get("homeTeam", {}).get("shortName") or m.get("homeTeam", {}).get("tla", ""),
                "homeCrest":      m.get("homeTeam", {}).get("crest", ""),
                "homeScore":      home_s,
                "awayTeam":       m.get("awayTeam", {}).get("name", ""),
                "awayShort":      m.get("awayTeam", {}).get("shortName") or m.get("awayTeam", {}).get("tla", ""),
                "awayCrest":      m.get("awayTeam", {}).get("crest", ""),
                "awayScore":      away_s,
                "statusRaw":      status_raw,
                "statusLabel":    _status_label(m, today),
                "isLive":         status_raw in ("IN_PLAY", "PAUSED", "HALFTIME"),
                "isFinished":     status_raw == "FINISHED",
                "utcDate":        m.get("utcDate", ""),
            })

    # Sort: live first, then scheduled by time, then finished
    def _sort_key(m: dict) -> tuple:
        if m["isLive"]:
            return (0, m["utcDate"])
        if not m["isFinished"]:
            return (1, m["utcDate"])
        return (2, m["utcDate"])

    all_matches.sort(key=_sort_key)
    result = {"date": today, "matches": all_matches}
    cache.json_save("matches_today", ck, result)
    return result
