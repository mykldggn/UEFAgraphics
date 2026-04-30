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
from app.services import fotmob_service as fotmob
from app.viz import (
    shotmap,
    radar as radar_viz,
    summary_card,
    career_xg as career_xg_viz,
    team_xg_timeline,
    team_season_card as team_card_viz,
    lineup_card as lineup_viz,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/infographics", tags=["infographics"])
PNG    = "image/png"


def _team_match(a: str, b: str) -> bool:
    """Fuzzy team name match: strip ' FC'/' AFC' suffixes, then check bidirectionally."""
    import re
    def norm(s: str) -> str:
        return re.sub(r'\s+(f\.?c\.?|a\.?f\.?c\.?)$', '', s.lower().strip())
    an, bn = norm(a), norm(b)
    return an in bn or bn in an


def _png(data: bytes) -> Response:
    return Response(content=data, media_type=PNG)


def _season_label(season: int) -> str:
    return f"{season}/{str(season + 1)[-2:]}"


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER — shot based (Understat player ID)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/shotmap")
def player_shotmap(
    player_id: str,
    season: int = Query(None),
    source: str = Query("understat"),
):
    ck = {"type": "shotmap", "player_id": player_id, "season": season or "all",
          "src": source}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    if source == "fotmob":
        try:
            import pandas as pd
            pd_data  = fotmob.get_player_data(player_id)
            name     = pd_data.get("name", player_id)
            team_id  = (pd_data.get("primaryTeam") or {}).get("id") or 0
            season_yr = season or 2024
            df = fotmob.get_player_season_shots(player_id, team_id, season_yr)
            label = _season_label(season_yr)
            if df.empty:
                df = pd.DataFrame()
            # Add team column so team_color() picks correct colour
            team_name = (pd_data.get("primaryTeam") or {}).get("name", "")
            if not df.empty and "team" not in df.columns:
                df["team"] = team_name
        except Exception as exc:
            logger.error(f"fotmob shotmap {player_id}: {exc}")
            df = pd.DataFrame(); name = player_id; label = ""; team_name = ""

        png = shotmap.render(df, name, label)
        cache.img_save("infographic", ck, png)
        return _png(png)

    # ── Understat path (default) ──────────────────────────────────────────────
    try:
        shots = understat.get_player_shots(player_id)
        meta  = understat.get_player_meta(player_id)
    except Exception as exc:
        logger.error(f"shotmap {player_id}/{season}: {exc}")
        raise HTTPException(503, "Failed to fetch shot data")

    if season is not None and not shots.empty:
        df = shots[shots["season"] == season]
    else:
        df = shots
    label = _season_label(season) if season else "All Seasons"
    png = shotmap.render(df, meta.get("name", player_id), label)
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/career-xg")
def player_career_xg(
    player_id: str,
    seasons: str = Query(None, description="Comma-separated years e.g. 2022,2023"),
    source: str = Query("understat"),
):
    season_list = [int(s) for s in seasons.split(",")] if seasons else None
    ck = {"type": "career_xg", "player_id": player_id, "seasons": seasons or "all",
          "src": source}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    if source == "fotmob":
        try:
            import pandas as pd
            pd_data = fotmob.get_player_data(player_id)
            name    = pd_data.get("name", player_id)
            career  = fotmob.get_player_career_history(player_id)
            # Build a shot-like DataFrame: one row per season with cumulative-friendly format
            rows: list[dict] = []
            for entry in career:
                yr = entry["season_year"]
                if season_list and yr not in season_list:
                    continue
                # Synthesise goal/no-goal rows from totals so career_xg_viz works
                g  = int(entry.get("goals", 0))
                xg = float(entry.get("xg", 0))
                shots_est = max(int(xg / 0.12), g, 1)  # rough shot count from xG
                per_shot_xg = xg / shots_est if shots_est else 0
                for i in range(shots_est):
                    rows.append({
                        "season":  yr,
                        "result":  "Goal" if i < g else "MissedShots",
                        "xG":      round(per_shot_xg, 3),
                        "team":    entry.get("team", ""),
                    })
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as exc:
            logger.error(f"fotmob career_xg {player_id}: {exc}")
            df = pd.DataFrame(); name = player_id

        png = career_xg_viz.render(name, df, seasons=season_list)
        cache.img_save("infographic", ck, png)
        return _png(png)

    # ── Understat path ────────────────────────────────────────────────────────
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
    source: str     = Query("understat"),
):
    ck = {"type": "radar", "player_id": player_id, "league_id": league_id,
          "season": season, "position": position, "compare": compare_id or "",
          "src": source}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    pos_key = position[:2].upper()

    if source == "fotmob":
        fm_id = fotmob.FOTMOB_LEAGUES.get(league_id)
        if not fm_id:
            raise HTTPException(400, f"FotMob not available for {league_id}")

        all_players = fotmob.get_league_player_stats(fm_id, season)
        if not all_players:
            raise HTTPException(503, "Could not load FotMob league player stats")

        player_row = next((p for p in all_players if p["id"] == str(player_id)), None)
        if player_row is None:
            # Fallback: fetch individual stats
            fm_stats = fotmob.get_player_season_stats(player_id, season, fm_id)
            pd_data  = fotmob.get_player_data(player_id)
            player_row = {
                **fm_stats,
                "player": pd_data.get("name", player_id),
                "id": str(player_id),
            }

        params    = radar_viz.FOTMOB_POSITION_PARAMS.get(pos_key, radar_viz.FOTMOB_ATTACKER_PARAMS)
        pcts, raw = _compute_percentiles(all_players, player_row, params,
                                         param_map=radar_viz.PARAM_TO_STAT)
        png = radar_viz.render(
            player_name  = player_row.get("player", player_id),
            position     = position,
            season_label = _season_label(season),
            percentiles  = pcts,
            raw_values   = raw,
            team         = player_row.get("team", ""),
            compare_name = None,
            compare_percentiles = None,
        )
        cache.img_save("infographic", ck, png)
        return _png(png)

    # ── Understat path ────────────────────────────────────────────────────────
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, f"Radar not available for {league_id} — "
                                 "only Understat leagues are supported")

    all_players = understat.get_league_player_stats(us_slug, season)
    if not all_players:
        raise HTTPException(503, "Could not load league player stats")

    player_row = next((p for p in all_players if p["id"] == player_id), None)
    if player_row is None:
        meta = understat.get_player_meta(player_id)
        season_stats = understat.get_player_season_stats(player_id, season)
        if not season_stats:
            raise HTTPException(404, f"No stats found for player {player_id} in {season}")
        player_row = {**season_stats, "player": meta.get("name", player_id),
                      "id": player_id}

    params    = radar_viz.POSITION_PARAMS.get(pos_key, radar_viz.ATTACKER_PARAMS)
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
    season: int    = Query(None),
    position: str  = Query("FW"),
    source: str    = Query("understat"),
):
    ck = {"type": "summary_card", "player_id": player_id,
          "league_id": league_id, "season": season or "all", "src": source}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    if source == "fotmob":
        pd_data  = fotmob.get_player_data(player_id)
        name     = pd_data.get("name", player_id)
        fm_id    = fotmob.FOTMOB_LEAGUES.get(league_id) if league_id else None

        if season is None:
            # Career aggregate
            career = fotmob.get_player_career_history(player_id)
            if not career:
                raise HTTPException(404, f"No career data for player {player_id}")
            stats = {
                "goals":      sum(e.get("goals", 0) for e in career),
                "assists":    sum(e.get("assists", 0) for e in career),
                "xG":         round(sum(e.get("xg", 0) for e in career), 2),
                "xA":         round(sum(e.get("xa", 0) for e in career), 2),
                "minutes":    sum(e.get("minutes", 0) for e in career),
                "apps":       len(career),
            }
            team         = career[-1].get("team", "") if career else ""
            season_label = "Career"
        else:
            s = fotmob.get_player_season_stats(player_id, season, fm_id)
            if not s:
                raise HTTPException(404, f"No FotMob stats for player {player_id} in {season}")
            stats = {
                "goals":      s.get("goals", 0),
                "assists":    s.get("assists", 0),
                "xG":         round(float(s.get("xg", 0)), 2),
                "xA":         round(float(s.get("xa", 0)), 2),
                "shots":      s.get("shots", 0),
                "key_passes": s.get("key_passes", 0),
                "minutes":    s.get("minutes", 0),
                "apps":       s.get("apps", 0),
            }
            team         = s.get("team", "")
            season_label = _season_label(season)

        png = summary_card.render(
            player_name  = name,
            position     = position,
            team         = team,
            season_label = season_label,
            stats        = stats,
            league_label = fdorg.LEAGUE_LABELS.get(league_id, league_id) if league_id else "",
        )
        cache.img_save("infographic", ck, png)
        return _png(png)

    # ── Understat path ────────────────────────────────────────────────────────
    meta = understat.get_player_meta(player_id)

    if season is None:
        all_seasons = meta.get("season_stats", [])
        if not all_seasons:
            raise HTTPException(404, f"No career stats for player {player_id}")
        def _sum(key):
            return sum(float(s.get(key) or 0) for s in all_seasons)
        stats = {
            "goals":      _sum("goals"),
            "assists":    _sum("assists"),
            "xG":         round(_sum("xg"), 2),
            "xA":         round(_sum("xa"), 2),
            "npxG":       round(_sum("npxg"), 2),
            "minutes":    _sum("minutes"),
            "apps":       _sum("apps"),
            "key_passes": _sum("key_passes"),
        }
        from collections import Counter
        team_apps: Counter = Counter()
        for s in all_seasons:
            team_apps[s.get("team", "")] += int(s.get("apps", 0) or 0)
        team = team_apps.most_common(1)[0][0] if team_apps else all_seasons[-1].get("team", "")
        season_label = "Career"
    else:
        season_stats = understat.get_player_season_stats(player_id, season)
        if not season_stats:
            raise HTTPException(404, f"No stats for player {player_id} in {season}")
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
        team         = season_stats.get("team", "")
        season_label = _season_label(season)

    png = summary_card.render(
        player_name  = meta.get("name", player_id),
        position     = position,
        team         = team,
        season_label = season_label,
        stats        = stats,
        league_label = fdorg.LEAGUE_LABELS.get(league_id, league_id) if league_id else "",
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
    us_slug    = understat.LEAGUE_TO_US.get(league_id) if league_id else None
    has_xg     = bool(us_slug)
    history: list[dict] = []

    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id) if league_id else None

    if us_slug:
        # Top-5 league: Understat xG
        us_team_id = team_id
        us_teams   = understat.get_league_teams(us_slug, season)
        us_team    = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
        if us_team:
            us_team_id = us_team["id"]
        ck = {"type": "team_xg_timeline", "team_id": us_team_id, "season": season}
        if cached := cache.img_get("infographic", ck):
            return _png(cached)
        try:
            history = understat.get_team_xg_history(us_team_id, season, league=us_slug)
        except Exception as exc:
            logger.error(f"team xg timeline {us_team_id}/{season}: {exc}")

    elif fm_league_id and team_id.isdigit():
        # Non-top-5 + FotMob available: real xG per match
        has_xg = True
        ck = {"type": "team_timeline_fotmob", "team_id": team_id,
              "league_id": fm_league_id, "season": season}
        if cached := cache.img_get("infographic", ck):
            return _png(cached)
        try:
            history = fotmob.get_team_season_xg(team_id, fm_league_id, season)
        except Exception as exc:
            logger.error(f"team xg timeline fotmob {team_id}/{season}: {exc}")

    if not history:
        # Fallback: fdorg match results (no xG)
        has_xg  = False
        fdorg_id = team_id
        if not team_id.isdigit() and league_id:
            table = fdorg.get_standings(league_id, season)
            matched = next(
                (r for r in table if _team_match(team_name, r.get("team", ""))), None
            )
            if matched and str(matched.get("team_id", "")).isdigit():
                fdorg_id = str(matched["team_id"])
        ck = {"type": "team_timeline_fdorg", "team_id": fdorg_id, "season": season}
        if cached := cache.img_get("infographic", ck):
            return _png(cached)
        try:
            history = fdorg.get_team_results(fdorg_id, season)
        except Exception as exc:
            logger.error(f"team results fdorg {fdorg_id}/{season}: {exc}")

    if not history:
        raise HTTPException(503, "No match data available for this team/season")

    opponents: list[dict] | None = [
        {"name": h.get("opponent", ""), "crest_url": ""} for h in history
    ]

    png = team_xg_timeline.render(team_name, _season_label(season), history,
                                  opponents=opponents, has_xg=has_xg)
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/{team_id}/season-card")
def team_season_card(
    team_id: str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season: int    = Query(...),
):
    ck = {"type": "team_season_card", "team_id": team_id, "season": season, "v": 4}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    # Standings from football-data.org
    table    = fdorg.get_standings(league_id, season)
    team_row = next(
        (r for r in table if _team_match(team_name, r.get("team", ""))), None
    )

    stats: dict = {}
    pos_h: list[dict] = []
    if team_row:
        stats = {k: team_row.get(k) for k in
                 ["wins","draws","losses","goals_for","goals_against","goal_diff","points"]}
        rank  = team_row.get("rank", 1)
        pos_h = [{"matchday": 1,  "position": rank},
                 {"matchday": 38, "position": rank}]

    # Top scorers from football-data.org (baseline — may be overwritten below)
    top_scorers = fdorg.get_top_scorers(league_id, season, limit=8)
    top_scorers = [s for s in top_scorers if _team_match(team_name, s.get("team", ""))]

    us_slug      = understat.LEAGUE_TO_US.get(league_id)
    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id) if league_id else None

    if us_slug:
        # ── Understat enrichment (top-5 leagues) ─────────────────────────────
        try:
            us_teams = understat.get_league_teams(us_slug, season)
            us_team  = next(
                (t for t in us_teams if _team_match(team_name, t["name"])), None
            )
            if us_team:
                stats["xG"]   = us_team.get("xG")
                stats["xGA"]  = us_team.get("xGA")
                stats["xPts"] = us_team.get("xPts")

                xg_hist = understat.get_team_xg_history(us_team["id"], season, league=us_slug)
                if xg_hist:
                    stats["clean_sheets"] = sum(1 for m in xg_hist if m.get("goals_against", 1) == 0)
                    pos_history_data = understat.get_league_position_history(us_slug, season)
                    if pos_history_data:
                        pos_h = [
                            {"matchday": row["match"], "position": row.get(us_team["name"])}
                            for row in pos_history_data.get("history", [])
                            if row.get(us_team["name"]) is not None
                        ]

                sorted_teams = sorted(us_teams, key=lambda t: t.get("pts", 0), reverse=True)
                final_pos = next(
                    (i + 1 for i, t in enumerate(sorted_teams)
                     if _team_match(team_name, t["name"])), None
                )
                if final_pos:
                    stats["final_position"] = final_pos

                all_players = understat.get_league_player_stats(us_slug, season)
                team_players = [p for p in all_players if p.get("team") == us_team["name"]]
                if team_players:
                    top_scorers = sorted(
                        [{"player": p["player"], "goals": p.get("goals", 0),
                          "xG": p.get("xg", 0)} for p in team_players],
                        key=lambda x: x["goals"], reverse=True
                    )[:8]
        except Exception as e:
            logger.warning(f"Understat enrichment failed for {team_name}: {e}")

    elif fm_league_id and team_id.isdigit():
        # ── FotMob enrichment (non-top-5 leagues) ────────────────────────────
        try:
            fm_tid = int(team_id)
            xg_hist = fotmob.get_team_season_xg(fm_tid, fm_league_id, season)
            if xg_hist:
                stats["xG"]  = round(sum(m["xG"]  for m in xg_hist), 1)
                stats["xGA"] = round(sum(m["xGA"] for m in xg_hist), 1)
                stats["clean_sheets"] = sum(1 for m in xg_hist if m.get("goals_against", 1) == 0)

            pos_data = fotmob.get_league_position_history(fm_league_id, season)
            if pos_data:
                # Find team name as it appears in the pos history keys
                fm_team_key = next(
                    (t for t in pos_data.get("teams", []) if _team_match(team_name, t)), None
                )
                if fm_team_key:
                    pos_h = [
                        {"matchday": row["match"], "position": row.get(fm_team_key)}
                        for row in pos_data.get("history", [])
                        if row.get(fm_team_key) is not None
                    ]
                    if pos_h:
                        stats["final_position"] = pos_h[-1]["position"]

            # Top scorers from FotMob league player pool
            fm_players = fotmob.get_league_player_stats(fm_league_id, season)
            team_players = [p for p in fm_players if _team_match(team_name, p.get("team", ""))]
            if team_players:
                top_scorers = sorted(
                    [{"player": p["player"], "goals": p.get("goals", 0),
                      "xG": round(float(p.get("xg", 0)), 2)} for p in team_players],
                    key=lambda x: x["goals"], reverse=True
                )[:8]
        except Exception as e:
            logger.warning(f"FotMob enrichment failed for {team_name}: {e}")

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


