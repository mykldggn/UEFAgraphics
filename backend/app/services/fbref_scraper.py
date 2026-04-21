"""
Direct FBref scraper — replaces soccerdata.

Key design decisions:
- Hardcoded FBref league IDs so we NEVER hit fbref.com/en/comps/ (the index
  that caused the 403 with soccerdata).
- Per-request throttle (4–8 s random delay) with a threading lock so
  concurrent FastAPI requests don't pile up.
- Everything is cached at the service layer (48 h for player stats,
  6 h for standings) so live traffic rarely triggers a real HTTP request.
"""
from __future__ import annotations

import io
import logging
import random
import threading
import time
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# ── Rate limiter ───────────────────────────────────────────────────────────────
_last_req: float = 0.0
_rate_lock = threading.Lock()
_MIN_DELAY = 4.0
_MAX_DELAY = 8.0


def _throttle() -> None:
    global _last_req
    with _rate_lock:
        elapsed = time.time() - _last_req
        delay   = random.uniform(_MIN_DELAY, _MAX_DELAY)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        _last_req = time.time()


# ── HTTP session ───────────────────────────────────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            _session = requests.Session()
        return _session


def _headers() -> dict:
    return {
        "User-Agent":                random.choice(_USER_AGENTS),
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":           "en-US,en;q=0.9",
        "Accept-Encoding":           "gzip, deflate, br",
        "Referer":                   "https://fbref.com/en/",
        "Connection":                "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":            "document",
        "Sec-Fetch-Mode":            "navigate",
        "Sec-Fetch-Site":            "same-origin",
        "Cache-Control":             "max-age=0",
    }


# ── League map: our ID → (fbref numeric id, url slug) ─────────────────────────
LEAGUE_MAP: dict[str, tuple[int, str]] = {
    "ENG-1":    (9,   "Premier-League"),
    "ENG-2":    (10,  "Championship"),
    "ENG-3":    (15,  "League-One"),
    "ENG-4":    (16,  "League-Two"),
    "ESP-1":    (12,  "La-Liga"),
    "DEU-1":    (20,  "Bundesliga"),
    "ITA-1":    (11,  "Serie-A"),
    "FRA-1":    (13,  "Ligue-1"),
    "NED-1":    (23,  "Eredivisie"),
    "PRT-1":    (32,  "Primeira-Liga"),
    "BEL-1":    (37,  "Belgian-First-Division-A"),
    "SCO-1":    (40,  "Scottish-Premiership"),
    "CHE-1":    (45,  "Swiss-Super-League"),
    "TUR-1":    (26,  "Super-Lig"),
    "GRC-1":    (27,  "Super-League-Greece"),
    "AUT-1":    (56,  "Austrian-Football-Bundesliga"),
    "RUS-1":    (30,  "Russian-Premier-League"),
    "UEFA-CL":  (8,   "Champions-League"),
    "UEFA-EL":  (19,  "Europa-League"),
    "UEFA-ECL": (882, "Europa-Conference-League"),
    "INT-EUROS":(676, "European-Championship"),
    "INT-WC":   (1,   "FIFA-World-Cup"),
    "INT-NL":   (218, "UEFA-Nations-League"),
}

# stat_type → URL path segment
_STAT_PATH = {
    "standard":   "stats",
    "shooting":   "shooting",
    "passing":    "passing",
    "defense":    "defense",
    "misc":       "misc",
    "gk":         "keepers",
    "possession": "possession",
}


def _season_str(season: int) -> str:
    """2024  →  '2024-2025'"""
    return f"{season}-{season + 1}"


def _stats_url(league_id: str, season: int, stat_type: str = "standard") -> str:
    fbref_id, slug = LEAGUE_MAP[league_id]
    s    = _season_str(season)
    path = _STAT_PATH.get(stat_type, stat_type)
    return f"https://fbref.com/en/comps/{fbref_id}/{s}/{path}/{s}-{slug}-Stats"


def _main_url(league_id: str, season: int) -> str:
    """League season overview page (has standings table)."""
    fbref_id, slug = LEAGUE_MAP[league_id]
    s = _season_str(season)
    return f"https://fbref.com/en/comps/{fbref_id}/{s}/{s}-{slug}-Stats"


# ── HTTP fetch ─────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> Optional[str]:
    """Fetch a page with throttling + browser headers. Returns HTML or None."""
    _throttle()
    try:
        resp = _get_session().get(url, headers=_headers(), timeout=30)
        if resp.status_code == 429:
            logger.warning(f"FBref 429 on {url} — backing off 60 s")
            time.sleep(60)
            return None
        if resp.status_code == 403:
            logger.warning(f"FBref 403 on {url}")
            return None
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.error(f"fetch_html {url}: {exc}")
        return None


# ── HTML parsing ───────────────────────────────────────────────────────────────

def _all_tables(soup: BeautifulSoup):
    """Yield all <table> elements including those wrapped in HTML comments."""
    yield from soup.find_all("table")
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        inner = BeautifulSoup(comment, "lxml")
        yield from inner.find_all("table")


def _flatten_columns(cols) -> list[str]:
    """Flatten FBref two-row MultiIndex headers into unique strings."""
    result: list[str] = []
    seen: dict[str, int] = {}
    for col in cols:
        if isinstance(col, tuple):
            parts = [str(p) for p in col if "Unnamed" not in str(p) and str(p).strip()]
            name  = parts[-1] if parts else str(col[0])
        else:
            name = str(col)
        name = name.strip()
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        result.append(name)
    return result


def parse_stats_table(html: str, hint: str) -> Optional[pd.DataFrame]:
    """
    Find the FBref stats table whose id contains `hint`, parse it,
    and return a flat DataFrame. Handles comment-wrapped tables.
    """
    soup  = BeautifulSoup(html, "lxml")
    table = None
    for t in _all_tables(soup):
        tid = t.get("id", "")
        if hint in tid:
            table = t
            break

    if table is None:
        logger.debug(f"Table hint '{hint}' not found — trying class search")
        # Fall back: find any table with player-like content
        for t in _all_tables(soup):
            ths = [th.get_text(strip=True) for th in t.find_all("th")]
            if "Player" in ths and ("Gls" in ths or "Tkl" in ths or "Cmp%" in ths):
                table = t
                break

    if table is None:
        return None

    try:
        dfs = pd.read_html(io.StringIO(str(table)), header=[0, 1])
        if not dfs:
            return None
        df = dfs[0]
        df.columns = _flatten_columns(df.columns)
        # Drop repeated header rows
        if "Player" in df.columns:
            df = df[df["Player"].notna() & (df["Player"] != "Player")]
        return df.reset_index(drop=True)
    except Exception as exc:
        logger.error(f"parse_stats_table ({hint}): {exc}")
        return None


def parse_standings_table(html: str) -> Optional[pd.DataFrame]:
    """
    Find the league standings table on a FBref league season page.
    Identifies it by the presence of a 'Pts' column in the header.
    """
    soup = BeautifulSoup(html, "lxml")
    for table in _all_tables(soup):
        header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Pts" in header_cells and ("W" in header_cells or "Squad" in header_cells):
            try:
                dfs = pd.read_html(io.StringIO(str(table)))
                if dfs:
                    df = dfs[0]
                    # Drop rows where Squad is NaN or header-repeated
                    if "Squad" in df.columns:
                        df = df[df["Squad"].notna() & (df["Squad"] != "Squad")]
                    return df.reset_index(drop=True)
            except Exception as exc:
                logger.debug(f"standings parse attempt failed: {exc}")
    return None
