"""
Infographic generation endpoints — all return image/png.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core import cache
from app.services import fbref_service as fbref
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


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER — Understat (shot-based)
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
    png = shotmap.render(df, meta.get("name", player_id),
                         f"{season}/{str(season+1)[-2:]}")
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/career-xg")
def player_career_xg(
    player_id: str,
    seasons: str = Query(None, description="Comma-separated years, e.g. 2022,2023"),
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
# PLAYER — FBref (stats-based)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/fbref/radar")
def player_radar(
    player: str  = Query(...),
    league_id: str = Query(...),
    season: int  = Query(...),
    position: str = Query("FW"),
    compare_player: str = Query(None),
):
    ck = {"type": "radar", "player": player, "league_id": league_id,
          "season": season, "position": position, "compare": compare_player or ""}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    df = fbref.get_combined_player_stats(league_id, season)
    if df.empty:
        raise HTTPException(503, "Could not load player stats — FBref may be temporarily unavailable")

    row = _find_player(df, player)
    if row is None:
        raise HTTPException(404, f"Player not found: {player}")

    params      = radar_viz.POSITION_PARAMS.get(position[:2].upper(), radar_viz.ATTACKER_PARAMS)
    pcts, raw   = _compute_percentiles(df, row, params)

    comp_pcts = None
    if compare_player:
        comp_row = _find_player(df, compare_player)
        if comp_row:
            comp_pcts, _ = _compute_percentiles(df, comp_row, params)

    png = radar_viz.render(
        player_name=player, position=position,
        season_label=f"{season}/{str(season+1)[-2:]}",
        percentiles=pcts, raw_values=raw,
        team=str(row.get("team", "")),
        compare_name=compare_player, compare_percentiles=comp_pcts,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/fbref/summary-card")
def player_summary_card(
    player: str   = Query(...),
    league_id: str = Query(...),
    season: int   = Query(...),
    position: str = Query("FW"),
):
    ck = {"type": "summary_card", "player": player,
          "league_id": league_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    df = fbref.get_combined_player_stats(league_id, season)
    if df.empty:
        raise HTTPException(503, "Could not load stats")

    row = _find_player(df, player)
    if row is None:
        raise HTTPException(404, f"Player not found: {player}")

    png = summary_card.render(
        player_name=player, position=position,
        team=str(row.get("team", "")),
        season_label=f"{season}/{str(season+1)[-2:]}",
        stats=row,
        league_label=fbref.LEAGUE_LABELS.get(league_id, league_id),
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
):
    ck = {"type": "team_xg_timeline", "team_id": team_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    try:
        history = understat.get_team_xg_history(team_id, season)
    except Exception as exc:
        logger.error(f"team xg timeline {team_id}/{season}: {exc}")
        raise HTTPException(503, "Failed to fetch team xG history")

    png = team_xg_timeline.render(team_name, f"{season}/{str(season+1)[-2:]}", history)
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/fbref/season-card")
def team_season_card(
    team: str      = Query(...),
    league_id: str = Query(...),
    season: int    = Query(...),
):
    ck = {"type": "team_season_card", "team": team, "league_id": league_id, "season": season}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    table    = fbref.get_league_table(league_id, season)
    team_row = next((r for r in table
                     if team.lower() in str(r.get("team", "")).lower()), None)

    stats: dict = {}
    pos_h: list[dict] = []
    if team_row:
        stats = {k: team_row.get(k) for k in
                 ["wins","draws","losses","goals_for","goals_against",
                  "goal_diff","points","xg","xga"]}
        rank = next((i+1 for i, r in enumerate(table)
                     if team.lower() in str(r.get("team","")).lower()), 1)
        pos_h = [{"matchday": 1, "position": rank},
                 {"matchday": 38, "position": rank}]

    # Top scorers from Understat (best-effort, won't block if unavailable)
    top_scorers: list[dict] = []
    try:
        us_teams = understat.get_league_teams(_us_league(league_id), season)
        us_team  = next((t for t in us_teams
                         if team.lower() in t.get("name","").lower()), None)
        if us_team:
            shots = understat.get_team_shots(us_team["id"], season)
            if not shots.empty and "player" in shots.columns:
                grp = (shots[shots["result"]=="Goal"]
                       .groupby("player")
                       .agg(goals=("result","count"), xG=("xG","sum"))
                       .reset_index().nlargest(8, "goals"))
                top_scorers = grp.to_dict(orient="records")
    except Exception:
        pass

    png = team_card_viz.render(
        team_name=team,
        season_label=f"{season}/{str(season+1)[-2:]}",
        league_label=fbref.LEAGUE_LABELS.get(league_id, league_id),
        position_history=pos_h, stats=stats, top_scorers=top_scorers,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_player(df: pd.DataFrame, name: str) -> dict | None:
    if "player" not in df.columns:
        return None
    mask = df["player"].str.lower().str.contains(name.lower(), na=False)
    rows = df[mask]
    return rows.iloc[0].to_dict() if not rows.empty else None


def _compute_percentiles(
    df: pd.DataFrame, player: dict, params: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    percentiles: dict[str, float] = {}
    raw:         dict[str, float] = {}
    for param in params:
        col = radar_viz.PARAM_TO_STAT.get(param)
        if not col or col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        val    = float(player.get(col) or 0)
        pct    = float((series < val).sum() / len(series) * 100) if len(series) > 1 else 50.0
        percentiles[param] = round(pct, 1)
        raw[param]         = round(val, 2)
    return percentiles, raw


# Understat league slug from our internal ID
_US_LEAGUE_MAP = {
    "ENG-1": "EPL", "ESP-1": "La_liga", "DEU-1": "Bundesliga",
    "ITA-1": "Serie_A", "FRA-1": "Ligue_1", "RUS-1": "RFPL",
}


def _us_league(league_id: str) -> str:
    return _US_LEAGUE_MAP.get(league_id, "EPL")
