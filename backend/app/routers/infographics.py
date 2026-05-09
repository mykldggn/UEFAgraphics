"""
Infographic generation endpoints — all return image/png.

Data sources:
- Shot maps, career xG, xG timeline:  Understat (no limits)
- Radar, summary card:                Understat league player stats (no limits)
- Team season card:                   football-data.org standings + Understat xG
"""
from __future__ import annotations

import logging
import unicodedata

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core import cache
from app.services import football_data_service as fdorg
from app.services import understat_service as understat
from app.services import fotmob_service as fotmob
from app.services import api_football_service as api_football
from app.services import espn_service as espn
from app.services import transfermarkt_service as transfermarkt
from app.viz import (
    shotmap,
    radar as radar_viz,
    summary_card,
    career_xg as career_xg_viz,
    team_xg_timeline,
    team_season_card as team_card_viz,
    lineup_card as lineup_viz,
    player_xg_arc,
    player_shot_quality,
    player_shot_situation,
    player_season_compare,
    player_rolling_form,
    team_squad_minutes as squad_minutes_viz,
    team_match_scatter as match_scatter_viz,
    team_situation as situation_viz,
    team_xpoints as xpoints_viz,
    team_scorer_timeline as scorer_timeline_viz,
    league_xg_table as xg_table_viz,
    league_quadrant as quadrant_viz,
    league_golden_boot as golden_boot_viz,
    league_form_table as form_table_viz,
    league_overperformers as overperformers_viz,
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


def _table_stats(row: dict | None) -> dict:
    if not row:
        return {}
    return {
        "wins":          row.get("wins"),
        "draws":         row.get("draws"),
        "losses":        row.get("losses"),
        "goals_for":     row.get("goals_for"),
        "goals_against": row.get("goals_against"),
        "goal_diff":     row.get("goal_diff"),
        "points":        row.get("points"),
        "final_position": row.get("rank"),
    }


def _merge_missing_stats(stats: dict, incoming: dict) -> None:
    for key, value in incoming.items():
        if value is not None and stats.get(key) in (None, ""):
            stats[key] = value


def _norm_name(name: str) -> str:
    return unicodedata.normalize("NFD", name or "").encode("ascii", "ignore").decode("ascii").lower()


def _player_name(row: dict) -> str:
    return row.get("player") or row.get("player_name") or row.get("name") or ""


def _is_goalkeeper(row: dict) -> bool:
    raw = str(row.get("position") or row.get("pos") or "").upper()
    return raw in {"G", "GK"} or "GK" in raw.split()


def _with_goalkeeper_fallback(
    players: list[dict],
    team_name: str,
    league_id: str,
    season: int,
) -> list[dict]:
    """Understat sometimes lacks GK rows; add recent lineup GKs without touching outfield data."""
    if any(_is_goalkeeper(p) for p in players):
        return players

    existing = {_norm_name(_player_name(p)) for p in players}
    candidates = espn.get_goalkeeper_candidates(team_name, league_id, season)
    candidates += api_football.get_goalkeeper_candidates(team_name, league_id, season)

    additions: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _norm_name(_player_name(candidate))
        if not key or key in existing or key in seen:
            continue
        additions.append(candidate)
        seen.add(key)

    return additions + players


def _safe_hints_for_players(raw_hints: dict | None, players: list[dict]) -> dict | None:
    """Keep full-name hints and only use last-name hints when they cannot collide."""
    if not raw_hints:
        return None

    names = [_player_name(p) for p in players if _player_name(p)]
    last_counts: dict[str, int] = {}
    for name in names:
        last = _norm_name(name.split()[-1])
        if last:
            last_counts[last] = last_counts.get(last, 0) + 1

    full_hint_lasts = {
        key.split()[-1]
        for key in raw_hints
        if " " in key and key.split()
    }

    safe: dict = {}
    for name in names:
        full = _norm_name(name)
        last = _norm_name(name.split()[-1])
        if full in raw_hints:
            safe[full] = raw_hints[full]
            if last_counts.get(last, 0) == 1:
                safe[last] = raw_hints[full]
        elif (
            last in raw_hints
            and last_counts.get(last, 0) == 1
            and last not in full_hint_lasts
        ):
            safe[last] = raw_hints[last]

    return safe or None


def _merge_position_hints(players: list[dict], *hint_sets: dict | None) -> dict | None:
    merged: dict = {}
    for hints in hint_sets:
        safe = _safe_hints_for_players(hints, players)
        if safe:
            merged.update(safe)
    return merged or None


def _safe_place_hints(players: list[dict], raw_hints: dict | None) -> dict | None:
    return _safe_hints_for_players(raw_hints, players)


def _resolve_fdorg_team_id(
    team_id: str,
    team_name: str,
    league_id: str,
    season: int,
) -> str:
    teams = fdorg.get_teams(league_id, season)
    if not teams:
        return team_id if team_id.isdigit() and league_id not in understat.LEAGUE_TO_US else ""

    def matches(team: dict) -> bool:
        return (
            _team_match(team_name, team.get("name", ""))
            or _team_match(team_name, team.get("short", ""))
        )

    id_match = next(
        (t for t in teams if str(t.get("id", "")) == str(team_id) and matches(t)),
        None,
    )
    if id_match:
        return str(id_match["id"])

    name_match = next((t for t in teams if matches(t)), None)
    if name_match and str(name_match.get("id", "")).isdigit():
        return str(name_match["id"])
    return ""


def _match_key(row: dict) -> tuple[str, str, int, int]:
    return (
        str(row.get("date", ""))[:10],
        str(row.get("h_a", "")).upper(),
        int(row.get("goals") or 0),
        int(row.get("goals_against") or 0),
    )


def _enrich_history_opponents(history: list[dict], results: list[dict]) -> list[dict]:
    """Copy opponent names/crests onto xG rows from a matching match-results feed."""
    if not history or not results:
        return history

    by_match: dict[tuple[str, str, int, int], list[dict]] = {}
    for result in results:
        by_match.setdefault(_match_key(result), []).append(result)

    can_fallback_by_index = len(history) == len(results)
    enriched: list[dict] = []
    for idx, row in enumerate(history):
        match = None
        bucket = by_match.get(_match_key(row))
        if bucket:
            match = bucket.pop(0)
        elif can_fallback_by_index:
            match = results[idx]

        if not match:
            enriched.append(row)
            continue

        merged = dict(row)
        merged["opponent"] = merged.get("opponent") or match.get("opponent", "")
        merged["opponent_crest"] = (
            merged.get("opponent_crest") or match.get("opponent_crest", "")
        )
        enriched.append(merged)
    return enriched


def _enrich_history_from_fdorg(
    history: list[dict],
    team_id: str,
    team_name: str,
    league_id: str | None,
    season: int,
) -> list[dict]:
    if not history or not league_id:
        return history

    try:
        fdorg_id = _resolve_fdorg_team_id(team_id, team_name, league_id, season)
        if not fdorg_id:
            return history
        results = fdorg.get_team_results(fdorg_id, season)
    except Exception as exc:
        logger.debug("opponent enrichment failed for %s/%s: %s", team_name, season, exc)
        return history

    return _enrich_history_opponents(history, results)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER — shot based (Understat player ID)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/player/{player_id}/shotmap")
def player_shotmap(
    player_id: str,
    season: int = Query(None),
):
    ck = {"type": "shotmap", "player_id": player_id, "season": season or "all", "v": 2}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

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

    pos_key = position[:2].upper()

    us_slug  = understat.LEAGUE_TO_US.get(league_id)
    fm_id    = fotmob.FOTMOB_LEAGUES.get(league_id)

    if us_slug:
        # ── Understat path (top-5 leagues) ────────────────────────────────────
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
            player_name         = player_row.get("player", player_id),
            position            = position,
            season_label        = _season_label(season),
            percentiles         = pcts,
            raw_values          = raw,
            team                = player_row.get("team", ""),
            compare_name        = None,
            compare_percentiles = comp_pcts,
        )
        cache.img_save("infographic", ck, png)
        return _png(png)

    elif fm_id:
        # ── FotMob pool path (non-top-5 leagues) ─────────────────────────────
        all_players = fotmob.get_league_player_stats(fm_id, season)
        if not all_players:
            raise HTTPException(503, "Could not load league player stats")

        player_row = next((p for p in all_players if p["id"] == str(player_id)), None)
        if player_row is None:
            raise HTTPException(404, f"No stats found for player {player_id} in {season}")

        params    = radar_viz.FOTMOB_POSITION_PARAMS.get(pos_key, radar_viz.FOTMOB_ATTACKER_PARAMS)
        pcts, raw = _compute_percentiles(all_players, player_row, params,
                                         param_map=radar_viz.PARAM_TO_STAT)
        png = radar_viz.render(
            player_name         = player_row.get("player", player_id),
            position            = position,
            season_label        = _season_label(season),
            percentiles         = pcts,
            raw_values          = raw,
            team                = player_row.get("team", ""),
            compare_name        = None,
            compare_percentiles = None,
        )
        cache.img_save("infographic", ck, png)
        return _png(png)

    raise HTTPException(400, f"Radar not available for {league_id}")


