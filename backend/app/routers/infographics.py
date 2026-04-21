"""
Infographic generation endpoints — all return image/png.

Data sources:
- Shot maps, career xG, xG timeline:  Understat (no limits)
- Radar, summary card:                Understat league player stats (no limits)
- Team season card:                   football-data.org standings + Understat xG
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core import cache
from app.services import football_data_service as fdorg
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
PNG    = "image/png"


def _png(data: bytes) -> Response:
    return Response(content=data, media_type=PNG)


def _season_label(season: int) -> str:
    return f"{season}/{str(season + 1)[-2:]}"


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER — shot based (Understat player ID)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/shotmap")
def player_shotmap(player_id: str, season: int = Query(...)):
    ck = {"type": "shotmap", "player_id": player_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    try:
        shots = understat.get_player_shots(player_id)
        meta  = understat.get_player_meta(player_id)
    except Exception as exc:
        logger.error(f"shotmap {player_id}/{season}: {exc}")
        raise HTTPException(503, "Failed to fetch shot data")

    df  = shots[shots["season"] == season] if not shots.empty else shots
    png = shotmap.render(df, meta.get("name", player_id), _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/career-xg")
def player_career_xg(
    player_id: str,
    seasons: str = Query(None, description="Comma-separated years e.g. 2022,2023"),
):
    season_list = [int(s) for s in seasons.split(",")] if seasons else None
    ck = {"type": "career_xg", "player_id": player_id, "seasons": seasons or "all"}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    try:
        shots = understat.get_player_shots(player_id)
        meta  = understat.get_player_meta(player_id)
    except Exception as exc:
        logger.error(f"career_xg {player_id}: {exc}")
        raise HTTPException(503, "Failed to fetch shot data")

    png = career_xg_viz.render(meta.get("name", player_id), shots, seasons=season_list)
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER — stats based (Understat league player pool for percentiles)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/radar")
def player_radar(
    player_id: str,
    league_id: str  = Query(...),
    season: int     = Query(...),
    position: str   = Query("FW"),
    compare_id: str = Query(None),
):
    ck = {"type": "radar", "player_id": player_id, "league_id": league_id,
          "season": season, "position": position, "compare": compare_id or ""}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, f"Radar not available for {league_id} — "
                                 "only Understat leagues are supported")

    all_players = understat.get_league_player_stats(us_slug, season)
    if not all_players:
        raise HTTPException(503, "Could not load league player stats")

    player_row = next((p for p in all_players if p["id"] == player_id), None)
    if player_row is None:
        # fall back to meta
        meta = understat.get_player_meta(player_id)
        season_stats = understat.get_player_season_stats(player_id, season)
        if not season_stats:
            raise HTTPException(404, f"No stats found for player {player_id} in {season}")
        player_row = {**season_stats, "player": meta.get("name", player_id),
                      "id": player_id}

    params    = radar_viz.POSITION_PARAMS.get(position[:2].upper(), radar_viz.ATTACKER_PARAMS)
    pcts, raw = _compute_percentiles(all_players, player_row, params)

    comp_pcts = None
    if compare_id:
        comp_row = next((p for p in all_players if p["id"] == compare_id), None)
        if comp_row:
            comp_pcts, _ = _compute_percentiles(all_players, comp_row, params)

    png = radar_viz.render(
        player_name  = player_row.get("player", player_id),
        position     = position,
        season_label = _season_label(season),
        percentiles  = pcts,
        raw_values   = raw,
        team         = player_row.get("team", ""),
        compare_name = None,
        compare_percentiles = comp_pcts,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/summary-card")
def player_summary_card(
    player_id: str,
    league_id: str = Query(None),
    season: int    = Query(...),
    position: str  = Query("FW"),
):
    ck = {"type": "summary_card", "player_id": player_id,
          "league_id": league_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    meta         = understat.get_player_meta(player_id)
    season_stats = understat.get_player_season_stats(player_id, season)
    if not season_stats:
        raise HTTPException(404, f"No stats for player {player_id} in {season}")

    # Map Understat season stats → summary_card expected keys
    stats = {
        "goals":      season_stats.get("goals"),
        "assists":    season_stats.get("assists"),
        "xG":         season_stats.get("xg"),
        "xA":         season_stats.get("xa"),
        "npxG":       season_stats.get("npxg"),
        "minutes":    season_stats.get("minutes"),
        "apps":       season_stats.get("apps"),
        "key_passes": season_stats.get("key_passes"),
    }

    png = summary_card.render(
        player_name  = meta.get("name", player_id),
        position     = position,
        team         = season_stats.get("team", ""),
        season_label = _season_label(season),
        stats        = stats,
        league_label = fdorg.LEAGUE_LABELS.get(league_id, league_id),
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# TEAM
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/team/{team_id}/xg-timeline")
def team_xg_timeline_img(
    team_id: str,
    team_name: str = Query(...),
    season: int    = Query(...),
    league_id: str = Query(None),
):
    # Resolve to Understat team ID (fdorg IDs differ from Understat IDs)
    us_team_id = team_id
    if league_id:
        us_slug = understat.LEAGUE_TO_US.get(league_id)
        if us_slug:
            us_teams = understat.get_league_teams(us_slug, season)
            us_team  = next(
                (t for t in us_teams if team_name.lower() in t["name"].lower()), None
            )
            if us_team:
                us_team_id = us_team["id"]

    ck = {"type": "team_xg_timeline", "team_id": us_team_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    try:
        history = understat.get_team_xg_history(us_team_id, season)
    except Exception as exc:
        logger.error(f"team xg timeline {us_team_id}/{season}: {exc}")
        raise HTTPException(503, "Failed to fetch team xG history")

    png = team_xg_timeline.render(team_name, _season_label(season), history)
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/{team_id}/season-card")
def team_season_card(
    team_id: str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season: int    = Query(...),
):
    ck = {"type": "team_season_card", "team_id": team_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    # Standings from football-data.org
    table    = fdorg.get_standings(league_id, season)
    team_row = next(
        (r for r in table if team_name.lower() in r.get("team", "").lower()), None
    )

    stats: dict = {}
    pos_h: list[dict] = []
    if team_row:
        stats = {k: team_row.get(k) for k in
                 ["wins","draws","losses","goals_for","goals_against","goal_diff","points"]}
        rank  = team_row.get("rank", 1)
        pos_h = [{"matchday": 1,  "position": rank},
                 {"matchday": 38, "position": rank}]

    # Top scorers from football-data.org
    top_scorers = fdorg.get_top_scorers(league_id, season, limit=8)
    # Filter to this team
    top_scorers = [s for s in top_scorers
                   if team_name.lower() in s.get("team", "").lower()]

    # Understat xG stats (best-effort)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if us_slug:
        try:
            us_teams = understat.get_league_teams(us_slug, season)
            us_team  = next(
                (t for t in us_teams if team_name.lower() in t["name"].lower()), None
            )
            if us_team:
                stats["xG"]  = us_team.get("xG")
                stats["xGA"] = us_team.get("xGA")
                stats["xPts"] = us_team.get("xPts")
                # Better top scorers from shot data
                shots = understat.get_team_shots(us_team["id"], season)
                if not shots.empty and "player" in shots.columns:
                    grp = (
                        shots[shots["result"] == "Goal"]
                        .groupby("player")
                        .agg(goals=("result", "count"), xG=("xG", "sum"))
                        .reset_index()
                        .nlargest(8, "goals")
                    )
                    top_scorers = grp.to_dict(orient="records")
        except Exception:
            pass

    png = team_card_viz.render(
        team_name      = team_name,
        season_label   = _season_label(season),
        league_label   = fdorg.LEAGUE_LABELS.get(league_id, league_id),
        position_history = pos_h,
        stats          = stats,
        top_scorers    = top_scorers,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_percentiles(
    all_players: list[dict],
    player: dict,
    params: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    percentiles: dict[str, float] = {}
    raw:         dict[str, float] = {}

    for param in params:
        col = radar_viz.PARAM_TO_STAT.get(param)
        if not col:
            continue
        vals = []
        for p in all_players:
            try:
                vals.append(float(p.get(col) or 0))
            except (TypeError, ValueError):
                pass
        if not vals:
            continue
        val = float(player.get(col) or 0)
        pct = float(np.sum(np.array(vals) < val) / len(vals) * 100)
        percentiles[param] = round(pct, 1)
        raw[param]         = round(val, 2)

    return percentiles, raw
