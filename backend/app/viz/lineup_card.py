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


def _is_pure_def(p: dict) -> bool:
    """
    True only for players with NO midfield/forward component.
    "D" or "D S" → True (pure CB or FB)
    "D M", "M D", "DM" → False (DM, box-to-box, inverted FB — play in midfield)
    """
    toks = _tokens(p)
    tok_set = set(toks)
    if "GK" in tok_set or "F" in tok_set or "AM" in tok_set:
        return False
    if "D" not in tok_set:
        return False
    # Any midfield component → not a pure defender
    return "M" not in tok_set and "DM" not in tok_set


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

# ── FotMob column hints ───────────────────────────────────────────────────────

def _fotmob_col(p: dict, hints: dict[str, int] | None) -> int | None:
    """
    Look up a player's FotMob column position (1=leftmost in row) by last name.
    Returns None when no hint is available.
    """
    if not hints:
        return None
    name = p.get("player", p.get("player_name", ""))
    last = name.split()[-1].lower() if name else ""
    # Try exact last name first, then partial match
    if last in hints:
        return hints[last]
    for key, val in hints.items():
        if last and (last in key or key in last):
            return val
    return None


def _order_by_fotmob(players: list[dict], hints: dict[str, int] | None) -> list[dict] | None:
    """
    If all players in the list have FotMob column hints, return them sorted
    left-to-right by column.  Returns None if hints are missing for any player.
    """
    if not hints:
        return None
    cols = [_fotmob_col(p, hints) for p in players]
    if any(c is None for c in cols):
        return None
    return [p for _, p in sorted(zip(cols, players))]  # type: ignore[arg-type]


def _order_def_line(players: list[dict], n_def: int,
                    hints: dict[str, int] | None = None) -> list[dict]:
    """
    Orders defenders left → right.

    CB vs FB discrimination uses AVG MINS per game (not total mins).
    A CB almost always plays the full 90 when fit → high avg_mins.
    A traditional FB gets rotated / subbed off more → lower avg_mins.
    This correctly places Hall (LB, lower avg) as the LB and
    Burn (CB, higher avg) as the left-CB for Newcastle.

    3ATB : sort by avg_mins desc (no lateral logic needed).
    4/5ATB hybrid ('D M') → flanks, highest avg hybrid → right.
    1 hybrid : lowest avg pure-D → left FB; rest = CBs sorted avg asc left-right.
    2 hybrids: each hybrid fills one flank; CBs in centre sorted avg asc.
    No hybrids: lowest avg pair → FBs (flanks); rest → CBs (centre, avg asc).
    """
    # FotMob grid takes priority — it knows actual positions
    fm_ordered = _order_by_fotmob(players, hints)
    if fm_ordered is not None:
        return fm_ordered

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

    return left_flank + centre + right_flank


def _order_fwd_line(players: list[dict],
                    hints: dict[str, int] | None = None) -> list[dict]:
    """
    Orders forwards left → right.

    When a clear striker is present (first token 'F', no 'M') → centre.
    Wingers / AMs on flanks: highest-total-mins winger → LEFT (usually the
    team's primary wide threat, e.g. LW), second → RIGHT.

    When NO clear striker is detected (Understat often tags LW/RW as bare 'F'):
    Use the lowest-total-mins FWD as the centre forward (strikers rotate more
    than nailed-down wingers) and place them in the middle slot.
    For exactly 3 FWDs: [highest-mins, lowest-mins, second-mins]
    = [LW, CF, RW] which is a reasonable approximation.
    """
    fm_ordered = _order_by_fotmob(players, hints)
    if fm_ordered is not None:
        return fm_ordered

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
    mid_players: list[dict] | None = None
) -> list[tuple[float, float]]:
    """Return 11 (x, y) Opta positions: GK + DEF row + MID row(s) + FWD row."""

    def _spread(n: int, y: float) -> list[tuple[float, float]]:
        if n == 0:
            return []
        xs = np.linspace(15, 85, n)
        return [(float(x), y) for x in xs]

    coords: list[tuple[float, float]] = [(50.0, 8.0)]   # GK
    coords += _spread(n_def, 27.0)

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


