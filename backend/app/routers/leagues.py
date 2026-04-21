"""
League / team / player search and metadata endpoints.

Data sources:
- Standings + teams:  football-data.org (free key, no daily limit)
- Understat leagues:  understat_service (no key, no limit)
- Player search:      understat_service
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import football_data_service as fdorg
from app.services import understat_service as understat

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("")
def list_leagues():
    return [
        {"id": lid, "label": fdorg.LEAGUE_LABELS.get(lid, lid),
         "country": fdorg.LEAGUE_COUNTRY.get(lid, "")}
        for lid in fdorg.LEAGUE_LABELS
    ]


@router.get("/{league_id}/teams")
def get_teams(league_id: str, season: int = Query(...)):
    if league_id not in fdorg.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")

    # Try football-data.org first; fall back to Understat team list
    teams = fdorg.get_teams(league_id, season)
    if not teams:
        us_slug = understat.LEAGUE_TO_US.get(league_id)
        if us_slug:
            us_teams = understat.get_league_teams(us_slug, season)
            teams = [{"id": t["id"], "name": t["name"]} for t in us_teams]

    return {"league": league_id, "season": season, "teams": teams}


@router.get("/{league_id}/players/search")
def search_players(
    league_id: str,
    q: str    = Query(..., min_length=2),
    season: int = Query(...),
):
    if league_id not in fdorg.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")

    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if us_slug:
        players = understat.get_league_players(us_slug, season)
        q_lower  = q.lower()
        results  = [p for p in players if q_lower in p["name"].lower()][:20]
    else:
        results = understat.search_players(q)

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
    if league_id not in fdorg.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")

    table = fdorg.get_standings(league_id, season)

    # Fallback: build table from Understat for older seasons or non-fdorg leagues
    if not table:
        us_slug = understat.LEAGUE_TO_US.get(league_id)
        if us_slug:
            us_teams = understat.get_league_teams(us_slug, season)
            if us_teams:
                sorted_teams = sorted(us_teams, key=lambda t: t.get("pts", 0), reverse=True)
                table = [
                    {
                        "rank":          i + 1,
                        "team":          t["name"],
                        "team_id":       t["id"],
                        "played":        t.get("wins", 0) + t.get("draws", 0) + t.get("loses", 0),
                        "wins":          t.get("wins", 0),
                        "draws":         t.get("draws", 0),
                        "losses":        t.get("loses", 0),
                        "goals_for":     t.get("goals_for", 0),
                        "goals_against": t.get("goals_against", 0),
                        "goal_diff":     t.get("goals_for", 0) - t.get("goals_against", 0),
                        "points":        t.get("pts", 0),
                        "form":          t.get("form", ""),
                    }
                    for i, t in enumerate(sorted_teams)
                ]

    if not table:
        raise HTTPException(503, "League table unavailable for this season")
    return {"league": league_id, "season": season, "table": table}


@router.get("/understat/team/{team_id}/xg-history")
def team_xg_history(team_id: str, season: int = Query(...)):
    history = understat.get_team_xg_history(team_id, season)
    return {"team_id": team_id, "season": season, "history": history}
