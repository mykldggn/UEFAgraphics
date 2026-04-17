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
from app.services import fbref_service as fbref
from app.services import understat_service as understat
from app.viz import (
    shotmap,
    radar as radar_viz,
    summary_card,
    career_xg as career_xg_viz,
    passmap,
    team_xg_timeline,
    team_season_card as team_card_viz,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/infographics", tags=["infographics"])

PNG = "image/png"


def _png(data: bytes) -> Response:
    return Response(content=data, media_type=PNG)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/shotmap")
def player_shotmap(
    player_id: str,
    season: int = Query(..., description="Season start year, e.g. 2023"),
):
    """Shot map for a player+season (Understat data)."""
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

    df = shots[shots["season"] == season] if not shots.empty else shots
    season_label = f"{season}/{str(season + 1)[-2:]}"
    team = df["team"].iloc[0] if not df.empty and "team" in df.columns else ""
    png = shotmap.render(df, meta.get("name", player_id), season_label, color=None)
    cache.img_save("infographic", cache_key, png)
    return _png(png)


@router.get("/player/{player_id}/career-xg")
def player_career_xg(
    player_id: str,
    seasons: str = Query(None, description="Comma-separated season years, e.g. 2022,2023"),
):
    """Career xG vs Goals chart (Understat)."""
    season_list = [int(s) for s in seasons.split(",")] if seasons else None
    cache_key = {"type": "career_xg", "player_id": player_id, "seasons": seasons or "all"}
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
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


@router.get("/player/fbref/radar")
def player_radar(
    player: str = Query(..., description="Player name (FBref)"),
    league_id: str = Query(...),
    season: int = Query(...),
    position: str = Query("FW"),
    compare_player: str = Query(None),
):
    """Radar / pizza chart from FBref percentiles."""
    cache_key = {
        "type": "radar", "player": player, "league_id": league_id,
        "season": season, "position": position, "compare": compare_player or "",
    }
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    df = fbref.get_combined_player_stats(league_id, season)
    if df.empty:
        raise HTTPException(503, "Could not load player stats")

    player_row = _find_player(df, player)
    if player_row is None:
        raise HTTPException(404, f"Player not found: {player}")

    params = radar_viz.POSITION_PARAMS.get(position[:2].upper(), radar_viz.ATTACKER_PARAMS)
    percentiles, raw = _compute_percentiles(df, player_row, params)
    team = str(player_row.get("team", ""))

    compare_pcts = None
    if compare_player:
        comp_row = _find_player(df, compare_player)
        if comp_row:
            compare_pcts, _ = _compute_percentiles(df, comp_row, params)

    season_label = f"{season}/{str(season + 1)[-2:]}"
    png = radar_viz.render(
        player_name=player,
        position=position,
        season_label=season_label,
        percentiles=percentiles,
        raw_values=raw,
        team=team,
        compare_name=compare_player,
        compare_percentiles=compare_pcts,
    )
    cache.img_save("infographic", cache_key, png)
    return _png(png)


@router.get("/player/fbref/summary-card")
def player_summary_card(
    player: str = Query(...),
    league_id: str = Query(...),
    season: int = Query(...),
    position: str = Query("FW"),
):
    """Player season summary card from FBref data."""
    cache_key = {"type": "summary_card", "player": player,
                 "league_id": league_id, "season": season}
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    df = fbref.get_combined_player_stats(league_id, season)
    if df.empty:
        raise HTTPException(503, "Could not load player stats")

    row = _find_player(df, player)
    if row is None:
        raise HTTPException(404, f"Player not found: {player}")

    stats = _row_to_summary_stats(row)
    season_label = f"{season}/{str(season + 1)[-2:]}"
    league_label = fbref.LEAGUE_LABELS.get(league_id, league_id)

    png = summary_card.render(
        player_name=player,
        position=position,
        team=str(row.get("team", "")),
        season_label=season_label,
        stats=stats,
        league_label=league_label,
    )
    cache.img_save("infographic", cache_key, png)
    return _png(png)


@router.get("/player/fbref/passmap")
def player_passmap(
    player: str = Query(...),
    league_id: str = Query(...),
    season: int = Query(...),
):
    """Pass map for a player from FBref passing data."""
    cache_key = {"type": "passmap", "player": player,
                 "league_id": league_id, "season": season}
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    df_pass = fbref.get_player_passing_stats(league_id, season)
    if df_pass.empty:
        raise HTTPException(503, "Could not load passing stats")

    row = _find_player(df_pass, player)
    if row is None:
        raise HTTPException(404, f"Player not found: {player}")

    pass_df = _build_pass_df(df_pass, player)
    season_label = f"{season}/{str(season + 1)[-2:]}"
    png = passmap.render(pass_df, player, season_label, team=str(row.get("team", "")))
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
    cached = cache.img_get("infographic", cache_key, ttl_hours=12)
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


@router.get("/team/fbref/season-card")
def team_season_card(
    team: str = Query(...),
    league_id: str = Query(...),
    season: int = Query(...),
):
    cache_key = {"type": "team_season_card", "team": team,
                 "league_id": league_id, "season": season}
    cached = cache.img_get("infographic", cache_key, ttl_hours=24)
    if cached:
        return _png(cached)

    df_std = fbref.get_team_standard_stats(league_id, season)
    df_sh  = fbref.get_team_shooting_stats(league_id, season)
    table  = fbref.get_league_table(league_id, season)

    stats  = _build_team_stats(df_std, df_sh, table, team, season)
    pos_h  = _build_position_history(table, team)  # simplified — single position
    league_label = fbref.LEAGUE_LABELS.get(league_id, league_id)
    season_label = f"{season}/{str(season + 1)[-2:]}"

    # top scorers from standard stats
    df_pl = fbref.get_player_standard_stats(league_id, season)
    top_scorers = _top_scorers(df_pl, team)

    png = team_card_viz.render(
        team_name=team,
        season_label=season_label,
        league_label=league_label,
        position_history=pos_h,
        stats=stats,
        top_scorers=top_scorers,
    )
    cache.img_save("infographic", cache_key, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_player(df: pd.DataFrame, name: str) -> dict | None:
    if "player" not in df.columns:
        return None
    mask = df["player"].str.lower().str.contains(name.lower(), na=False)
    rows = df[mask]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


_STAT_MAP = {
    # summary_card key → FBref column candidates
    "goals":          ["goals", "Gls"],
    "assists":        ["assists", "Ast"],
    "xG":             ["npxg", "xg", "xG"],
    "xA":             ["xAG", "xa", "xA"],
    "npxG":           ["npxg", "npxG"],
    "minutes":        ["minutes", "Min"],
    "apps":           ["games", "MP"],
    "pass_cmp_pct":   ["passes_pct", "Cmp%"],
    "key_passes":     ["assisted_shots", "KP"],
    "prog_passes":    ["progressive_passes", "PrgP"],
    "tackles":        ["tackles", "Tkl"],
    "interceptions":  ["interceptions", "Int"],
    "pressures":      ["pressures", "Press"],
    "dribbles":       ["dribbles_completed", "Succ"],
    "fouls_won":      ["fouled", "Fld"],
    "aerials_won_pct":["aerials_won_pct", "Won%"],
}


def _compute_percentiles(
    df: pd.DataFrame,
    player_row: dict,
    params: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute rank-based percentiles for a player vs full DataFrame."""
    # Map our display param names to actual columns (best-effort)
    param_to_col = {
        "Goals":            "goals",
        "xG":               "npxg",
        "Shots/90":         "shots_per90",
        "xG/Shot":          "npxg_per_shot",
        "Assists":          "assists",
        "xA":               "xAG",
        "Prog Passes/90":   "progressive_passes_per90",
        "Key Passes/90":    "assisted_shots",
        "Dribbles/90":      "dribbles_completed",
        "Touches in Box/90":"touches_att_pen_area",
        "Fouls Won/90":     "fouled",
        "Aerial Win%":      "aerials_won_pct",
        "Pass Cmp%":        "passes_pct",
        "Through Balls/90": "through_balls",
        "Tackles/90":       "tackles",
        "Interceptions/90": "interceptions",
        "Clearances/90":    "clearances",
        "Blocks/90":        "blocks",
        "Pressures/90":     "pressures",
        "Ball Recoveries/90":"ball_recoveries",
        "Fouls/90":         "fouls",
        "Errors/90":        "errors",
        "Goals Against/90": "goals_against_per90",
        "Save%":            "save_pct",
        "PSxG-GA":          "psxg_net",
        "Clean Sheet%":     "clean_sheets_pct",
        "xGA/90":           "psnpxg_per_shot_on_target_against",
        "Crosses Stopped%": "crosses_stopped_pct",
        "Long Pass Cmp%":   "passes_long_pct",
    }
    percentiles: dict[str, float] = {}
    raw: dict[str, float] = {}

    for param in params:
        col = param_to_col.get(param)
        if col and col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            val = float(player_row.get(col, 0) or 0)
            if len(series) > 1:
                pct = float((series < val).sum() / len(series) * 100)
            else:
                pct = 50.0
            percentiles[param] = round(pct, 1)
            raw[param] = round(val, 2)

    return percentiles, raw


def _row_to_summary_stats(row: dict) -> dict:
    result = {}
    for stat_key, candidates in _STAT_MAP.items():
        for col in candidates:
            if col in row and row[col] is not None:
                result[stat_key] = row[col]
                break
    return result


def _build_pass_df(df_pass: pd.DataFrame, player: str) -> pd.DataFrame:
    """
    FBref passing stats don't include individual pass coordinates.
    Return an empty DataFrame — the passmap will render a 'no data' fallback.
    Individual pass events require StatsBomb / Opta event data.
    """
    return pd.DataFrame()


def _build_team_stats(
    df_std: pd.DataFrame,
    df_sh:  pd.DataFrame,
    table:  pd.DataFrame,
    team:   str,
    season: int,
) -> dict:
    stats: dict = {}

    def _get(df, team, col):
        if df.empty or "team" not in df.columns or col not in df.columns:
            return None
        mask = df["team"].str.lower().str.contains(team.lower(), na=False)
        rows = df[mask]
        return float(rows.iloc[0][col]) if not rows.empty else None

    stats["wins"]   = _get(df_std, team, "wins")
    stats["draws"]  = _get(df_std, team, "draws")
    stats["losses"] = _get(df_std, team, "losses")

    if not table.empty and "team" in table.columns:
        t_mask = table["team"].str.lower().str.contains(team.lower(), na=False)
        t_rows = table[t_mask]
        if not t_rows.empty:
            tr = t_rows.iloc[0]
            stats["goals_for"]      = tr.get("goals_for")
            stats["goals_against"]  = tr.get("goals_against")
            stats["goal_diff"]      = tr.get("goal_diff")
            stats["points"]         = tr.get("points")
            stats["final_position"] = t_rows.index[0] + 1  # rank by row position

    stats["xG"]  = _get(df_sh, team, "npxg")
    stats["xGA"] = None  # FBref separate endpoint
    return stats


def _build_position_history(table: pd.DataFrame, team: str) -> list[dict]:
    """No matchday position data in FBref season summary — return static end position."""
    if table.empty or "team" not in table.columns:
        return []
    teams_lower = table["team"].str.lower().tolist()
    name_lower  = team.lower()
    for i, t in enumerate(teams_lower):
        if name_lower in t or t in name_lower:
            return [{"matchday": 1, "position": i + 1},
                    {"matchday": 38, "position": i + 1}]
    return []


def _top_scorers(df_pl: pd.DataFrame, team: str) -> list[dict]:
    if df_pl.empty or "player" not in df_pl.columns:
        return []
    t_mask = df_pl.get("team", pd.Series(dtype=str)).str.lower().str.contains(
        team.lower(), na=False)
    sub = df_pl[t_mask].copy() if "team" in df_pl.columns else df_pl.copy()
    for col in ["goals", "Gls"]:
        if col in sub.columns:
            sub["_goals"] = pd.to_numeric(sub[col], errors="coerce").fillna(0)
            break
    else:
        return []
    sub = sub.nlargest(8, "_goals")
    out = []
    for _, r in sub.iterrows():
        xg_val = 0.0
        for xg_col in ["npxg", "xg", "xG"]:
            if xg_col in r:
                xg_val = float(r[xg_col] or 0)
                break
        out.append({"player": r["player"], "goals": int(r["_goals"]), "xG": xg_val})
    return out
