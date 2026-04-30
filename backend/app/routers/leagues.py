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
from app.services import fotmob_service as fotmob

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
    q: str      = Query(..., min_length=2),
    season: int = Query(...),
):
    if league_id not in fdorg.LEAGUE_LABELS:
        raise HTTPException(404, f"Unknown league: {league_id}")

    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if us_slug:
        players = understat.get_league_players(us_slug, season)
        q_lower = q.lower()
        results = [p for p in players if q_lower in p["name"].lower()][:20]
        return {"query": q, "results": results, "source": "understat"}

    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id)
    if fm_league_id:
        # Search within the cached league player pool (fast, no extra requests)
        pool    = fotmob.get_league_player_stats(fm_league_id, season)
        q_lower = q.lower()
        results = [
            {"id": p["id"], "name": p["player"], "team": p["team"], "source": "fotmob"}
            for p in pool if q_lower in p["player"].lower()
        ][:20]
        # If pool search comes up short try FotMob suggest endpoint
        if not results:
            hits = fotmob.search_players_fotmob(q, fm_league_id)
            results = [{**h, "source": "fotmob"} for h in hits][:20]
        return {"query": q, "results": results, "source": "fotmob"}

    # Last resort: global Understat search
    results = understat.search_players(q)
    return {"query": q, "results": results, "source": "understat"}


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


@router.get("/{league_id}/position-history")
def league_position_history(league_id: str, season: int = Query(...)):
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if us_slug:
        result = understat.get_league_position_history(us_slug, season)
        if not result:
            raise HTTPException(503, "Could not load position history")
        return {"league": league_id, "season": season, **result}

    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id)
    if fm_league_id:
        result = fotmob.get_league_position_history(fm_league_id, season)
        if not result:
            raise HTTPException(503, "Could not load position history")
        return {"league": league_id, "season": season, **result}

    raise HTTPException(400, "Position history not available for this league")


@router.get("/{league_id}/leaders")
def league_leaders(league_id: str, season: int = Query(...)):
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if us_slug:
        result = understat.get_league_leaders(us_slug, season)
        if not result:
            raise HTTPException(503, "Could not load league leaders")
        return {"league": league_id, "season": season, **result}

    # FotMob — full stats pool available
    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id)
    if fm_league_id:
        pool = fotmob.get_league_player_stats(fm_league_id, season)
        if pool:
            def top(key: str, n: int = 10) -> list[dict]:
                return [
                    {"player": p["player"], "team": p["team"],
                     "value": round(float(p.get(key, 0) or 0), 2)}
                    for p in sorted(
                        [p for p in pool if float(p.get(key, 0) or 0) > 0],
                        key=lambda p: float(p.get(key, 0) or 0), reverse=True,
                    )[:n]
                ]
            return {
                "league":     league_id,
                "season":     season,
                "goals":      top("goals"),
                "assists":    top("assists"),
                "xg":         top("xg"),
                "key_passes": top("key_passes"),
                "shots":      top("shots"),
            }

    # Last resort: fdorg top scorers (goals + assists only)
    scorers = fdorg.get_top_scorers(league_id, season, limit=20)
    if not scorers:
        raise HTTPException(503, "No leader data available for this league")
    return {
        "league": league_id,
        "season": season,
        "goals": [
            {"player": s["player"], "team": s["team"], "value": s["goals"]}
            for s in scorers if s.get("goals", 0) > 0
        ],
        "assists": sorted(
            [{"player": s["player"], "team": s["team"], "value": s["assists"]}
             for s in scorers if s.get("assists", 0) > 0],
            key=lambda x: x["value"], reverse=True
        ),
        "xg": [], "key_passes": [], "shots": [],
    }


@router.get("/{league_id}/team-meta")
def get_team_meta(league_id: str, team_name: str = Query(...), season: int = Query(default=2024)):
    """Return crest, venue, founded for a named team within a league."""
    teams = fdorg.get_teams(league_id, season)
    name_lower = team_name.lower()
    match = next(
        (t for t in teams if t["name"].lower() == name_lower
         or t.get("short", "").lower() == name_lower
         or name_lower in t["name"].lower()),
        None,
    )
    if not match:
        return {"crest": None, "venue": None, "founded": None, "address": None}
    return {
        "crest":   match.get("crest"),
        "venue":   match.get("venue"),
        "founded": match.get("founded"),
        "address": match.get("address"),
    }


@router.get("/{league_id}/team-colors")
def get_team_colors(league_id: str, season: int = Query(default=2024)):
    """Return {teamName: hexColor} for a league's teams."""
    from app.viz.common import team_color
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    teams: list[str] = []
    if us_slug:
        us_teams = understat.get_league_teams(us_slug, season)
        teams = [t["name"] for t in us_teams]
    else:
        fdorg_teams = fdorg.get_teams(league_id, season)
        teams = [t["name"] for t in fdorg_teams]
    return {t: team_color(t) for t in teams}


@router.get("/understat/team/{team_id}/xg-history")
def team_xg_history(team_id: str, season: int = Query(...)):
    history = understat.get_team_xg_history(team_id, season)
    return {"team_id": team_id, "season": season, "history": history}
