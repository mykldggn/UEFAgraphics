"""
FBref data layer via the soccerdata library.
Covers all major European leagues + Top 4 English divisions + national teams.

League IDs map to soccerdata's FBref league strings.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import soccerdata as sd

from app.config import settings
from app.core import cache

logger = logging.getLogger(__name__)

# Point soccerdata at our cache dir
os.environ.setdefault("SOCCERDATA_DIR", str(Path(settings.SOCCERDATA_DIR).resolve()))

# ── League registry ──────────────────────────────────────────────────────────
# key: our internal ID  |  value: FBref league name used by soccerdata
FBREF_LEAGUES: dict[str, str] = {
    # England
    "ENG-1": "ENG-Premier League",
    "ENG-2": "ENG-Championship",
    "ENG-3": "ENG-League One",
    "ENG-4": "ENG-League Two",
    # Spain
    "ESP-1": "ESP-La Liga",
    # Germany
    "DEU-1": "DEU-Bundesliga",
    # Italy
    "ITA-1": "ITA-Serie A",
    # France
    "FRA-1": "FRA-Ligue 1",
    # Netherlands
    "NED-1": "NED-Eredivisie",
    # Portugal
    "PRT-1": "PRT-Primeira Liga",
    # Belgium
    "BEL-1": "BEL-First Division A",
    # Scotland
    "SCO-1": "SCO-Scottish Premiership",
    # Switzerland
    "CHE-1": "CHE-Super League",
    # Turkey
    "TUR-1": "TUR-Süper Lig",
    # Greece
    "GRC-1": "GRC-Super League",
    # Austria
    "AUT-1": "AUT-Austrian Football Bundesliga",
    # Russia (pre-sanctions era data still accessible)
    "RUS-1": "RUS-Russian Premier League",
    # European competitions
    "UEFA-CL": "UEFA-Champions League",
    "UEFA-EL": "UEFA-Europa League",
    "UEFA-ECL": "UEFA-Europa Conference League",
    # International
    "INT-EUROS": "INT-European Championship",
    "INT-WC": "INT-World Cup",
    "INT-NL": "INT-UEFA Nations League",
    "INT-AFCON": "INT-Africa Cup of Nations",
    "INT-COPA": "INT-Copa América",
}

LEAGUE_LABELS: dict[str, str] = {
    "ENG-1": "Premier League",
    "ENG-2": "Championship",
    "ENG-3": "League One",
    "ENG-4": "League Two",
    "ESP-1": "La Liga",
    "DEU-1": "Bundesliga",
    "ITA-1": "Serie A",
    "FRA-1": "Ligue 1",
    "NED-1": "Eredivisie",
    "PRT-1": "Primeira Liga",
    "BEL-1": "First Division A",
    "SCO-1": "Scottish Premiership",
    "CHE-1": "Super League",
    "TUR-1": "Süper Lig",
    "GRC-1": "Super League Greece",
    "AUT-1": "Austrian Bundesliga",
    "RUS-1": "Russian Premier League",
    "UEFA-CL": "Champions League",
    "UEFA-EL": "Europa League",
    "UEFA-ECL": "Conference League",
    "INT-EUROS": "European Championship",
    "INT-WC": "World Cup",
    "INT-NL": "UEFA Nations League",
    "INT-AFCON": "AFCON",
    "INT-COPA": "Copa América",
}

LEAGUE_COUNTRY: dict[str, str] = {
    "ENG-1": "England", "ENG-2": "England", "ENG-3": "England", "ENG-4": "England",
    "ESP-1": "Spain", "DEU-1": "Germany", "ITA-1": "Italy", "FRA-1": "France",
    "NED-1": "Netherlands", "PRT-1": "Portugal", "BEL-1": "Belgium",
    "SCO-1": "Scotland", "CHE-1": "Switzerland", "TUR-1": "Turkey",
    "GRC-1": "Greece", "AUT-1": "Austria", "RUS-1": "Russia",
    "UEFA-CL": "Europe", "UEFA-EL": "Europe", "UEFA-ECL": "Europe",
    "INT-EUROS": "International", "INT-WC": "International",
    "INT-NL": "International", "INT-AFCON": "International", "INT-COPA": "International",
}


def fbref_id(league_id: str) -> str:
    return FBREF_LEAGUES[league_id]


def _fbref(league_id: str, season: int) -> sd.FBref:
    return sd.FBref(leagues=fbref_id(league_id), seasons=season)


# ── Teams ────────────────────────────────────────────────────────────────────

def get_teams(league_id: str, season: int) -> list[dict]:
    key = {"league": league_id, "season": season}
    cached = cache.json_get("fbref_teams", key, ttl_hours=48)
    if cached is not None:
        return cached
    try:
        fb = _fbref(league_id, season)
        df = fb.read_team_season_stats(stat_type="standard")
        df = df.reset_index()
        teams = [
            {"id": str(r.get("team", "")), "name": str(r.get("team", ""))}
            for _, r in df.iterrows()
            if r.get("team")
        ]
        teams = list({t["id"]: t for t in teams}.values())
        cache.json_save("fbref_teams", key, teams)
        return teams
    except Exception as exc:
        logger.error(f"get_teams {league_id}/{season}: {exc}")
        return []


# ── Player stats ─────────────────────────────────────────────────────────────

def get_player_standard_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "standard"}
    cached = cache.json_get("fbref_player_std", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_player_season_stats(stat_type="standard")
        df = df.reset_index()
        cache.json_save("fbref_player_std", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"player_standard {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_player_shooting_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "shooting"}
    cached = cache.json_get("fbref_player_shooting", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_player_season_stats(stat_type="shooting")
        df = df.reset_index()
        cache.json_save("fbref_player_shooting", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"player_shooting {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_player_passing_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "passing"}
    cached = cache.json_get("fbref_player_passing", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_player_season_stats(stat_type="passing")
        df = df.reset_index()
        cache.json_save("fbref_player_passing", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"player_passing {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_player_misc_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "misc"}
    cached = cache.json_get("fbref_player_misc", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_player_season_stats(stat_type="misc")
        df = df.reset_index()
        cache.json_save("fbref_player_misc", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"player_misc {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_player_defense_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "defense"}
    cached = cache.json_get("fbref_player_defense", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_player_season_stats(stat_type="defense")
        df = df.reset_index()
        cache.json_save("fbref_player_defense", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"player_defense {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_player_possession_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "possession"}
    cached = cache.json_get("fbref_player_poss", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_player_season_stats(stat_type="possession")
        df = df.reset_index()
        cache.json_save("fbref_player_poss", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"player_possession {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_combined_player_stats(league_id: str, season: int) -> pd.DataFrame:
    """Merge standard + shooting + passing into one wide DataFrame per player."""
    std = get_player_standard_stats(league_id, season)
    shoot = get_player_shooting_stats(league_id, season)
    passing = get_player_passing_stats(league_id, season)

    if std.empty:
        return pd.DataFrame()

    # Key columns that identify a player row uniquely
    merge_on = [c for c in ["player", "team", "nationality", "pos"] if c in std.columns]

    df = std.copy()
    if not shoot.empty:
        shared = [c for c in shoot.columns if c in df.columns and c not in merge_on]
        shoot_clean = shoot.drop(columns=shared, errors="ignore")
        df = df.merge(shoot_clean, on=merge_on, how="left", suffixes=("", "_sh"))
    if not passing.empty:
        shared = [c for c in passing.columns if c in df.columns and c not in merge_on]
        pass_clean = passing.drop(columns=shared, errors="ignore")
        df = df.merge(pass_clean, on=merge_on, how="left", suffixes=("", "_pa"))

    return df


# ── Team stats ───────────────────────────────────────────────────────────────

def get_team_standard_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "team_standard"}
    cached = cache.json_get("fbref_team_std", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_team_season_stats(stat_type="standard")
        df = df.reset_index()
        cache.json_save("fbref_team_std", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"team_standard {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_team_shooting_stats(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season, "stat": "team_shooting"}
    cached = cache.json_get("fbref_team_shooting", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_team_season_stats(stat_type="shooting")
        df = df.reset_index()
        cache.json_save("fbref_team_shooting", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"team_shooting {league_id}/{season}: {exc}")
        return pd.DataFrame()


def get_league_table(league_id: str, season: int) -> pd.DataFrame:
    key = {"league": league_id, "season": season}
    cached = cache.json_get("fbref_league_table", key, ttl_hours=24)
    if cached is not None:
        return pd.DataFrame(cached)
    try:
        fb = _fbref(league_id, season)
        df = fb.read_league_table()
        df = df.reset_index()
        cache.json_save("fbref_league_table", key, df.to_dict(orient="records"))
        return df
    except Exception as exc:
        logger.error(f"league_table {league_id}/{season}: {exc}")
        return pd.DataFrame()


def search_players_fbref(query: str, league_id: str, season: int) -> list[dict]:
    """Filter combined player stats by name query."""
    df = get_player_standard_stats(league_id, season)
    if df.empty or "player" not in df.columns:
        return []
    mask = df["player"].str.lower().str.contains(query.lower(), na=False)
    matches = df[mask][["player", "team", "pos"]].drop_duplicates().head(20)
    return matches.to_dict(orient="records")
