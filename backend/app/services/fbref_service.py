"""
FBref data layer — uses direct scraping via fbref_scraper (no soccerdata).
Public interface is the same as before so routers don't change.

Column normalisation produces a canonical schema:
  player, team, pos, age, nationality, apps, minutes, nineties,
  goals, assists, xg, npxg, xag, shots, shots_on,
  pass_cmp_pct, key_passes, prog_passes,
  tackles, interceptions, blocks, clearances, errors, pressures,
  dribbles_succ, dribbles_att, fouls_won, fouls,
  aerials_won, aerials_lost,
  + computed per-90 and percentage columns
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.core import cache
from app.services import fbref_scraper as scraper

logger = logging.getLogger(__name__)

LEAGUE_LABELS  = {lid: f"{slug.replace('-', ' ')}" for lid, (_, slug) in scraper.LEAGUE_MAP.items()}
LEAGUE_COUNTRY: dict[str, str] = {
    "ENG-1": "England",  "ENG-2": "England",  "ENG-3": "England",  "ENG-4": "England",
    "ESP-1": "Spain",    "DEU-1": "Germany",  "ITA-1": "Italy",    "FRA-1": "France",
    "NED-1": "Netherlands", "PRT-1": "Portugal", "BEL-1": "Belgium",
    "SCO-1": "Scotland", "CHE-1": "Switzerland", "TUR-1": "Turkey",
    "GRC-1": "Greece",   "AUT-1": "Austria",  "RUS-1": "Russia",
    "UEFA-CL": "Europe", "UEFA-EL": "Europe", "UEFA-ECL": "Europe",
    "INT-EUROS": "International", "INT-WC": "International",
    "INT-NL": "International",
}

# Better display labels
_LABELS: dict[str, str] = {
    "ENG-1": "Premier League",     "ENG-2": "Championship",
    "ENG-3": "League One",         "ENG-4": "League Two",
    "ESP-1": "La Liga",            "DEU-1": "Bundesliga",
    "ITA-1": "Serie A",            "FRA-1": "Ligue 1",
    "NED-1": "Eredivisie",         "PRT-1": "Primeira Liga",
    "BEL-1": "First Division A",   "SCO-1": "Scottish Premiership",
    "CHE-1": "Super League",       "TUR-1": "Süper Lig",
    "GRC-1": "Super League Greece","AUT-1": "Austrian Bundesliga",
    "RUS-1": "Russian Premier League",
    "UEFA-CL": "Champions League", "UEFA-EL": "Europa League",
    "UEFA-ECL": "Conference League",
    "INT-EUROS": "European Championship", "INT-WC": "World Cup",
    "INT-NL": "UEFA Nations League",
}
LEAGUE_LABELS = _LABELS  # re-assign with nice names


# ── FBref column → our canonical name ─────────────────────────────────────────
# Applied after _flatten_columns; we take the FIRST matching column.
_RENAME_STD: dict[str, str] = {
    "Player": "player", "Squad": "team", "Pos": "pos",
    "Age": "age", "Nation": "nationality",
    "MP": "apps", "Min": "minutes",
    "Gls": "goals", "Ast": "assists",
    "xG": "xg", "npxG": "npxg", "xAG": "xag",
    "PrgP": "prog_passes", "PrgC": "prog_carries",
}
_RENAME_SHOOT: dict[str, str] = {
    "Player": "player", "Squad": "team",
    "Sh": "shots", "SoT": "shots_on",
    "Dist": "shot_distance",
}
_RENAME_PASS: dict[str, str] = {
    "Player": "player", "Squad": "team",
    "Cmp%": "pass_cmp_pct", "KP": "key_passes",
}
_RENAME_DEF: dict[str, str] = {
    "Player": "player", "Squad": "team",
    "Tkl": "tackles", "Int": "interceptions",
    "Clr": "clearances", "Blocks": "blocks", "Err": "errors",
}
_RENAME_MISC: dict[str, str] = {
    "Player": "player", "Squad": "team",
    "Press": "pressures",
    "Fld": "fouls_won", "Fls": "fouls",
    "Won": "aerials_won", "Lost": "aerials_lost",
}
_RENAME_POSS: dict[str, str] = {
    "Player": "player", "Squad": "team",
    "Succ": "dribbles_succ", "Att": "dribbles_att",
}
_RENAME_GK: dict[str, str] = {
    "Player": "player", "Squad": "team",
    "GA": "goals_against", "GA90": "ga_p90",
    "Saves": "saves", "Save%": "save_pct",
    "CS": "clean_sheets", "CS%": "clean_sheet_pct",
    "PSxG-GA": "psxg_net",
}


def _normalise(df: pd.DataFrame, rename: dict[str, str]) -> pd.DataFrame:
    """Apply rename map, keep only first occurrence of each source col."""
    df = df.copy()
    for src, dst in rename.items():
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})
    # Numeric coercion on everything except string identity cols
    str_cols = {"player", "team", "pos", "age", "nationality"}
    for col in df.columns:
        if col not in str_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _add_per90(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-90 and percentage derivative columns."""
    df = df.copy()
    nineties = (df.get("minutes", pd.Series(dtype=float)) / 90).replace(0, np.nan)

    def p90(col: str, out: str) -> None:
        if col in df.columns:
            df[out] = (df[col] / nineties).round(2)

    p90("goals",        "goals_p90")
    p90("assists",      "assists_p90")
    p90("xg",          "xg_p90")
    p90("npxg",        "npxg_p90")
    p90("xag",         "xag_p90")
    p90("shots",       "shots_p90")
    p90("shots_on",    "shots_on_p90")
    p90("tackles",     "tackles_p90")
    p90("interceptions","ints_p90")
    p90("blocks",      "blocks_p90")
    p90("clearances",  "clearances_p90")
    p90("pressures",   "pressures_p90")
    p90("dribbles_succ","dribbles_p90")
    p90("fouls_won",   "fouls_won_p90")
    p90("fouls",       "fouls_p90")
    p90("prog_passes", "prog_passes_p90")
    p90("key_passes",  "key_passes_p90")

    # Percentages
    if "shots_on" in df.columns and "shots" in df.columns:
        df["shot_accuracy"] = (df["shots_on"] / df["shots"].replace(0, np.nan) * 100).round(1)
    if "dribbles_succ" in df.columns and "dribbles_att" in df.columns:
        df["dribble_success"] = (df["dribbles_succ"] / df["dribbles_att"].replace(0, np.nan) * 100).round(1)
    if "aerials_won" in df.columns and "aerials_lost" in df.columns:
        total = df["aerials_won"] + df["aerials_lost"]
        df["aerial_win_pct"] = (df["aerials_won"] / total.replace(0, np.nan) * 100).round(1)

    return df