@router.get("/team/{team_id}/lineup-players")
def team_lineup_players(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    """Return XI player list as JSON (for clickable overlays)."""
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id)

    if us_slug:
        us_teams = understat.get_league_teams(us_slug, season)
        us_team  = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
        us_name  = us_team["name"] if us_team else team_name
        players  = understat.get_most_played_xi(us_slug, season, us_name)
        if not players:
            return {"players": [], "formation": ""}
        fotmob_hints = _fotmob_col_hints(team_name)
        xi, formation = lineup_viz.build_xi(players, fotmob_hints=fotmob_hints)
        player_pool   = understat.get_league_player_stats(us_slug, season)
        id_map = {p["player"]: p["id"] for p in player_pool}
        return {
            "players": [
                {"player": p["player"], "position": p["position"],
                 "minutes": p["minutes"], "id": id_map.get(p["player"]),
                 "source": "understat"}
                for p in xi
            ],
            "formation": formation,
        }

    if fm_league_id and team_id.isdigit():
        try:
            fm_tid    = int(team_id)
            fm_players = fotmob.get_league_player_stats(fm_league_id, season)
            team_pl   = sorted(
                [p for p in fm_players if _team_match(team_name, p.get("team", ""))],
                key=lambda p: p.get("minutes", 0), reverse=True
            )[:15]
            if not team_pl:
                return {"players": [], "formation": ""}
            for p in team_pl:
                p["position"] = p.get("pos", "")
            fotmob_hints = _fotmob_col_hints(team_name)
            xi, formation = lineup_viz.build_xi(team_pl, fotmob_hints=fotmob_hints)
            return {
                "players": [
                    {"player": p["player"], "position": p["position"],
                     "minutes": p.get("minutes", 0),
                     "id": p.get("id"), "source": "fotmob"}
                    for p in xi
                ],
                "formation": formation,
            }
        except Exception as exc:
            logger.warning(f"FotMob lineup-players {team_name}: {exc}")

    return {"players": [], "formation": "", "unavailable": True}


