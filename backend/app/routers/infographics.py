"""
Infographic generation endpoints.
All return PNG bytes with Content-Type: image/png.
"""
from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core import cache
from app.services import api_football_service as apif
from app.services import understat_service as understat
from app.viz import (
    shotmap,
    radar as radar_viz,
    summary_card,
    career_xg as career_xg_viz,
    team_xg_timeline,
    team_season_card as team_card_viz,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/infographics", tags=["infographics"])

PNG = "image/png"


def _png(data: bytes) -> Response:
    return Response(content=data, media_type=PNG)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER  (Understat — shot data)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/shotmap")
def player_shotmap(
    player_id: str,
    season: int = Query(..., description="Season start year, e.g. 2023"),
):
    cache_key = {"type": "shotmap", "player_id": player_id, "season": season}
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    try:
        shots = understat.get_player_shots(player_id)
        meta  = understat.get_player_meta(player_id)
    except Exception as exc:
        logger.error(f"shotmap {player_id}/{season}: {exc}")
        raise HTTPException(503, "Failed to fetch shot data")

    df           = shots[shots["season"] == season] if not shots.empty else shots
    season_label = f"{season}/{str(season + 1)[-2:]}"
    png          = shotmap.render(df, meta.get("name", player_id), season_label)
    cache.img_save("infographic", cache_key, png)
    return _png(png)


@router.get("/player/{player_id}/career-xg")
def player_career_xg(
    player_id: str,
    seasons: str = Query(None, description="Comma-separated season years, e.g. 2022,2023"),
):
    season_list = [int(s) for s in seasons.split(",")] if seasons else None
    cache_key   = {"type": "career_xg", "player_id": player_id, "seasons": seasons or "all"}
    cached      = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    try:
        shots = understat.get_player_shots(player_id)
        meta  = understat.get_player_meta(player_id)
    except Exception as exc:
        logger.error(f"career_xg {player_id}: {exc}")
        raise HTTPException(503, "Failed to fetch shot data")

    png = career_xg_viz.render(meta.get("name", player_id), shots, seasons=season_list)
    cache.img_save("infographic", cache_key, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER  (API-Football — stats-based charts)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/radar")
def player_radar(
    player_id: str,
    league_id: str = Query(...),
    season: int = Query(...),
    position: str = Query("FW"),
    compare_id: str = Query(None),
):
    """Radar / pizza chart using API-Football percentiles."""
    cache_key = {
        "type": "radar", "player_id": player_id,
        "league_id": league_id, "season": season,
        "position": position, "compare": compare_id or "",
    }
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    all_players = apif.get_league_player_stats(league_id, season)
    if not all_players:
        raise HTTPException(503, "Could not load player stats — check API key")

    player_stats = apif.get_player_stats(player_id, season)
    if not player_stats:
        raise HTTPException(404, f"No stats found for player {player_id}")

    params = radar_viz.POSITION_PARAMS.get(position[:2], radar_viz.ATTACKER_PARAMS)
    percentiles, raw = _compute_percentiles(all_players, player_stats, params)

    compare_pcts = None
    if compare_id:
        comp_stats = apif.get_player_stats(compare_id, season)
        if comp_stats:
            compare_pcts, _ = _compute_percentiles(all_players, comp_stats, params)

    season_label = f"{season}/{str(season + 1)[-2:]}"
    png = radar_viz.render(
        player_name=player_stats.get("player", player_id),
        position=position,
        season_label=season_label,
        percentiles=percentiles,
        raw_values=raw,
        team=player_stats.get("team", ""),
        compare_name=player_stats.get("player") if compare_id else None,
        compare_percentiles=compare_pcts,
    )
    cache.img_save("infographic", cache_key, png)
    return _png(png)


@router.get("/player/{player_id}/summary-card")
def player_summary_card(
    player_id: str,
    season: int = Query(...),
    position: str = Query("FW"),
):
    cache_key = {"type": "summary_card", "player_id": player_id, "season": season}
    cached    = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    stats = apif.get_player_stats(player_id, season)
    if not stats:
        raise HTTPException(404, f"No stats found for player {player_id}")

    season_label = f"{season}/{str(season + 1)[-2:]}"
    png = summary_card.render(
        player_name=stats["player"],
        position=position,
        team=stats.get("team", ""),
        season_label=season_label,
        stats=stats,
        league_label="",
        nationality=stats.get("nationality", ""),
        age=stats.get("age", ""),
    )
    cache.img_save("infographic", cache_key, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# TEAM
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/team/{team_id}/xg-timeline")
def team_xg_timeline_img(
    team_id: str,
    team_name: str = Query(...),
    season: int = Query(...),
):
    cache_key = {"type": "team_xg_timeline", "team_id": team_id, "season": season}
    cached    = cache.img_get("infographic", cache_key, ttl_hours=12)
    if cached:
        return _png(cached)

    try:
        history = understat.get_team_xg_history(team_id, season)
    except Exception as exc:
        logger.error(f"team xg timeline {team_id}/{season}: {exc}")
        raise HTTPException(503, "Failed to fetch team xG history")

    season_label = f"{season}/{str(season + 1)[-2:]}"
    png = team_xg_timeline.render(team_name, season_label, history)
    cache.img_save("infographic", cache_key, png)
    return _png(png)


@router.get("/team/{team_id}/season-card")
def team_season_card(
    team_id: str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season: int = Query(...),
):
    cache_key = {"type": "team_season_card", "team_id": team_id, "season": season}
    cached    = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    table = apif.get_league_table(league_id, season)
    team_row = next((r for r in table if str(r.get("team_id")) == str(team_id)), None)

    stats: dict = {}
    pos_history: list[dict] = []
    if team_row:
        stats = {
            "wins":          team_row.get("wins"),
            "draws":         team_row.get("draws"),
            "losses":        team_row.get("losses"),
            "goals_for":     team_row.get("goals_for"),
            "goals_against": team_row.get("goals_against"),
            "goal_diff":     team_row.get("goal_diff"),
            "points":        team_row.get("points"),
            "final_position": team_row.get("rank"),
        }
        rank = team_row.get("rank", 1)
        pos_history = [{"matchday": 1, "position": rank},
                       {"matchday": 38, "position": rank}]

    league_label = apif.LEAGUE_LABELS.get(league_id, league_id)
    season_label = f"{season}/{str(season + 1)[-2:]}"

    # Top scorers from Understat (best-effort)
    top_scorers: list[dict] = []
    try:
        us_shots = understat.get_team_shots(team_id, season)
        if not us_shots.empty and "player" in us_shots.columns:
            grp = (
                us_shots[us_shots["result"] == "Goal"]
                .groupby("player")
                .agg(goals=("result", "count"), xG=("xG", "sum"))
                .reset_index()
                .nlargest(8, "goals")
            )
            top_scorers = grp.to_dict(orient="records")
    except Exception:
        pass

    png = team_card_viz.render(
        team_name=team_name,
        season_label=season_label,
        league_label=league_label,
        position_history=pos_history,
        stats=stats,
        top_scorers=top_scorers,
    )
    cache.img_save("infographic", cache_key, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_percentiles(
    all_players: list[dict],
    player: dict,
    params: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    import numpy as np

    percentiles: dict[str, float] = {}
    raw:         dict[str, float] = {}

    for param in params:
        stat_key = radar_viz.PARAM_TO_STAT.get(param)
        if not stat_key:
            continue
        league_vals = []
        for p in all_players:
            try:
                league_vals.append(float(p.get(stat_key) or 0))
            except (TypeError, ValueError):
                pass
        if not league_vals:
            continue
        val = float(player.get(stat_key) or 0)
        pct = float(np.sum(np.array(league_vals) < val) / len(league_vals) * 100)
        percentiles[param] = round(pct, 1)
        raw[param]         = round(val, 2)

    return percentiles, raw