@router.get("/player/{player_id}/summary-card")
def player_summary_card(
    player_id: str,
    league_id: str = Query(None),
    season: int    = Query(None),
    position: str  = Query("FW"),
):
    ck = {"type": "summary_card", "player_id": player_id,
          "league_id": league_id, "season": season or "all"}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    us_slug = understat.LEAGUE_TO_US.get(league_id) if league_id else None
    fm_id   = fotmob.FOTMOB_LEAGUES.get(league_id) if league_id else None

    if fm_id and not us_slug:
        # ── FotMob pool path (non-top-5 leagues) ─────────────────────────────
        if season is None:
            raise HTTPException(400, "Season required for non-top-5 league summary cards")
        all_players = fotmob.get_league_player_stats(fm_id, season)
        if not all_players:
            raise HTTPException(503, "Could not load league player stats")
        player_row = next((p for p in all_players if p["id"] == str(player_id)), None)
        if player_row is None:
            raise HTTPException(404, f"No stats found for player {player_id} in {season}")
        stats = {
            "goals":      player_row.get("goals", 0),
            "assists":    player_row.get("assists", 0),
            "xG":         round(float(player_row.get("xg", 0)), 2),
            "xA":         round(float(player_row.get("xa", 0)), 2),
            "shots":      player_row.get("shots", 0),
            "key_passes": player_row.get("key_passes", 0),
            "minutes":    player_row.get("minutes", 0),
            "apps":       player_row.get("apps", 0),
        }
        png = summary_card.render(
            player_name  = player_row.get("player", player_id),
            position     = position,
            team         = player_row.get("team", ""),
            season_label = _season_label(season),
            stats        = stats,
            league_label = fdorg.LEAGUE_LABELS.get(league_id, league_id),
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
        ck = {"type": "team_xg_timeline", "team_id": us_team_id, "season": season, "v": 2}
        if cached := cache.img_get("infographic", ck):
            return _png(cached)
        try:
            history = understat.get_team_xg_history(us_team_id, season, league=us_slug)
            history = _enrich_history_from_fdorg(
                history, team_id, team_name, league_id, season
            )
        except Exception as exc:
            logger.error(f"team xg timeline {us_team_id}/{season}: {exc}")

    elif fm_league_id:
        # Non-top-5 + FotMob available: real xG per match
        fm_tid = fotmob.resolve_fotmob_team_id(team_name, fm_league_id, season)
        if fm_tid:
            has_xg = True
            ck = {"type": "team_timeline_fotmob", "fm_tid": fm_tid,
                  "league_id": fm_league_id, "season": season, "v": 2}
            if cached := cache.img_get("infographic", ck):
                return _png(cached)
            try:
                history = fotmob.get_team_season_xg(fm_tid, fm_league_id, season)
            except Exception as exc:
                logger.error(f"team xg timeline fotmob {fm_tid}/{season}: {exc}")

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
        ck = {"type": "team_timeline_fdorg", "team_id": fdorg_id, "season": season, "v": 2}
        if cached := cache.img_get("infographic", ck):
            return _png(cached)
        try:
            history = fdorg.get_team_results(fdorg_id, season)
        except Exception as exc:
            logger.error(f"team results fdorg {fdorg_id}/{season}: {exc}")

    if not history:
        raise HTTPException(503, "No match data available for this team/season")

    opponents: list[dict] | None = [
        {
            "name": h.get("opponent", ""),
            "crest_url": h.get("opponent_crest", ""),
        }
        for h in history
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
    ck = {"type": "team_season_card", "team_id": team_id, "season": season, "v": 6}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)

    us_slug      = understat.LEAGUE_TO_US.get(league_id)
    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id) if league_id else None

    # Standings from football-data.org, then FotMob for leagues football-data
    # does not cover or when team names/IDs do not line up.
    table    = fdorg.get_standings(league_id, season)
    team_row = next(
        (r for r in table if _team_match(team_name, r.get("team", ""))), None
    )
    if not table or not team_row:
        af_table = api_football.get_standings(league_id, season)
        if af_table:
            table = af_table
            team_row = next(
                (r for r in table if _team_match(team_name, r.get("team", ""))), None
            )

    if (not table or not team_row) and fm_league_id:
        fm_table = fotmob.get_league_table(fm_league_id, season)
        if fm_table:
            table = fm_table
            team_row = next(
                (r for r in table if _team_match(team_name, r.get("team", ""))), None
            )

    stats: dict = {}
    pos_h: list[dict] = []
    if team_row:
        stats = _table_stats(team_row)
        rank  = team_row.get("rank", 1)
        played = int(team_row.get("played") or 38)
        pos_h = [{"matchday": 1, "position": rank},
                 {"matchday": max(1, played), "position": rank}]

    # Top scorers from football-data.org (baseline — may be overwritten below)
    top_scorers = fdorg.get_top_scorers(league_id, season, limit=8)
    if not top_scorers:
        top_scorers = api_football.get_top_scorers(league_id, season, limit=8)
    top_scorers = [s for s in top_scorers if _team_match(team_name, s.get("team", ""))]

    if us_slug:
        # ── Understat enrichment (top-5 leagues) ─────────────────────────────
        try:
            us_teams = understat.get_league_teams(us_slug, season)
            us_team  = next(
                (t for t in us_teams if _team_match(team_name, t["name"])), None
            )
            if us_team:
                _merge_missing_stats(stats, {
                    "wins":          us_team.get("wins"),
                    "draws":         us_team.get("draws"),
                    "losses":        us_team.get("loses"),
                    "goals_for":     us_team.get("goals_for"),
                    "goals_against": us_team.get("goals_against"),
                    "goal_diff":     (us_team.get("goals_for", 0) - us_team.get("goals_against", 0)),
                    "points":        us_team.get("pts"),
                })
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

    elif fm_league_id:
        # ── FotMob enrichment (non-top-5 leagues) ────────────────────────────
        try:
            if not team_row:
                fm_table = fotmob.get_league_table(fm_league_id, season)
                team_row = next(
                    (r for r in fm_table if _team_match(team_name, r.get("team", ""))), None
                )
            _merge_missing_stats(stats, _table_stats(team_row))

            fm_tid = fotmob.resolve_fotmob_team_id(team_name, fm_league_id, season)
            if not fm_tid:
                if team_row and str(team_row.get("team_id", "")).isdigit():
                    fm_tid = int(team_row["team_id"])
            if fm_tid:
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
    us_slug      = understat.LEAGUE_TO_US.get(league_id)
    fm_league_id = fotmob.FOTMOB_LEAGUES.get(league_id)

    espn_pos, formation_hint, place_hints = espn.get_team_lineup_hints(team_name, league_id, season)
    af_pos, af_formation, af_place_hints = api_football.get_team_lineup_hints(team_name, league_id, season)
    formation_hint = formation_hint or af_formation
    place_hints = place_hints or af_place_hints

    if us_slug:
        us_teams = understat.get_league_teams(us_slug, season)
        us_team  = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
        us_name  = us_team["name"] if us_team else team_name
        players  = understat.get_most_played_xi(us_slug, season, us_name)
        if not players:
            return {"players": [], "formation": ""}
        players  = _with_goalkeeper_fallback(players, team_name, league_id, season)
        names    = [p.get("player", "") for p in players]
        tm_pos   = transfermarkt.get_team_position_hints(names)
        pos_hints = _merge_position_hints(players, af_pos, espn_pos, tm_pos)
        safe_places = _safe_place_hints(players, place_hints)
        xi, formation = lineup_viz.build_xi(
            players, pos_hints=pos_hints, forced_formation=formation_hint,
            place_hints=safe_places)
        player_pool = understat.get_league_player_stats(us_slug, season)
        id_map = {p["player"]: p["id"] for p in player_pool}
        return {
            "players": [
                {"player": p["player"], "position": p["position"],
                 "role": p.get("role"),
                 "minutes": p["minutes"], "id": id_map.get(p["player"]),
                 "source": "understat" if id_map.get(p["player"]) else "lineup"}
                for p in xi
            ],
            "formation": formation,
        }

    if fm_league_id:
        try:
            fm_players = fotmob.get_league_player_stats(fm_league_id, season)
            team_pl    = sorted(
                [p for p in fm_players if _team_match(team_name, p.get("team", ""))],
                key=lambda p: p.get("minutes", 0), reverse=True
            )[:15]
            if not team_pl:
                return {"players": [], "formation": ""}
            names    = [p.get("player", p.get("player_name", "")) for p in team_pl]
            tm_pos   = transfermarkt.get_team_position_hints(names)
            pos_hints = _merge_position_hints(team_pl, af_pos, espn_pos, tm_pos)
            safe_places = _safe_place_hints(team_pl, place_hints)
            xi, formation = lineup_viz.build_xi(
                team_pl, pos_hints=pos_hints, forced_formation=formation_hint,
                place_hints=safe_places)
            return {
                "players": [
                    {"player": p["player"], "position": p["position"],
                     "role": p.get("role"),
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
    ck = {"type": "team_lineup", "team_id": team_id, "season": season, "v": 43}
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
        players  = _with_goalkeeper_fallback(players, team_name, league_id, season)
    elif fm_league_id:
        try:
            fm_players = fotmob.get_league_player_stats(fm_league_id, season)
            players    = sorted(
                [p for p in fm_players if _team_match(team_name, p.get("team", ""))],
                key=lambda p: p.get("minutes", 0), reverse=True
            )[:15]
        except Exception as exc:
            logger.warning(f"FotMob lineup {team_name}: {exc}")

    if not players:
        from app.viz.common import get_font
        png = lineup_viz._no_data_png(team_name, "Lineup data unavailable", get_font())
        return _png(png)

    espn_pos, formation_hint, place_hints = espn.get_team_lineup_hints(team_name, league_id, season)
    af_pos, af_formation, af_place_hints = api_football.get_team_lineup_hints(team_name, league_id, season)
    formation_hint = formation_hint or af_formation
    place_hints = place_hints or af_place_hints
    names     = [p.get("player", p.get("player_name", "")) for p in players]
    tm_pos    = transfermarkt.get_team_position_hints(names)
    pos_hints = _merge_position_hints(players, af_pos, espn_pos, tm_pos)
    place_hints = _safe_place_hints(players, place_hints)

    fdorg_team_id = _resolve_fdorg_team_id(team_id, team_name, league_id, season)
    manager = fdorg.get_team_coach(fdorg_team_id) if fdorg_team_id else ""

    png = lineup_viz.render(
        team_name        = team_name,
        season_label     = _season_label(season),
        league_label     = fdorg.LEAGUE_LABELS.get(league_id, league_id),
        players          = players,
        manager          = manager,
        pos_hints        = pos_hints,
        forced_formation = formation_hint,
        place_hints      = place_hints,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER — shot-based analytics (Understat top-5 leagues only)
# ─────────────────────────────────────────────────────────────────────────────

def _player_shots_season(player_id: str, season: int):
    """Fetch and filter shots for a player/season. Raises 503 on failure."""
    try:
        shots = understat.get_player_shots(player_id)
    except Exception as exc:
        logger.error(f"shots {player_id}: {exc}")
        raise HTTPException(503, "Failed to fetch shot data")
    if season is not None and not shots.empty:
        shots = shots[shots["season"] == season]
    return shots


@router.get("/player/{player_id}/xg-arc")
def player_xg_arc_img(player_id: str, season: int = Query(...)):
    ck = {"type": "xg_arc", "player_id": player_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    shots = _player_shots_season(player_id, season)
    meta  = understat.get_player_meta(player_id)
    png   = player_xg_arc.render(shots, meta.get("name", player_id), _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/shot-quality")
def player_shot_quality_img(player_id: str, season: int = Query(...)):
    ck = {"type": "shot_quality", "player_id": player_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    shots = _player_shots_season(player_id, season)
    meta  = understat.get_player_meta(player_id)
    png   = player_shot_quality.render(shots, meta.get("name", player_id), _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/shot-situation")
def player_shot_situation_img(player_id: str, season: int = Query(...)):
    ck = {"type": "shot_situation", "player_id": player_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    shots = _player_shots_season(player_id, season)
    meta  = understat.get_player_meta(player_id)
    png   = player_shot_situation.render(shots, meta.get("name", player_id), _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/season-compare")
def player_season_compare_img(player_id: str):
    ck = {"type": "season_compare", "player_id": player_id, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    meta = understat.get_player_meta(player_id)
    png  = player_season_compare.render(meta.get("season_stats", []), meta.get("name", player_id))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/player/{player_id}/rolling-form")
def player_rolling_form_img(player_id: str, season: int = Query(...)):
    ck = {"type": "rolling_form", "player_id": player_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    shots = _player_shots_season(player_id, season)
    meta  = understat.get_player_meta(player_id)
    png   = player_rolling_form.render(shots, meta.get("name", player_id), _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# TEAM — analytics (new)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/team/{team_id}/squad-minutes")
def team_squad_minutes_img(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    ck = {"type": "squad_minutes", "team_id": team_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Squad minutes requires an Understat league")
    us_teams  = understat.get_league_teams(us_slug, season)
    us_team   = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
    us_name   = us_team["name"] if us_team else team_name
    all_pl    = understat.get_league_player_stats(us_slug, season)
    players   = [p for p in all_pl if p.get("team") == us_name]
    png = squad_minutes_viz.render(players, team_name, _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/{team_id}/match-scatter")
def team_match_scatter_img(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    ck = {"type": "match_scatter", "team_id": team_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Match scatter requires an Understat league")
    us_teams = understat.get_league_teams(us_slug, season)
    us_team  = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
    us_id    = us_team["id"] if us_team else team_id
    history  = understat.get_team_xg_history(us_id, season, us_slug)
    png = match_scatter_viz.render(history, team_name, _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/{team_id}/situation")
def team_situation_img(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    ck = {"type": "situation", "team_id": team_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Situation breakdown requires an Understat league")
    us_teams = understat.get_league_teams(us_slug, season)
    us_team  = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
    us_id    = us_team["id"] if us_team else team_id
    shots_df = understat.get_team_shots(us_id, season, us_slug)
    png = situation_viz.render(shots_df, team_name, _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/{team_id}/xpoints")
def team_xpoints_img(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    ck = {"type": "xpoints", "team_id": team_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "xPoints requires an Understat league")

    us_teams    = understat.get_league_teams(us_slug, season)
    us_team     = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
    if not us_team:
        raise HTTPException(404, f"Team {team_name} not found in Understat")

    xpts = float(us_team.get("xPts") or 0)
    xg   = float(us_team.get("xG")   or 0)
    xga  = float(us_team.get("xGA")  or 0)

    sorted_by_xpts = sorted(us_teams, key=lambda t: float(t.get("xPts") or 0), reverse=True)
    xg_rank = next((i + 1 for i, t in enumerate(sorted_by_xpts)
                    if _team_match(team_name, t["name"])), len(us_teams))

    table        = fdorg.get_standings(league_id, season)
    team_row     = next((r for r in table if _team_match(team_name, r.get("team", ""))), None)
    actual_pts   = int(team_row.get("points") or 0) if team_row else 0
    actual_rank  = next((i + 1 for i, r in enumerate(table)
                         if _team_match(team_name, r.get("team", ""))), len(table))

    league_avg_xg  = round(sum(float(t.get("xG",  0)) for t in us_teams) / len(us_teams), 2) if us_teams else 0
    league_avg_xga = round(sum(float(t.get("xGA", 0)) for t in us_teams) / len(us_teams), 2) if us_teams else 0

    png = xpoints_viz.render(
        team_name=team_name,
        season_label=_season_label(season),
        league_label=fdorg.LEAGUE_LABELS.get(league_id, league_id),
        actual_pts=actual_pts, xpts=xpts, xg=xg, xga=xga,
        actual_rank=actual_rank, xg_rank=xg_rank,
        league_avg_xg=league_avg_xg, league_avg_xga=league_avg_xga,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/team/{team_id}/scorer-timeline")
def team_scorer_timeline_img(
    team_id:   str,
    team_name: str = Query(...),
    league_id: str = Query(...),
    season:    int = Query(...),
):
    ck = {"type": "scorer_timeline", "team_id": team_id, "season": season, "v": 1}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Scorer timeline requires an Understat league")
    us_teams = understat.get_league_teams(us_slug, season)
    us_team  = next((t for t in us_teams if _team_match(team_name, t["name"])), None)
    us_id    = us_team["id"] if us_team else team_id
    shots_df = understat.get_team_shots(us_id, season, us_slug)
    png = scorer_timeline_viz.render(shots_df, team_name, _season_label(season))
    cache.img_save("infographic", ck, png)
    return _png(png)


# ─────────────────────────────────────────────────────────────────────────────
# LEAGUE — infographic images
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/league/{league_id}/xg-table")
def league_xg_table_img(league_id: str, season: int = Query(...)):
    ck = {"type": "league_xg_table", "league_id": league_id, "season": season, "v": 3}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "xG table requires an Understat league")
    teams = understat.get_league_teams(us_slug, season)
    teams_sorted = sorted(teams, key=lambda t: float(t.get("pts") or 0), reverse=True)
    png = xg_table_viz.render(
        fdorg.LEAGUE_LABELS.get(league_id, league_id),
        _season_label(season),
        teams_sorted,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/league/{league_id}/quadrant")
def league_quadrant_img(league_id: str, season: int = Query(...)):
    ck = {"type": "league_quadrant", "league_id": league_id, "season": season, "v": 2}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Quadrant chart requires an Understat league")
    teams = understat.get_league_teams(us_slug, season)
    png   = quadrant_viz.render(
        fdorg.LEAGUE_LABELS.get(league_id, league_id),
        _season_label(season),
        teams,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/league/{league_id}/golden-boot")
def league_golden_boot_img(league_id: str, season: int = Query(...)):
    ck = {"type": "league_golden_boot", "league_id": league_id, "season": season, "v": 2}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Golden boot requires an Understat league")
    players = understat.get_league_player_stats(us_slug, season)
    png     = golden_boot_viz.render(
        fdorg.LEAGUE_LABELS.get(league_id, league_id),
        _season_label(season),
        players,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/league/{league_id}/form-table")
def league_form_table_img(league_id: str, season: int = Query(...)):
    ck = {"type": "league_form_table", "league_id": league_id, "season": season, "v": 2}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    teams: list[dict] = []
    if us_slug:
        us_teams = understat.get_league_teams(us_slug, season)
        teams    = sorted(us_teams, key=lambda t: float(t.get("pts") or 0), reverse=True)
    else:
        table = fdorg.get_standings(league_id, season)
        teams = [{"name": r.get("team",""), "pts": r.get("points",0),
                  "form": r.get("form",""), "wins": r.get("wins",0),
                  "draws": r.get("draws",0), "loses": r.get("losses",0)} for r in table]
    png = form_table_viz.render(
        fdorg.LEAGUE_LABELS.get(league_id, league_id),
        _season_label(season),
        teams,
    )
    cache.img_save("infographic", ck, png)
    return _png(png)


@router.get("/league/{league_id}/overperformers")
def league_overperformers_img(league_id: str, season: int = Query(...)):
    ck = {"type": "league_overperformers", "league_id": league_id, "season": season, "v": 3}
    if cached := cache.img_get("infographic", ck):
        return _png(cached)
    us_slug = understat.LEAGUE_TO_US.get(league_id)
    if not us_slug:
        raise HTTPException(400, "Overperformers requires an Understat league")

    us_teams = understat.get_league_teams(us_slug, season)
    table    = fdorg.get_standings(league_id, season)

    merged: list[dict] = []
    for t in us_teams:
        fdrow = next((r for r in table if _team_match(t["name"], r.get("team",""))), None)
        actual_pts = int(fdrow.get("points") or 0) if fdrow else int(t.get("pts") or 0)
        merged.append({
            "name":       t["name"],
            "pts":        actual_pts,
            "xPts":       float(t.get("xPts") or 0),
            "xG":         float(t.get("xG")   or 0),
            "xGA":        float(t.get("xGA")  or 0),
        })

    png = overperformers_viz.render(
        fdorg.LEAGUE_LABELS.get(league_id, league_id),
        _season_label(season),
        merged,
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