@router.get("/team/{team_id}/lineup")
def team_lineup(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    ck = {"type": "team_lineup", "team_id": team_id, "season": season, "v": 11}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    us_slug      = understat.LEAGUE_TO_US.get(league_id)
    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id)

    players: list[dict] = []

    if us_slug:
        us_teams = understat.get_league_teams(us_slug, season)
        us_team  = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
        us_name  = us_team["name"] if us_team else team_name
        players  = understat.get_most_played_xi(us_slug, season, us_name)
    elif fm_league_id and team_id.isdigit():
        try:
            fm_players = fotmob.get_league_player_stats(fm_league_id, season)
            players    = sorted(
                [p for p in fm_players if _team_match(team_name, p.get("team", ""))],
                key=lambda p: p.get("minutes", 0), reverse=True
            )[:15]
            for p in players:
                p["position"] = p.get("pos", "")
        except Exception as exc:
            logger.warning(f"FotMob lineup {team_name}: {exc}")

    if not players:
        from app.viz.common import get_font
        png = lineup_viz._no_data_png(team_name, "Lineup data unavailable", get_font())
        return _png(png)

    manager      = fdorg.get_team_coach(team_id) if team_id.isdigit() else ""
    fotmob_hints = _fotmob_col_hints(team_name)

    png = lineup_viz.render(
        team_name    = team_name,
        season_label = _season_label(season),
        league_label = fdorg.LEAGUE_LABELS.get(league_id, league_id),
        players      = players,
        manager      = manager,
        fotmob_hints = fotmob_hints,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fotmob_col_hints(team_name: str, side: str = "homeTeam") -> dict[str, int] | None:
    """
    Best-effort: look up the most recent FotMob lineup for a team and return
    a dict mapping player last name (lowercase) → column position (1=left, N=right).
    Returns None if FotMob lookup fails.
    """
    try:
        fotmob_team_id = fotmob.search_team(team_name)
        if not fotmob_team_id:
            return None
        fixtures = fotmob.get_team_fixtures(fotmob_team_id)
        if not fixtures:
            return None
        # Take most recent finished match
        recent = fixtures[0]
        lineup = fotmob.get_match_lineup(recent["matchId"])
        if not lineup:
            return None
        # Determine which side this team played as
        home_name = lineup.get("homeTeam", {}).get("name", "")
        if _team_match(team_name, home_name):
            team_data = lineup.get("homeTeam", {})
        else:
            team_data = lineup.get("awayTeam", {})

        hints: dict[str, int] = {}
        for player in team_data.get("players", []):
            name = player.get("name", "")
            last = name.split()[-1].lower() if name else ""
            col  = player.get("col")
            if last and col is not None:
                hints[last] = col
        return hints if hints else None
    except Exception as exc:
        logger.debug(f"FotMob col hints failed for {team_name}: {exc}")
        return None


def _compute_percentiles(
    all_players: list[dict],
    player: dict,
    params: list[str],
    param_map: dict[str, str] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    pmap = param_map if param_map is not None else radar_viz.PARAM_TO_STAT
    percentiles: dict[str, float] = {}
    raw:         dict[str, float] = {}

    for param in params:
        col = pmap.get(param)
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