def _cache_key(league_id: str, season: int, stat: str) -> dict:
    return {"src": "fbref_direct", "league": league_id, "season": season, "stat": stat}


def _fetch_stats(league_id: str, season: int, stat_type: str,
                  rename: dict[str, str], table_hint: str) -> pd.DataFrame:
    key    = _cache_key(league_id, season, stat_type)
    cached = cache.json_get(f"fbref_{stat_type}", key, ttl_hours=48)
    if cached is not None:
        return pd.DataFrame(cached)

    url  = scraper._stats_url(league_id, season, stat_type)
    html = scraper.fetch_html(url)
    if not html:
        return pd.DataFrame()

    raw = scraper.parse_stats_table(html, table_hint)
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = _normalise(raw, rename)
    # Remove "X squads" aggregation rows by keeping only first occurrence per player
    if "player" in df.columns and "team" in df.columns:
        df = df.drop_duplicates(subset=["player"], keep="first")
    df = df[df.get("player", pd.Series(dtype=str)).notna()].reset_index(drop=True)

    cache.json_save(f"fbref_{stat_type}", key, df.to_dict(orient="records"))
    return df


# ── Public API ─────────────────────────────────────────────────────────────────

def get_player_standard_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "standard", _RENAME_STD, "stats_standard")


def get_player_shooting_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "shooting", _RENAME_SHOOT, "stats_shooting")