# ── Build XI ─────────────────────────────────────────────────────────────────

def _fotmob_row_to_pos(row: int, n_rows: int) -> str:
    """
    Convert FotMob lineup row number to position category.
    row 1      → GK
    row 2      → DEF
    row n_rows → FWD  (last row = strikers/forwards)
    anything between 2 and n_rows → MID
    n_rows is total number of distinct rows in the lineup (incl. GK row).
    """
    if row == 1:
        return "GK"
    if row == 2:
        return "DEF"
    if row >= n_rows:
        return "FWD"
    return "MID"


def _lookup_row(p: dict, row_hints: dict[str, int]) -> int | None:
    """Find a player's FotMob row via last-name lookup (same logic as _fotmob_col)."""
    name = p.get("player", p.get("player_name", ""))
    last = name.split()[-1].lower() if name else ""
    if last and last in row_hints:
        return row_hints[last]
    # partial match
    for key, val in row_hints.items():
        if last and (last in key or key in last):
            return val
    return None


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
    """Look up a player's API-Football position by last name."""
    name = p.get("player", p.get("player_name", ""))
    last = name.split()[-1].lower() if name else ""
    if last and last in pos_hints:
        return pos_hints[last]
    for key, val in pos_hints.items():
        if last and (last in key or key in last):
            return val
    return None


