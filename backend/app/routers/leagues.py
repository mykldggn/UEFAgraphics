"""
League / team / player search and metadata endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import fbref_service as fbref
from app.services import understat_service as understat

router = APIRouter(prefix="/leagues", tags=["leagues"])


# ── League list ───────────────────────────────────────────────────────────────

@router.get("")
def list_leagues():
    """Return all supported leagues."""
    return [
        {"id": lid, "label": fbref.LEAGUE_LABELS.get(lid, lid),
         "country": fbref.LEAGUE_COUNTRY.get(lid, "")}
        for lid in fbref.FBREF_LEAGUES
    ]


# ── Teams ─────────────────────────────────────────────────────────────────────

@router.get("/{league_id}/teams")
def get_teams(league_id: str, season: int = Query(..., description="4-digit season start year")):
    if league_id not in fbref.FBREF_LEAGUES:
        raise HTTPException(404, f"Unknown league: {league_id}")
    teams = fbref.get_teams(league_id, season)
    return {"league": league_id, "season": season, "teams": teams}


# ── Player search ─────────────────────────────────────────────────────────────

@router.get("/{league_id}/players/search")
def search_players(
    league_id: str,
    q: str = Query(..., min_length=2),
    season: int = Query(...),
):
    if league_id not in fbref.FBREF_LEAGUES:
        raise HTTPException(404, f"Unknown league: {league_id}")
    results = fbref.search_players_fbref(q, league_id, season)
    return {"query": q, "results": results}


@router.get("/understat/search")
def understat_search(q: str = Query(..., min_length=2)):
    """Cross-league player search via Understat."""
    results = understat.search_players(q)
    return {"query": q, "results": results}


@router.get("/understat/{league}/players")
def understat_players(league: str, season: int = Query(...)):
    """Player list for an Understat league+season."""
    if league not in understat.UNDERSTAT_LEAGUES:
        raise HTTPException(404, f"Unsupported Understat league: {league}. "
                                 f"Supported: {list(understat.UNDERSTAT_LEAGUES)}")
    players = understat.get_league_players(league, season)
    return {"league": league, "season": season, "players": players}


# ── League table ──────────────────────────────────────────────────────────────

@router.get("/{league_id}/table")
def league_table(league_id: str, season: int = Query(...)):
    if league_id not in fbref.FBREF_LEAGUES:
        raise HTTPException(404, f"Unknown league: {league_id}")
    df = fbref.get_league_table(league_id, season)
    if df.empty:
        raise HTTPException(503, "Could not fetch league table")
    return {"league": league_id, "season": season, "table": df.to_dict(orient="records")}


# ── Team xG history (Understat) ───────────────────────────────────────────────

@router.get("/understat/team/{team_id}/xg-history")
def team_xg_history(team_id: str, season: int = Query(...)):
    history = understat.get_team_xg_history(team_id, season)
    return {"team_id": team_id, "season": season, "history": history}