def get_player_passing_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "passing", _RENAME_PASS, "stats_passing")


def get_player_defense_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "defense", _RENAME_DEF, "stats_defense")


def get_player_misc_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "misc", _RENAME_MISC, "stats_misc")


def get_player_possession_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "possession", _RENAME_POSS, "stats_possession")


def get_player_gk_stats(league_id: str, season: int) -> pd.DataFrame:
    return _fetch_stats(league_id, season, "gk", _RENAME_GK, "stats_keeper")


def get_combined_player_stats(league_id: str, season: int) -> pd.DataFrame:
    """Merge standard + shooting + passing + defense + misc into one wide DataFrame."""
    key    = _cache_key(league_id, season, "combined")
    cached = cache.json_get("fbref_combined", key, ttl_hours=48)
    if cached is not None:
        return pd.DataFrame(cached)

    std  = get_player_standard_stats(league_id, season)
    if std.empty:
        return pd.DataFrame()

    merge_on = [c for c in ["player", "team"] if c in std.columns]

    def _merge(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
        if other.empty:
            return base
        drop = [c for c in other.columns if c in base.columns and c not in merge_on]
        return base.merge(other.drop(columns=drop, errors="ignore"),
                          on=merge_on, how="left", suffixes=("", "_dup"))

    df = std.copy()
    for fetcher in [get_player_shooting_stats, get_player_passing_stats,
                    get_player_defense_stats,  get_player_misc_stats,
                    get_player_possession_stats]:
        df = _merge(df, fetcher(league_id, season))

    # Drop any _dup suffix columns
    df = df[[c for c in df.columns if not c.endswith("_dup")]]
    df = _add_per90(df)

    cache.json_save("fbref_combined", key, df.to_dict(orient="records"))
    return df


def get_teams(league_id: str, season: int) -> list[dict]:
    key    = _cache_key(league_id, season, "teams")
    cached = cache.json_get("fbref_teams", key, ttl_hours=48)
    if cached is not None:
        return cached

    df = get_player_standard_stats(league_id, season)
    if df.empty or "team" not in df.columns:
        return []
    teams = (
        df[["team"]].dropna().drop_duplicates()
        .assign(id=lambda d: d["team"])
        .rename(columns={"team": "name"})
        .to_dict(orient="records")
    )
    cache.json_save("fbref_teams", key, teams)
    return teams


def get_league_table(league_id: str, season: int) -> list[dict]:
    key    = _cache_key(league_id, season, "standings")
    cached = cache.json_get("fbref_standings", key, ttl_hours=6)
    if cached is not None:
        return cached

    url  = scraper._main_url(league_id, season)
    html = scraper.fetch_html(url)
    if not html:
        return []

    df = scraper.parse_standings_table(html)
    if df is None or df.empty:
        return []

    # Normalise column names
    rename = {
        "Squad": "team", "MP": "played",
        "W": "wins", "D": "draws", "L": "losses",
        "GF": "goals_for", "GA": "goals_against",
        "GD": "goal_diff", "Pts": "points",
        "Pts/MP": "pts_per_game", "xG": "xg", "xGA": "xga",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    for col in ["played","wins","draws","losses","goals_for","goals_against","goal_diff","points"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "points" in df.columns:
        df = df.sort_values("points", ascending=False)

    df = df.reset_index(drop=True)
    rows = df.to_dict(orient="records")
    cache.json_save("fbref_standings", key, rows)
    return rows


def search_players(query: str, league_id: str, season: int) -> list[dict]:
    df = get_player_standard_stats(league_id, season)
    if df.empty or "player" not in df.columns:
        return []
    mask    = df["player"].str.lower().str.contains(query.lower(), na=False)
    cols    = [c for c in ["player", "team", "pos"] if c in df.columns]
    matches = df[mask][cols].drop_duplicates().head(20)
    return matches.to_dict(orient="records")