def build_xi(
    players: list[dict],
    fotmob_hints: dict[str, int] | None = None,
    forced_formation: str | None = None,
    row_hints: dict[str, int] | None = None,
    pos_hints: dict[str, str] | None = None,
) -> tuple[list[dict], str]:
    """
    Returns (xi_with_coords, formation_str).
    Each result dict: player, minutes, position, x, y.

    When forced_formation is provided (e.g. "4-3-3" from a FotMob lineup),
    that formation is treated as ground truth.  Players are selected:
      1. GK  — highest-minute goalkeeper
      2. DEF — top n_def defenders by minutes
      3. FWD — top n_fwd forwards by minutes
      4. MID — top n_mid from all remaining outfield players
    This fills "attacking midfielders" (FWD-classified "F M") naturally into
    the midfield for 4-2-3-1 / 4-3-3 etc. without any heuristic guards.
    """
    MIN_AVG = 45   # exclude pure super-subs

    # ── Pool: players averaging ≥45 min/game ──────────────────────────────────
    starters = [p for p in players if _avg_mins(p) >= MIN_AVG]
    pool = starters if len(starters) >= 11 else players

    # ── Separate GK ───────────────────────────────────────────────────────────
    gk_pool  = sorted([p for p in pool if _strict_pos(p) == "GK"],
                      key=_total_mins, reverse=True)
    out_pool = sorted([p for p in pool if _strict_pos(p) != "GK"],
                      key=_total_mins, reverse=True)

    xi_gk = gk_pool[:1]
    if not xi_gk and out_pool:
        xi_gk    = out_pool[:1]
        out_pool = out_pool[1:]

    # ── Forced-formation path (FotMob lineup tells us the real shape) ─────────
    parsed = _parse_formation(forced_formation) if forced_formation else None
    if parsed:
        n_def_t, n_mid_t, n_fwd_t = parsed
        # n_rows = number of lines including GK (e.g. 4-3-3 → 4 rows)
        n_rows = len([x for x in str(forced_formation).split("-") if x.strip().isdigit()]) + 1

        def _classify(p: dict) -> str:
            """
            Priority:
            1. API-Football pos field (actual match position — most reliable)
            2. API-Football row hint (inferred from grid row number)
            3. Conservative Understat fallback:
               - FWD: any F or AM token
               - DEF: ONLY if no midfield component (pure D, no M/DM)
               - MID: everything else, including D M, DM, M D, M
               This prevents DMs like Rice (D M) from landing in the back 4.
            """
            if pos_hints:
                ap = _lookup_pos(p, pos_hints)
                if ap is not None:
                    return ap
            if row_hints:
                row = _lookup_row(p, row_hints)
                if row is not None:
                    return _fotmob_row_to_pos(row, n_rows)
            toks = _tokens(p)
            tok_set = set(toks)
            if "GK" in tok_set:
                return "GK"
            if "F" in tok_set or "AM" in tok_set:
                return "FWD"
            if _is_pure_def(p):
                return "DEF"
            return "MID"

        def_pool = sorted([p for p in out_pool if _classify(p) == "DEF"],
                          key=_total_mins, reverse=True)
        fwd_pool = sorted([p for p in out_pool if _classify(p) == "FWD"],
                          key=_total_mins, reverse=True)

        xi_def = def_pool[:n_def_t]
        xi_fwd = fwd_pool[:n_fwd_t]

        # MID = highest-minute players not already claimed
        used = {id(p) for p in xi_def + xi_fwd}
        remaining = [p for p in out_pool if id(p) not in used]
        xi_mid = remaining[:n_mid_t]

        # If any group is short (row_hints might not cover everyone), pull from leftover
        for _ in range(3):
            used2 = {id(p) for p in xi_def + xi_mid + xi_fwd}
            leftover = [p for p in out_pool if id(p) not in used2]
            if len(xi_def) < n_def_t and leftover:
                xi_def.append(leftover.pop(0))
            elif len(xi_fwd) < n_fwd_t and leftover:
                xi_fwd.append(leftover.pop(0))
            elif len(xi_mid) < n_mid_t and leftover:
                xi_mid.append(leftover.pop(0))
            else:
                break

        n_def, n_mid, n_fwd = len(xi_def), len(xi_mid), len(xi_fwd)

        for p in xi_def: p["_pos_override"] = "DEF"
        for p in xi_mid: p["_pos_override"] = "MID"
        for p in xi_fwd: p["_pos_override"] = "FWD"

        xi_def = sorted(xi_def, key=_total_mins, reverse=True)
        xi_mid = sorted(xi_mid, key=_total_mins, reverse=True)
        xi_fwd = sorted(xi_fwd, key=_total_mins, reverse=True)

        def_ordered = _order_def_line(xi_def, n_def, fotmob_hints)
        mid_ordered = _order_by_fotmob(xi_mid, fotmob_hints) or xi_mid
        fwd_ordered = _order_fwd_line(xi_fwd, fotmob_hints)

        xi_ordered = xi_gk + def_ordered + mid_ordered + fwd_ordered
        coords     = _formation_coords(n_def, n_mid, n_fwd, mid_players=mid_ordered)

        result = []
        for player, (x, y) in zip(xi_ordered, coords):
            result.append({
                "player":   player.get("player", player.get("player_name", "?")),
                "minutes":  int(_total_mins(player)),
                "position": player.get("_pos_override") or _strict_pos(player),
                "x": x, "y": y,
            })
        return result, _formation_str(n_def, n_mid, n_fwd)

    # ── Fallback: heuristic path (Understat / no formation hint) ─────────────
    # If we have row_hints but no forced formation, still use them for classification
    # by inferring the formation from the most likely shape (4 rows = 4-X-Y)
    if (row_hints or pos_hints) and not parsed:
        # Determine n_rows from the row_hints data (max row value seen)
        n_rows_inferred = max(row_hints.values(), default=4) if row_hints else 4

        def _classify_heuristic(p: dict) -> str:
            if pos_hints:
                ap = _lookup_pos(p, pos_hints)
                if ap is not None:
                    return ap
            if row_hints:
                row = _lookup_row(p, row_hints)
                if row is not None:
                    return _fotmob_row_to_pos(row, n_rows_inferred)
            toks = _tokens(p)
            tok_set = set(toks)
            if "GK" in tok_set: return "GK"
            if "F" in tok_set or "AM" in tok_set: return "FWD"
            if _is_pure_def(p): return "DEF"
            return "MID"

        xi_out = list(out_pool[:10])
        xi_def = sorted([p for p in xi_out if _classify_heuristic(p) == "DEF"], key=_total_mins, reverse=True)
        xi_mid = sorted([p for p in xi_out if _classify_heuristic(p) == "MID"], key=_total_mins, reverse=True)
        xi_fwd = sorted([p for p in xi_out if _classify_heuristic(p) == "FWD"], key=_total_mins, reverse=True)

        n_def, n_mid, n_fwd = len(xi_def), len(xi_mid), len(xi_fwd)
        def_ordered = _order_def_line(xi_def, n_def, fotmob_hints)
        mid_ordered = _order_by_fotmob(xi_mid, fotmob_hints) or xi_mid
        fwd_ordered = _order_fwd_line(xi_fwd, fotmob_hints)
        xi_ordered  = xi_gk + def_ordered + mid_ordered + fwd_ordered
        coords      = _formation_coords(n_def, n_mid, n_fwd, mid_players=mid_ordered)
        result = []
        for player, (x, y) in zip(xi_ordered, coords):
            result.append({
                "player":   player.get("player", player.get("player_name", "?")),
                "minutes":  int(_total_mins(player)),
                "position": _classify_heuristic(player),
                "x": x, "y": y,
            })
        return result, _formation_str(n_def, n_mid, n_fwd)

    # Take top 10 outfield by total minutes
    xi_out = list(out_pool[:10])

    # 5ATB guard: only keep >4 DEFs when ≥2 are hybrids (genuine wing-back)
    for _ in range(2):
        defs_in_xi   = [p for p in xi_out if _strict_pos(p) == "DEF"]
        n_hyb_in_xi  = sum(1 for p in defs_in_xi if _is_hybrid_def(p))
        if len(defs_in_xi) > 4 and n_hyb_in_xi < 2:
            worst_def  = min(defs_in_xi, key=_total_mins)
            xi_out.remove(worst_def)
            xi_ids     = {id(p) for p in xi_out}
            candidates = [p for p in out_pool
                          if id(p) not in xi_ids and _strict_pos(p) != "DEF"]
            if not candidates:
                candidates = [p for p in out_pool if id(p) not in xi_ids]
            if candidates:
                xi_out.append(max(candidates, key=_total_mins))
        else:
            break

    # FWD overcounting guard: demote lowest-minute hybrid FWDs to MID
    def _is_hybrid_fwd(p: dict) -> bool:
        toks = set(_tokens(p))
        return "F" in toks and "M" in toks

    for _ in range(3):
        fwds_in_xi = [p for p in xi_out if _strict_pos(p) == "FWD"]
        if len(fwds_in_xi) <= 3:
            break
        hybrids = [p for p in fwds_in_xi if _is_hybrid_fwd(p)]
        if not hybrids:
            break
        min(hybrids, key=_total_mins)["_pos_override"] = "MID"

    def _effective_pos(p: dict) -> str:
        return p.get("_pos_override") or _strict_pos(p)

    xi_def = sorted([p for p in xi_out if _effective_pos(p) == "DEF"], key=_total_mins, reverse=True)
    xi_mid = sorted([p for p in xi_out if _effective_pos(p) == "MID"], key=_total_mins, reverse=True)
    xi_fwd = sorted([p for p in xi_out if _effective_pos(p) == "FWD"], key=_total_mins, reverse=True)

    n_def, n_mid, n_fwd = len(xi_def), len(xi_mid), len(xi_fwd)

    def_ordered = _order_def_line(xi_def, n_def, fotmob_hints)
    mid_ordered = _order_by_fotmob(xi_mid, fotmob_hints) or xi_mid
    fwd_ordered = _order_fwd_line(xi_fwd, fotmob_hints)

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
    fotmob_hints:     dict[str, int] | None = None,
    row_hints:        dict[str, int] | None = None,
    pos_hints:        dict[str, str] | None = None,
    forced_formation: str | None = None,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    if not players:
        return _no_data_png(team_name, season_label, font)

    xi, formation = build_xi(players, fotmob_hints=fotmob_hints,
                             row_hints=row_hints, pos_hints=pos_hints,
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
