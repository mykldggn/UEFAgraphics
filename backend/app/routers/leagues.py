"""
League / team / player search and metadata endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import fbref_service as fbref
from app.services import understat_service as understat

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("")
def list_leagues():
    return [
        {"id": lid, "label": fbref.LEAGUE_LABELS.get(lid, lid),
         "country": fbref.LEAGUE_COUNTRY.get(lid, "")}
        for lid in fbref.LEAGUE_LABELS
    ]


@router.get("/{league_id}/teams")
def get_teams(league_id: str, season: int = Query(...)):
    if league_id not in fbref.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")
    teams = fbref.get_teams(league_id, season)
    return {"league": league_id, "season": season, "teams": teams}


@router.get("/{league_id}/players/search")
def search_players(
    league_id: str,
    q: str = Query(..., min_length=2),
    season: int = Query(...),
):
    if league_id not in fbref.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")
    results = fbref.search_players(q, league_id, season)
    return {"query": q, "results": results}


@router.get("/understat/search")
def understat_search(q: str = Query(..., min_length=2)):
    results = understat.search_players(q)
    return {"query": q, "results": results}


@router.get("/understat/{league}/players")
def understat_players(league: str, season: int = Query(...)):
    if league not in understat.UNDERSTAT_LEAGUES:
        raise HTTPException(404, f"Unsupported Understat league: {league}")
    players = understat.get_league_players(league, season)
    return {"league": league, "season": season, "players": players}


@router.get("/{league_id}/table")
def league_table(league_id: str, season: int = Query(...)):
    if league_id not in fbref.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")
    table = fbref.get_league_table(league_id, season)
    if not table:
        raise HTTPException(503, "Could not fetch league table — FBref may be temporarily unavailable")
    return {"league": league_id, "season": season, "table": table}


@router.get("/understat/team/{team_id}/xg-history")
def team_xg_history(team_id: str, season: int = Query(...)):
    history = understat.get_team_xg_history(team_id, season)
    return {"team_id": team_id, "season": season, "history": history}
