"""
Most-Played XI card.
Draws a vertical pitch with the 11 most-used players placed in formation,
plus manager name and formation string.

Algorithm
─────────
1.  STRICT position classification (Understat tokens):
      GK  — "GK" token anywhere
      FWD — "F" or "AM" token anywhere  (catches "M F S", "F M S", "AM")
      DEF — first non-S token is "D", no F/AM tokens  (catches "D M", "D S")
      MID — everything else  ("M", "M S", "M D", etc.)

2.  Pool: players with avg_mins ≥ 45.  Fall back to full list if < 11 qualify.

3.  XI selection:
      • Take the 10 highest-total-minute outfield players from the pool.
      • If more than 4 of them are DEF-classified AND fewer than 2 of those
        DEFs are hybrids ('D M'), swap the lowest-minute DEF with the
        highest-minute non-DEF player not yet in the XI.
        (This prevents "5ATB" for normal 4ATB teams like Newcastle where
        Understat happens to classify 5 DEF players.)
      • 5ATB is kept only when ≥2 hybrid DEFs exist in the XI
        (genuine wing-back system).

4.  Formation = count strict positions of the final XI.

5.  Within-line ordering:
      When FotMob hints are provided (player_last_name → column 1…N),
      lines are sorted left-to-right by the FotMob grid column.
      Without hints, heuristics apply:
      DEF: hybrids ('D M') → flanks; pure-D players ranked by avg_mins
           (highest = CB → centre, lowest = traditional FB → remaining flank)
      FWD: pure-F players (no M) → centre (striker)
           hybrid ('F M', 'M F S', 'AM') → flanks (wingers)
      MID: sorted by total minutes (no strong lateral preference)
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from mplsoccer import VerticalPitch

from app.viz.common import BG, BG_CARD, TEXT, TEXT_SUB, fig_to_png, get_font, team_color


# ── Strict position classification ────────────────────────────────────────────

def _tokens(p: dict) -> list[str]:
    """Non-S tokens from the Understat position string, in original order."""
    return [t for t in p.get("position", "").upper().split() if t not in ("S", "")]



def _strict_pos(p: dict) -> str:
    """
    Single unambiguous position category.

    ANY 'F' or 'AM' token → FWD.
    First token 'D', no F/AM → DEF.
    Everything else → MID.
    """
    toks = _tokens(p)
    tok_set = set(toks)
    if not toks:
        return "MID"
    if "GK" in tok_set:
        return "GK"
    if "F" in tok_set or "AM" in tok_set:
        return "FWD"
    if toks[0] == "D":
        return "DEF"
    return "MID"


def _is_hybrid_def(p: dict) -> bool:
    """'D M' or 'D AM' — attacking fullback or wing-back."""
    toks = set(_tokens(p))
    return "D" in toks and ("M" in toks or "AM" in toks)


def _is_striker(p: dict) -> bool:
    """
    True for central forwards (CF/ST): first token is 'F' and no 'M' secondary.
    'F'   / 'F S'   → striker  ✓
    'F M S'         → False  (M secondary = winger tendency)
    'M F S' / 'AM'  → False  (first token M/AM = wide/second-striker)
    """
    toks = _tokens(p)
    return bool(toks) and toks[0] == "F" and "M" not in set(toks)


# ── Minute helpers ────────────────────────────────────────────────────────────

def _total_mins(p: dict) -> float:
    return float(p.get("minutes", p.get("time", 0)) or 0)


def _avg_mins(p: dict) -> float:
    mins = _total_mins(p)
    apps = float(p.get("apps", 0) or 0)
    return mins / apps if apps > 0 else 0.0


# ── Within-line ordering ──────────────────────────────────────────────────────

def _order_def_line(players: list[dict], n_def: int) -> list[dict]:
    """
    Orders defenders left → right using avg mins to discriminate CB vs FB.
    A CB plays full 90s when fit → higher avg_mins.
    A FB gets rotated / subbed → lower avg_mins.
    """
    if n_def == 3:
        return sorted(players, key=_avg_mins, reverse=True)

    # Sort hybrids by avg_mins desc; sort pures by avg_mins DESC (high = CB)
    hybrids = sorted([p for p in players if _is_hybrid_def(p)],
                     key=_avg_mins, reverse=True)
    pures   = sorted([p for p in players if not _is_hybrid_def(p)],
                     key=_avg_mins, reverse=True)   # index 0 = highest avg = most CB-like

    if len(hybrids) >= 2:
        right_flank = [hybrids[0]]     # higher avg hybrid → right flank
        left_flank  = [hybrids[1]]     # lower  avg hybrid → left flank
        extra       = hybrids[2:]
        # CBs (extras + pures) sorted avg ascending → left-CB has lower avg than right-CB
        centre = sorted(extra + pures, key=_avg_mins)
    elif len(hybrids) == 1:
        right_flank = [hybrids[0]]     # hybrid → right flank (attacking RB / WB)
        if pures:
            left_flank = [pures[-1]]   # lowest avg pure-D → left FB
            # Remaining CBs sorted avg ascending (lower avg CB on left)
            centre = sorted(pures[:-1], key=_avg_mins)
        else:
            left_flank = []
            centre = []
    else:
        # No hybrids: bottom 2 by avg_mins = FBs on flanks; rest = CBs in centre
        sorted_asc = sorted(pures, key=_avg_mins)          # lowest avg first
        n_fb = min(2, len(sorted_asc))
        fbs  = sorted_asc[:n_fb]    # lowest avg = most FB-like
        cbs  = sorted_asc[n_fb:]    # highest avg = most CB-like, already ascending
        left_flank  = [fbs[0]] if fbs else []
        right_flank = [fbs[1]] if len(fbs) >= 2 else []
        centre      = cbs   # already ascending avg → left-CB has lower avg

    return right_flank + centre + left_flank


def _order_fwd_line(players: list[dict]) -> list[dict]:
    """Orders forwards left → right. Clear strikers → centre, wingers → flanks."""
    strikers = sorted([p for p in players if _is_striker(p)],
                      key=_total_mins, reverse=True)
    wingers  = sorted([p for p in players if not _is_striker(p)],
                      key=_total_mins, reverse=True)  # desc: index 0 = highest

    if strikers and wingers:
        # Strikers in centre, wingers on flanks.
        # Highest-mins winger → LEFT, 2nd → RIGHT.
        left  = [wingers[0]]   if len(wingers) >= 1 else []
        right = [wingers[1]]   if len(wingers) >= 2 else []
        extra = wingers[2:]    # rare 3+-winger case → right of right
        return left + extra + strikers + right
    elif not strikers:
        # No reliable striker detected.
        # Lowest total mins → centre; highest → left; second → right.
        desc = sorted(players, key=_total_mins, reverse=True)
        n = len(desc)
        if n == 1:
            return desc
        if n == 2:
            return desc   # higher-mins left, lower right
        # n >= 3: [0]=highest→left, [-1]=lowest→centre, [1:-1]=rest→right
        left   = [desc[0]]
        center = [desc[-1]]
        right  = desc[1:-1]   # already desc so higher-mins comes first on right
        return left + center + right
    else:
        # All strikers (no wingers)
        return strikers


# ── Formation coordinate lookup ───────────────────────────────────────────────

def _is_dm(p: dict) -> bool:
    """Defensive mid: first token D or M, second token M with no F/AM."""
    toks = _tokens(p)
    tok_set = set(toks)
    if not toks or "F" in tok_set or "AM" in tok_set or "GK" in tok_set or toks[0] == "D":
        return False
    # 'M D' or 'D M' already classed as DEF; pure 'M' with a D secondary = DM
    return "D" in tok_set


def _is_am(p: dict) -> bool:
    """Attacking mid: has AM token and is classified MID (not FWD)."""
    toks = _tokens(p)
    return "AM" in set(toks)


def _formation_coords(
    n_def: int, n_mid: int, n_fwd: int,
    mid_players: list[dict] | None = None,
    forced_formation_parts: list[int] | None = None,
) -> list[tuple[float, float]]:
    """Return 11 (x, y) Opta positions: GK + DEF row + MID row(s) + FWD row."""

    def _spread(n: int, y: float) -> list[tuple[float, float]]:
        if n == 0:
            return []
        # Tighten the spread for small groups so 2 players don't end up at the wings
        margins = {1: (50, 50), 2: (33, 67), 3: (20, 80)}
        lo, hi = margins.get(n, (15, 85))
        xs = np.linspace(lo, hi, n)
        return [(float(x), y) for x in xs]

    coords: list[tuple[float, float]] = [(50.0, 8.0)]   # GK
    coords += _spread(n_def, 27.0)

    # Multi-layer mid: use forced formation structure when available (e.g. 4-2-3-1 → [2, 3])
    if forced_formation_parts and len(forced_formation_parts) > 3:
        mid_layer_counts = forced_formation_parts[1:-1]
        n_layers = len(mid_layer_counts)
        if n_layers == 2:
            ys = [43.0, 60.0]
        elif n_layers == 3:
            ys = [40.0, 52.0, 65.0]
        else:
            ys = list(np.linspace(40.0, 65.0, n_layers))
        for count, y_pos in zip(mid_layer_counts, ys):
            coords += _spread(count, y_pos)
        coords += _spread(n_fwd, 76.0)
        return coords

    # Mid layering: detect DM / CM / AM sub-groups when mid_players is provided
    if mid_players and n_mid >= 3:
        dms = [p for p in mid_players if _is_dm(p)]
        ams = [p for p in mid_players if _is_am(p) and not _is_dm(p)]
        cms = [p for p in mid_players if not _is_dm(p) and not _is_am(p)]

        # Only split into layers when we have meaningful groupings
        if dms and (cms or ams):
            n_dm = len(dms); n_cm = len(cms); n_am = len(ams)
            if n_am and n_cm:
                coords += _spread(n_dm, 40.0)
                coords += _spread(n_cm, 53.0)
                coords += _spread(n_am, 65.0)
            elif n_dm and n_cm:
                coords += _spread(n_dm, 43.0)
                coords += _spread(n_cm, 58.0)
            elif n_dm and n_am:
                coords += _spread(n_dm, 43.0)
                coords += _spread(n_am, 63.0)
            else:
                coords += _spread(n_mid, 52.0)
        elif n_mid > 5:
            mid1 = n_mid // 2
            coords += _spread(mid1, 47.0)
            coords += _spread(n_mid - mid1, 62.0)
        else:
            coords += _spread(n_mid, 52.0)
    elif n_mid > 5:
        mid1 = n_mid // 2
        coords += _spread(mid1, 47.0)
        coords += _spread(n_mid - mid1, 62.0)
    else:
        coords += _spread(n_mid, 52.0)

    coords += _spread(n_fwd, 76.0)
    return coords


def _formation_str(n_def: int, n_mid: int, n_fwd: int) -> str:
    return f"{n_def}-{n_mid}-{n_fwd}"


# ── ESPN position helpers ─────────────────────────────────────────────────────

import unicodedata as _ud

def _norm(s: str) -> str:
    return _ud.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()

# Raw ESPN abbreviation → GK/DEF/MID/FWD category
_ESPN_CAT: dict[str, str] = {
    "G": "GK", "GK": "GK",
    "D": "DEF", "CB": "DEF", "CD": "DEF", "CD-L": "DEF", "CD-R": "DEF",
    "LB": "DEF", "RB": "DEF", "LWB": "DEF", "RWB": "DEF", "SW": "DEF",
    "M": "MID", "CM": "MID", "DM": "MID", "CDM": "MID",
    "LM": "MID", "RM": "MID", "AM": "MID", "CAM": "MID",
    "F": "FWD", "LF": "FWD", "RF": "FWD", "CF": "FWD",
    "ST": "FWD", "LW": "FWD", "RW": "FWD", "SS": "FWD",
}

def _espn_side(abbr: str) -> str:
    """L / C / R from ESPN position abbreviation."""
    if not abbr:
        return "C"
    if abbr[0] == "L":
        return "L"
    if abbr[0] == "R":
        return "R"
    return "C"

def _lookup_espn_abbr(p: dict, pos_hints: dict[str, str]) -> str | None:
    """Return raw ESPN position abbreviation for a player via normalised last-name lookup."""
    name = p.get("player", p.get("player_name", ""))
    last = _norm(name.split()[-1]) if name else ""
    if last and last in pos_hints:
        return pos_hints[last]
    for key, val in pos_hints.items():
        if last and (last in key or key in last):
            return val
    return None

def _order_line_by_side(players: list[dict], pos_hints: dict[str, str]) -> list[dict]:
    """
    Sort players left → right using ESPN lateral position hints.
    Falls back to current order if hints not available.
    """
    def _side_key(p: dict) -> int:
        abbr = _lookup_espn_abbr(p, pos_hints) or ""
        s = _espn_side(abbr)
        return {"L": 0, "C": 1, "R": 2}[s]

    # Only reorder if we have hints for all players
    if all(_lookup_espn_abbr(p, pos_hints) for p in players):
        return sorted(players, key=_side_key)
    return players


def _select_def_xi(def_pool: list[dict], n_def: int,
                   pos_hints: dict[str, str]) -> list[dict]:
    """
    Select n_def defenders with formation-aware slot filling:
    For 4-back: 1 LB + 2 CB + 1 RB (avoids picking 2 LBs when 2 LBs are available)
    For 3-back: 3 CBs
    Falls back to top-N by minutes if hints insufficient.
    """
    if not pos_hints or n_def not in (3, 4, 5):
        return def_pool[:n_def]

    lbs  = [p for p in def_pool if _espn_side(_lookup_espn_abbr(p, pos_hints) or "") == "L"]
    rbs  = [p for p in def_pool if _espn_side(_lookup_espn_abbr(p, pos_hints) or "") == "R"]
    cbs  = [p for p in def_pool if _espn_side(_lookup_espn_abbr(p, pos_hints) or "") == "C"]

    if n_def == 3:
        slot_l, slot_c, slot_r = 0, 3, 0
    elif n_def == 4:
        slot_l, slot_c, slot_r = 1, 2, 1
    else:  # 5
        slot_l, slot_c, slot_r = 1, 3, 1

    chosen = lbs[:slot_l] + cbs[:slot_c] + rbs[:slot_r]

    # If any slot is underfilled (e.g. no RB data), top up from remaining pool
    used = {id(p) for p in chosen}
    leftover = [p for p in def_pool if id(p) not in used]
    while len(chosen) < n_def and leftover:
        chosen.append(leftover.pop(0))

    return chosen


# ── Build XI ─────────────────────────────────────────────────────────────────

def _parse_formation(formation_str: str) -> tuple[int, int, int] | None:
    """
    Parse a formation string into (n_def, n_mid, n_fwd).
    "4-3-3"   → (4, 3, 3)
    "4-2-3-1" → (4, 5, 1)   — middle layers summed
    "3-5-2"   → (3, 5, 2)
    Returns None if parsing fails or total ≠ 10.
    """
    try:
        parts = [int(x) for x in str(formation_str).split("-") if x.strip().isdigit()]
    except (ValueError, AttributeError):
        return None
    if len(parts) < 2:
        return None
    n_def = parts[0]
    n_fwd = parts[-1]
    n_mid = sum(parts[1:-1]) if len(parts) > 2 else parts[1]
    if n_def + n_mid + n_fwd != 10:
        return None
    return n_def, n_mid, n_fwd


def _lookup_pos(p: dict, pos_hints: dict[str, str]) -> str | None:
    """Return GK/DEF/MID/FWD category for a player via ESPN pos_hints."""
    abbr = _lookup_espn_abbr(p, pos_hints)
    if abbr is None:
        return None
    return _ESPN_CAT.get(abbr, "MID")


def build_xi(
    players: list[dict],
    pos_hints: dict[str, str] | None = None,
    forced_formation: str | None = None,
) -> tuple[list[dict], str]:
    """
    Returns (xi_with_coords, formation_str).
    Each result dict: player, minutes, position, x, y.

    pos_hints: {last_name_lower → "GK"/"DEF"/"MID"/"FWD"} from ESPN lineup data.
    forced_formation: formation string e.g. "4-3-3" from ESPN.

    When pos_hints is available, it is used as the primary classifier —
    distinguishing e.g. Rice (LM→MID) from Timber (RB→DEF) even though
    both are "D M" in Understat. _strict_pos is only the final fallback.
    """
    MIN_AVG = 45

    starters = [p for p in players if _avg_mins(p) >= MIN_AVG]
    pool = starters if len(starters) >= 11 else players

    gk_pool  = sorted([p for p in pool if _strict_pos(p) == "GK"],
                      key=_total_mins, reverse=True)
    out_pool = sorted([p for p in pool if _strict_pos(p) != "GK"],
                      key=_total_mins, reverse=True)

    xi_gk = gk_pool[:1]
    if not xi_gk and out_pool:
        xi_gk    = out_pool[:1]
        out_pool = out_pool[1:]

    def _classify(p: dict) -> str:
        """ESPN pos_hints first (reliable), _strict_pos as last resort."""
        if pos_hints:
            pos = _lookup_pos(p, pos_hints)
            if pos is not None:
                return pos
        return _strict_pos(p)

    # ── Forced-formation path (ESPN tells us the real shape) ──────────────────
    parsed = _parse_formation(forced_formation) if forced_formation else None
    if parsed:
        n_def_t, n_mid_t, n_fwd_t = parsed
        forced_parts = [int(x) for x in forced_formation.split("-") if x.strip().isdigit()]

        def_pool = sorted([p for p in out_pool if _classify(p) == "DEF"],
                          key=_total_mins, reverse=True)
        fwd_pool = sorted([p for p in out_pool if _classify(p) == "FWD"],
                          key=_total_mins, reverse=True)

        # Smart DEF selection: 1 LB + 2 CB + 1 RB (avoids 2 LBs in back 4)
        xi_def = _select_def_xi(def_pool, n_def_t, pos_hints or {})
        xi_fwd = fwd_pool[:n_fwd_t]
        mid_pool = sorted([p for p in out_pool if _classify(p) == "MID"],
                          key=_total_mins, reverse=True)
        xi_mid = mid_pool[:n_mid_t]

        # Top up any short group from pool-agnostic leftovers
        for _ in range(5):
            used2 = {id(p) for p in xi_def + xi_mid + xi_fwd}
            leftover = [p for p in out_pool if id(p) not in used2]
            if not leftover:
                break
            if len(xi_def) < n_def_t:
                xi_def.append(leftover.pop(0))
            elif len(xi_mid) < n_mid_t:
                xi_mid.append(leftover.pop(0))
            elif len(xi_fwd) < n_fwd_t:
                xi_fwd.append(leftover.pop(0))
            else:
                break

        for p in xi_def: p["_pos_override"] = "DEF"
        for p in xi_mid: p["_pos_override"] = "MID"
        for p in xi_fwd: p["_pos_override"] = "FWD"

        n_def, n_mid, n_fwd = len(xi_def), len(xi_mid), len(xi_fwd)
        # Use ESPN lateral hints for ordering, fall back to heuristics
        if pos_hints:
            def_ordered = _order_line_by_side(xi_def, pos_hints)
            mid_ordered = _order_line_by_side(xi_mid, pos_hints)
            fwd_ordered = _order_line_by_side(xi_fwd, pos_hints)
        else:
            def_ordered = _order_def_line(xi_def, n_def)
            mid_ordered = sorted(xi_mid, key=_total_mins, reverse=True)
            fwd_ordered = _order_fwd_line(xi_fwd)

        # For multi-layer formations (e.g. 4-2-3-1), reorder mids so DMs come first
        if len(forced_parts) > 3 and mid_ordered:
            n_dm_layer = forced_parts[1]
            if pos_hints:
                dms_first = [p for p in mid_ordered
                             if (_lookup_espn_abbr(p, pos_hints) or "") in ("DM", "CDM")]
                others = [p for p in mid_ordered if id(p) not in {id(x) for x in dms_first}]
                if len(dms_first) < n_dm_layer:
                    # Second priority: Understat DM heuristic (e.g. "M D" position token)
                    # catches players ESPN tags as generic "CM" but who play DM
                    understat_dms = [p for p in others if _is_dm(p)]
                    dms_first += understat_dms[:n_dm_layer - len(dms_first)]
                    used_ids = {id(p) for p in dms_first}
                    others = [p for p in mid_ordered if id(p) not in used_ids]

                if len(dms_first) < n_dm_layer:
                    # Last resort: central mids; exclude wide/attacking/hybrid-def
                    _non_dm_abbrs = {"CAM", "AM", "SS", "CF", "LW", "RW", "LM", "RM"}
                    non_am = [p for p in others
                              if (_lookup_espn_abbr(p, pos_hints) or "") not in _non_dm_abbrs
                              and not _is_am(p)
                              and not (
                                  _lookup_espn_abbr(p, pos_hints) is None
                                  and _is_hybrid_def(p)
                              )]
                    central = [p for p in non_am
                               if _espn_side(_lookup_espn_abbr(p, pos_hints) or "") == "C"
                               or not _lookup_espn_abbr(p, pos_hints)]
                    dms_first += central[:n_dm_layer - len(dms_first)]
                    used_ids = {id(p) for p in dms_first}
                    others = [p for p in mid_ordered if id(p) not in used_ids]
            else:
                dms_first = [p for p in mid_ordered if _is_dm(p)]
                others = [p for p in mid_ordered if not _is_dm(p)]
                if len(dms_first) < n_dm_layer:
                    extra = others[:n_dm_layer - len(dms_first)]
                    dms_first += extra
                    used_ids = {id(p) for p in dms_first}
                    others = [p for p in mid_ordered if id(p) not in used_ids]
            mid_ordered = dms_first[:n_dm_layer] + others

        use_parts = forced_parts if len(forced_parts) > 3 else None
        xi_ordered = xi_gk + def_ordered + mid_ordered + fwd_ordered
        coords     = _formation_coords(n_def, n_mid, n_fwd, mid_players=mid_ordered,
                                       forced_formation_parts=use_parts)

        result = []
        for player, (x, y) in zip(xi_ordered, coords):
            result.append({
                "player":   player.get("player", player.get("player_name", "?")),
                "minutes":  int(_total_mins(player)),
                "position": player.get("_pos_override") or _strict_pos(player),
                "x": x, "y": y,
            })
        return result, forced_formation

    # ── Fallback: pos_hints available but no forced formation ─────────────────
    if pos_hints:
        xi_out = list(out_pool[:10])
        def_pool_h = sorted([p for p in xi_out if _classify(p) == "DEF"], key=_total_mins, reverse=True)
        xi_def = _select_def_xi(def_pool_h, len(def_pool_h), pos_hints)
        xi_mid = sorted([p for p in xi_out if _classify(p) == "MID"], key=_total_mins, reverse=True)
        xi_fwd = sorted([p for p in xi_out if _classify(p) == "FWD"], key=_total_mins, reverse=True)
        n_def, n_mid, n_fwd = len(xi_def), len(xi_mid), len(xi_fwd)
        xi_ordered = xi_gk + _order_line_by_side(xi_def, pos_hints) + _order_line_by_side(xi_mid, pos_hints) + _order_line_by_side(xi_fwd, pos_hints)
        coords = _formation_coords(n_def, n_mid, n_fwd, mid_players=xi_mid)
        result = []
        for player, (x, y) in zip(xi_ordered, coords):
            result.append({
                "player":   player.get("player", player.get("player_name", "?")),
                "minutes":  int(_total_mins(player)),
                "position": _classify(player),
                "x": x, "y": y,
            })
        return result, _formation_str(n_def, n_mid, n_fwd)

    # ── Pure Understat fallback (no ESPN data) ────────────────────────────────
    xi_out = list(out_pool[:10])

    # 5ATB guard
    for _ in range(2):
        defs_in_xi  = [p for p in xi_out if _strict_pos(p) == "DEF"]
        n_hyb       = sum(1 for p in defs_in_xi if _is_hybrid_def(p))
        if len(defs_in_xi) > 4 and n_hyb < 2:
            worst_def  = min(defs_in_xi, key=_total_mins)
            xi_out.remove(worst_def)
            xi_ids     = {id(p) for p in xi_out}
            candidates = [p for p in out_pool if id(p) not in xi_ids and _strict_pos(p) != "DEF"]
            if not candidates:
                candidates = [p for p in out_pool if id(p) not in xi_ids]
            if candidates:
                xi_out.append(max(candidates, key=_total_mins))
        else:
            break

    # FWD overcounting guard
    for _ in range(3):
        fwds = [p for p in xi_out if _strict_pos(p) == "FWD"]
        if len(fwds) <= 3:
            break
        hybrids = [p for p in fwds if set(_tokens(p)) & {"F", "M"} == {"F", "M"}]
        if not hybrids:
            break
        min(hybrids, key=_total_mins)["_pos_override"] = "MID"

    def _effective_pos(p: dict) -> str:
        return p.get("_pos_override") or _strict_pos(p)

    xi_def = sorted([p for p in xi_out if _effective_pos(p) == "DEF"], key=_total_mins, reverse=True)
    xi_mid = sorted([p for p in xi_out if _effective_pos(p) == "MID"], key=_total_mins, reverse=True)
    xi_fwd = sorted([p for p in xi_out if _effective_pos(p) == "FWD"], key=_total_mins, reverse=True)
    n_def, n_mid, n_fwd = len(xi_def), len(xi_mid), len(xi_fwd)

    def_ordered = _order_def_line(xi_def, n_def)
    mid_ordered = xi_mid
    fwd_ordered = _order_fwd_line(xi_fwd)

    xi_ordered = xi_gk + def_ordered + mid_ordered + fwd_ordered
    coords     = _formation_coords(n_def, n_mid, n_fwd, mid_players=mid_ordered)

    result = []
    for player, (x, y) in zip(xi_ordered, coords):
        result.append({
            "player":   player.get("player", player.get("player_name", "?")),
            "minutes":  int(_total_mins(player)),
            "position": _effective_pos(player),
            "x": x, "y": y,
        })
    return result, _formation_str(n_def, n_mid, n_fwd)


# ── Render ────────────────────────────────────────────────────────────────────

def render(
    team_name:        str,
    season_label:     str,
    league_label:     str,
    players:          list[dict],
    manager:          str = "",
    pos_hints:        dict[str, str] | None = None,
    forced_formation: str | None = None,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    if not players:
        return _no_data_png(team_name, season_label, font)

    xi, formation = build_xi(players, pos_hints=pos_hints,
                             forced_formation=forced_formation)
    if not xi:
        return _no_data_png(team_name, season_label, font)

    fig = plt.figure(figsize=(9, 12), facecolor=BG)

    # ── Header ────────────────────────────────────────────────────────────────
    ax_hdr = fig.add_axes([0, 0.88, 1, 0.12])
    ax_hdr.set_facecolor(BG_CARD); ax_hdr.axis("off")
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)
    ax_hdr.axvline(x=0.008, color=primary, lw=8, alpha=0.9)
    ax_hdr.text(0.04, 0.78, team_name, fontsize=22, fontproperties=font,
                color=TEXT, fontweight="bold", va="top")
    meta = "  ·  ".join(p for p in [league_label, season_label,
                                     f"Most Played XI  ·  {formation}"] if p)
    ax_hdr.text(0.04, 0.38, meta, fontsize=9.5, fontproperties=font,
                color=TEXT_SUB, va="top")
    if manager:
        ax_hdr.text(0.04, 0.12, f"Manager: {manager}", fontsize=9,
                    fontproperties=font, color=TEXT_SUB, va="top")

    # ── Pitch ─────────────────────────────────────────────────────────────────
    pitch = VerticalPitch(
        pitch_type="opta",
        pitch_color="#1A2A1A",
        line_color="#3D5C3D",
        linewidth=1.0,
        goal_type="box",
        corner_arcs=True,
    )
    ax_pitch = fig.add_axes([0.03, 0.04, 0.94, 0.83])
    pitch.draw(ax=ax_pitch)

    pos_colors = {"GK": "#F59E0B", "DEF": "#3B82F6", "MID": "#22C55E", "FWD": "#EF4444"}

    for p in xi:
        x, y   = p["x"], p["y"]
        pos    = p["position"]
        name   = p["player"]
        mins   = p["minutes"]
        short  = name.split()[-1] if " " in name else name
        pc     = pos_colors.get(pos, TEXT_SUB)

        ax_pitch.scatter(x, y, s=900, color=primary, zorder=4,
                         edgecolors=TEXT, linewidths=1.2)
        ax_pitch.scatter(x + 3.5, y + 3.5, s=130, color=pc,
                         zorder=5, edgecolors=BG, linewidths=0.8)
        ax_pitch.text(x, y - 5.8, short, ha="center", va="top",
                      fontsize=7.5, fontproperties=font, color=TEXT,
                      fontweight="bold", zorder=6,
                      bbox=dict(facecolor=BG, edgecolor="none",
                                boxstyle="round,pad=0.15", alpha=0.75))
        ax_pitch.text(x, y + 0.2, str(mins), ha="center", va="center",
                      fontsize=6, fontproperties=font,
                      color=BG, fontweight="bold", zorder=7)

    legend_items = [
        mpatches.Patch(color="#F59E0B", label="GK"),
        mpatches.Patch(color="#3B82F6", label="DEF"),
        mpatches.Patch(color="#22C55E", label="MID"),
        mpatches.Patch(color="#EF4444", label="FWD"),
    ]
    # Place legend inside the pitch at the very bottom to avoid overlapping the footer
    ax_pitch.legend(handles=legend_items, loc="lower center",
                    bbox_to_anchor=(0.5, 0.01), ncol=4, frameon=False,
                    prop=font, fontsize=8, labelcolor=TEXT)

    fig.text(0.5, 0.004, "Ordered by minutes played  ·  Data: Understat  ·  UEFAgraphics",
             fontsize=7.5, color="#374151", ha="center", va="bottom", fontproperties=font)

    return fig_to_png(fig, dpi=150)


def _no_data_png(team_name: str, season_label: str, font) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG)
    ax.set_facecolor(BG); ax.axis("off")
    ax.text(0.5, 0.6, team_name, color=TEXT, fontsize=16, ha="center",
            transform=ax.transAxes, fontweight="bold", fontproperties=font)
    ax.text(0.5, 0.4, f"No lineup data for {season_label}", color=TEXT_SUB,
            fontsize=11, ha="center", transform=ax.transAxes, fontproperties=font)
    return fig_to_png(fig)
