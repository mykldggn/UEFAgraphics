"""
Most-Played XI card — vertical pitch with formation, manager name, and minutes bubbles.

Position classification priority:
  1. Transfermarkt (merged into pos_hints) — e.g. "CDM", "CB", "LW" — most reliable
  2. ESPN pos_hints + place_hints — formation shape and left/right ordering
  3. Understat _strict_pos — last resort when no external data available
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
    """Understat-only fallback: GK / FWD (any F or AM token) / DEF (first token D) / MID."""
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
    """CF/ST: first Understat token 'F' with no 'M' secondary (excludes wingers)."""
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
    """Left→right ordering for DEF line when no pos_hints/place_hints available.
    Uses avg_mins as CB-vs-FB proxy: higher avg = more CB-like (plays full 90s)."""
    if n_def == 3:
        return sorted(players, key=_avg_mins, reverse=True)

    hybrids = sorted([p for p in players if _is_hybrid_def(p)], key=_avg_mins, reverse=True)
    pures   = sorted([p for p in players if not _is_hybrid_def(p)], key=_avg_mins, reverse=True)

    if len(hybrids) >= 2:
        centre = sorted(hybrids[2:] + pures, key=_avg_mins)
        return [hybrids[1]] + centre + [hybrids[0]]
    elif len(hybrids) == 1:
        centre = sorted(pures[:-1], key=_avg_mins) if pures else []
        left   = [pures[-1]] if pures else []
        return left + centre + [hybrids[0]]
    else:
        sorted_asc = sorted(pures, key=_avg_mins)
        n_fb = min(2, len(sorted_asc))
        fbs, cbs = sorted_asc[:n_fb], sorted_asc[n_fb:]
        left_flank  = [fbs[0]] if fbs else []
        right_flank = [fbs[1]] if len(fbs) >= 2 else []
        return left_flank + cbs + right_flank


def _order_fwd_line(players: list[dict]) -> list[dict]:
    """Left→right ordering for FWD line: strikers → centre, wingers → flanks."""
    strikers = sorted([p for p in players if _is_striker(p)],     key=_total_mins, reverse=True)
    wingers  = sorted([p for p in players if not _is_striker(p)], key=_total_mins, reverse=True)

    if strikers and wingers:
        left  = [wingers[1]] if len(wingers) >= 2 else []
        right = [wingers[0]] if wingers else []
        return left + wingers[2:] + strikers + right
    if not strikers:
        desc = sorted(players, key=_total_mins, reverse=True)
        if len(desc) <= 2:
            return desc
        return [desc[0]] + desc[2:] + [desc[1]]
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
        # mplsoccer's vertical pitch renders the x-axis right-to-left in this view.
        xs = np.linspace(hi, lo, n)
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

# Position abbreviation → GK/DEF/MID/FWD category
# Covers both ESPN abbreviations and Transfermarkt-derived ones (CDM, CAM, CF, etc.)
_ESPN_CAT: dict[str, str] = {
    "G": "GK",  "GK": "GK",
    "D": "DEF", "CB": "DEF", "CD": "DEF", "CD-L": "DEF", "CD-R": "DEF",
    "LB": "DEF", "RB": "DEF", "WB": "DEF",
    "LWB": "DEF", "RWB": "DEF", "SW": "DEF",
    "M": "MID", "CM": "MID", "DM": "MID", "CDM": "MID",
    "LM": "MID", "RM": "MID", "AM": "MID", "CAM": "MID",
    "WM": "MID",
    "F": "FWD", "CF": "FWD", "ST": "FWD", "WF": "FWD",
    "LW": "FWD", "RW": "FWD", "LF": "FWD", "RF": "FWD", "SS": "FWD",
}

_SIDE = {"L": 0, "C": 1, "R": 2}

_DEF_SLOT_SETS = {
    1: ["CB"],
    2: ["LCB", "RCB"],
    3: ["LCB", "CB", "RCB"],
    4: ["LB", "LCB", "RCB", "RB"],
    5: ["LWB", "LCB", "CB", "RCB", "RWB"],
}

_MID_SLOT_SETS = {
    1: ["CM"],
    2: ["LCM", "RCM"],
    3: ["LCM", "CM", "RCM"],
    4: ["LM", "LCM", "RCM", "RM"],
    5: ["LM", "LCM", "CM", "RCM", "RM"],
}

_FWD_SLOT_SETS = {
    1: ["CF"],
    2: ["LCF", "RCF"],
    3: ["LW", "CF", "RW"],
    4: ["LW", "LCF", "RCF", "RW"],
}

def _espn_side(abbr: str) -> str:
    """L / C / R from ESPN position abbreviation."""
    if not abbr:
        return "C"
    if abbr.endswith("-L"):
        return "L"
    if abbr.endswith("-R"):
        return "R"
    if abbr[0] == "L":
        return "L"
    if abbr[0] == "R":
        return "R"
    return "C"


def _player_name(p: dict) -> str:
    return p.get("player") or p.get("player_name") or p.get("name") or "?"


def _understat_abbr(p: dict) -> str:
    """Convert Understat's multi-token position string into one concrete role."""
    toks = _tokens(p)
    tok_set = set(toks)
    if not toks:
        return "CM"
    if "GK" in tok_set:
        return "GK"
    if "D" in tok_set and "F" in tok_set and "M" in tok_set:
        return "WM"
    if "D" in tok_set and "F" in tok_set:
        return "WB"
    if "F" in tok_set and "M" not in tok_set:
        return "CF"
    if "F" in tok_set and "M" in tok_set:
        return "WF" if toks[0] == "F" else "CAM"
    if "AM" in tok_set:
        return "CAM"
    # Understat often records D/M for both fullbacks and defensive mids.
    # Treat it as CDM for slot filling; it can still fill fullback slots if needed,
    # but it will no longer be preferred as a centre-back.
    if "D" in tok_set and "M" in tok_set:
        return "CDM"
    if toks[0] == "D":
        return "CB"
    if "D" in tok_set:
        return "CDM"
    return "CM"


def _abbr_for_player(p: dict, pos_hints: dict[str, str] | None = None) -> str:
    understat_abbr = _understat_abbr(p)
    if pos_hints:
        hinted = _lookup_espn_abbr(p, pos_hints)
        if hinted:
            toks = set(_tokens(p))
            hinted_cat = _abbr_category(hinted)
            if hinted in {"D", "M", "F"} and understat_abbr not in {"GK", "CM"}:
                return understat_abbr
            # Lineup APIs can collide on common surnames or report tactical rows
            # that disagree with a player's season role. Keep clear strikers
            # central and never turn defender/fullback tokens into forwards.
            if understat_abbr == "CF" and hinted_cat == "MID":
                return understat_abbr
            if "F" in toks and hinted in {"DM", "CDM", "LDM", "RDM"}:
                return understat_abbr
            if "D" in toks and hinted_cat == "FWD":
                side = _espn_side(hinted)
                if side == "L":
                    return "LB"
                if side == "R":
                    return "RB"
                return understat_abbr
            return hinted
    return understat_abbr


def _abbr_category(abbr: str) -> str:
    return _ESPN_CAT.get(abbr, "MID")


def _slot_category(slot: str) -> str:
    if slot == "GK":
        return "GK"
    if slot in {"LB", "LCB", "CB", "RCB", "RB", "LWB", "RWB"} or slot.startswith("DEF"):
        return "DEF"
    if slot in {"LW", "LF", "LCF", "CF", "RCF", "RF", "RW", "SS"} or slot.startswith("FWD"):
        return "FWD"
    return "MID"


def _slot_side(slot: str) -> str:
    if slot.startswith("L"):
        return "L"
    if slot.startswith("R"):
        return "R"
    return "C"


def _role_match_score(slot: str, abbr: str) -> float:
    """Large positive/negative role score; minutes break ties inside a slot."""
    slot_cat = _slot_category(slot)
    abbr_cat = _abbr_category(abbr)
    score = 0.0

    if abbr_cat == slot_cat:
        score += 100_000
    else:
        score -= 120_000

    if (
        slot == abbr
        or (slot == "LCB" and abbr == "CD-L")
        or (slot == "RCB" and abbr == "CD-R")
        or (slot == "CB" and abbr in {"CD", "CD-L", "CD-R", "CB"})
        or (slot == "CF" and abbr in {"F", "ST", "CF"})
    ):
        score += 60_000

    if slot in {"LCB", "CB", "RCB"}:
        if abbr in {"CB", "CD", "CD-L", "CD-R", "SW"}:
            score += 45_000
        elif abbr in {"LB", "RB", "LWB", "RWB"}:
            score -= 20_000
        elif abbr in {"CDM", "DM"}:
            score -= 50_000

    if slot in {"LB", "LWB"}:
        if abbr in {"LB", "LWB"}:
            score += 55_000
        elif abbr == "WB":
            score += 20_000
        elif abbr in {"RB", "RWB"}:
            score -= 90_000
        elif abbr in {"CB", "CD"}:
            score -= 18_000

    if slot in {"RB", "RWB"}:
        if abbr in {"RB", "RWB"}:
            score += 55_000
        elif abbr == "WB":
            score += 20_000
        elif abbr in {"LB", "LWB"}:
            score -= 90_000
        elif abbr in {"CB", "CD"}:
            score -= 18_000

    if slot in {"LDM", "RDM", "CDM"}:
        if abbr in {"CDM", "DM"}:
            score += 55_000
        elif abbr in {"CM", "M"}:
            score += 25_000
        elif abbr_cat == "DEF":
            score -= 70_000

    if slot in {"LCM", "CM", "RCM"}:
        if abbr in {"CM", "M", "CDM", "DM"}:
            score += 30_000
        elif abbr in {"CAM", "AM"}:
            score += 33_000

    if slot in {"LAM", "CAM", "RAM"}:
        if abbr in {"CAM", "AM", "SS"}:
            score += 45_000
        elif abbr in {"LW", "RW", "LM", "RM"}:
            score += 30_000
        elif abbr in {"CF", "ST", "F"}:
            score -= 18_000

    if slot in {"LM", "RM"}:
        if abbr in {slot, slot.replace("M", "W")}:
            score += 45_000
        elif abbr in {"CM", "M", "CAM", "AM"}:
            score += 15_000

    if slot in {"LW", "RW"}:
        if abbr == slot:
            score += 60_000
        elif abbr in {"LF", "RF", "LM", "RM"} and _espn_side(abbr) == _slot_side(slot):
            score += 35_000
        elif abbr in {"CF", "ST", "F"}:
            score -= 45_000

    if slot in {"LCF", "CF", "RCF"}:
        if abbr in {"CF", "ST", "F"}:
            score += 55_000
        elif abbr in {"LW", "RW"}:
            score -= 22_000

    abbr_side = _espn_side(abbr)
    slot_side = _slot_side(slot)
    if abbr_side != "C" and slot_side != "C":
        if abbr_side == slot_side:
            score += 18_000
        else:
            score -= 80_000

    return score


def _mid_slots_for_layers(mid_layers: list[int]) -> list[str]:
    if len(mid_layers) <= 1:
        return _MID_SLOT_SETS.get(mid_layers[0] if mid_layers else 0, [f"CM{i + 1}" for i in range(mid_layers[0] if mid_layers else 0)])

    slots: list[str] = []
    for layer_idx, count in enumerate(mid_layers):
        if layer_idx == 0:
            if count == 1:
                layer = ["CDM"]
            elif count == 2:
                layer = ["LDM", "RDM"]
            elif count == 3:
                layer = ["LDM", "CDM", "RDM"]
            else:
                layer = _MID_SLOT_SETS.get(count, [f"DM{i + 1}" for i in range(count)])
        elif layer_idx == len(mid_layers) - 1:
            if count == 1:
                layer = ["CAM"]
            elif count == 2:
                layer = ["LAM", "RAM"]
            elif count == 3:
                layer = ["LAM", "CAM", "RAM"]
            else:
                layer = _MID_SLOT_SETS.get(count, [f"AM{i + 1}" for i in range(count)])
        else:
            layer = _MID_SLOT_SETS.get(count, [f"CM{i + 1}" for i in range(count)])
        slots.extend(layer)
    return slots


def _slots_for_formation_parts(parts: list[int]) -> list[str]:
    n_def = parts[0]
    n_fwd = parts[-1]
    mid_layers = parts[1:-1] if len(parts) > 2 else [parts[1]]
    return (
        ["GK"]
        + _DEF_SLOT_SETS.get(n_def, [f"DEF{i + 1}" for i in range(n_def)])
        + _mid_slots_for_layers(mid_layers)
        + _FWD_SLOT_SETS.get(n_fwd, [f"FWD{i + 1}" for i in range(n_fwd)])
    )


def _assign_players_to_slots(
    players: list[dict],
    slots: list[str],
    pos_hints: dict[str, str] | None,
    place_hints: dict[str, float] | None,
) -> list[dict]:
    selected: list[dict] = []
    used: set[int] = set()
    by_minutes = sorted(players, key=_total_mins, reverse=True)

    for slot_index, slot in enumerate(slots, start=1):
        best_player = None
        best_score = -10**12
        for player in by_minutes:
            if id(player) in used:
                continue
            abbr = _abbr_for_player(player, pos_hints)
            score = _role_match_score(slot, abbr) + _total_mins(player)
            if place_hints:
                place = _lookup_place(player, place_hints)
                if place is not None:
                    # FormationPlace is useful for ordering, but minutes should
                    # still decide between same-role players over a season.
                    score += max(0, 3_000 - abs(place - slot_index) * 600)
            if score > best_score:
                best_player = player
                best_score = score
        if best_player is not None:
            chosen = dict(best_player)
            chosen["_slot"] = slot
            chosen["_pos_override"] = _slot_category(slot)
            chosen["_role_abbr"] = _abbr_for_player(best_player, pos_hints)
            selected.append(chosen)
            used.add(id(best_player))

    return selected

def _lookup_espn_abbr(p: dict, pos_hints: dict[str, str]) -> str | None:
    """Return raw ESPN position abbreviation for a player via normalised last-name lookup."""
    name = p.get("player", p.get("player_name", ""))
    full = _norm(name)
    if full and full in pos_hints:
        return pos_hints[full]
    last = _norm(name.split()[-1]) if name else ""
    if last and last in pos_hints:
        return pos_hints[last]
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

    # Reorder as long as any player has a hint; unknowns default to "C" (centre slot)
    if any(_lookup_espn_abbr(p, pos_hints) for p in players):
        return sorted(players, key=_side_key)
    return players


def _lookup_place(p: dict, place_hints: dict[str, float]) -> float | None:
    """Return avg ESPN formationPlace for a player via normalised last-name lookup."""
    name = p.get("player") or p.get("player_name") or ""
    full = _norm(name)
    if full and full in place_hints:
        return place_hints[full]
    last = _norm(name.split()[-1]) if name else ""
    if last and last in place_hints:
        return place_hints[last]
    return None


def _order_line_by_place(players: list[dict], place_hints: dict[str, float]) -> list[dict]:
    """Sort left→right by ESPN formationPlace. Players with no place default to 6.0."""
    def _key(p: dict) -> float:
        pl = _lookup_place(p, place_hints)
        return pl if pl is not None else 6.0
    return sorted(players, key=_key)


def _order_fwd_by_hint(
    players: list[dict],
    place_hints: dict[str, float],
    pos_hints: dict[str, str],
) -> list[dict]:
    """Order FWD line by formationPlace, but use pos_hints L/C/R for players with no place data.
    Prevents new signings (no ESPN history yet) from defaulting to 6.0 and landing
    in the wrong slot — e.g. a new CF showing up on the left wing.
    """
    _side_base = {"L": 8.5, "C": 10.0, "R": 11.5}
    def _key(p: dict) -> float:
        pl = _lookup_place(p, place_hints)
        if pl is not None:
            return pl
        abbr = _lookup_espn_abbr(p, pos_hints) or ""
        return _side_base.get(_espn_side(abbr), 10.0)
    return sorted(players, key=_key)


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
    place_hints: dict[str, float] | None = None,
) -> tuple[list[dict], str]:
    """Returns (xi_with_coords, formation_str). Each result dict: player, minutes, position, x, y.

    pos_hints: merged TM + ESPN abbreviations {last_name_lower → "CDM"/"CB"/"LW" etc.}
    forced_formation: most common formation string from ESPN e.g. "4-3-3".
    place_hints: ESPN formationPlace averages for left→right ordering.
    """
    ranked_players = sorted(players, key=_total_mins, reverse=True)
    max_mins = _total_mins(ranked_players[0]) if ranked_players else 0
    minute_floor = max(180.0, max_mins * 0.15)
    meaningful = [
        p for p in ranked_players
        if _total_mins(p) >= minute_floor or _strict_pos(p) == "GK"
    ]
    pool = meaningful[:18] if len(meaningful) >= 11 else ranked_players[:18]

    gk_pool  = sorted([p for p in pool if _strict_pos(p) == "GK"],
                      key=_total_mins, reverse=True)
    out_pool = sorted([p for p in pool if _strict_pos(p) != "GK"],
                      key=_total_mins, reverse=True)

    xi_gk = gk_pool[:1]
    if not xi_gk and out_pool:
        xi_gk    = out_pool[:1]
        out_pool = out_pool[1:]

    def _classify(p: dict) -> str:
        # place_hints (ESPN formationPlace) first — reliable for established players
        if place_hints:
            pl = _lookup_place(p, place_hints)
            if pl is not None:
                return "DEF" if pl <= 5 else ("FWD" if pl > 8 else "MID")
        # TM/ESPN pos_hints fallback — for new signings with no ESPN place history
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

        def _classify(p: dict) -> str:  # noqa: F811 — formation-aware thresholds
            # place_hints first — formation-aware thresholds, e.g. 4-3-3: DEF≤5, MID≤8, FWD>8
            if place_hints:
                pl = _lookup_place(p, place_hints)
                if pl is not None:
                    if pl <= 1 + n_def_t:
                        return "DEF"
                    elif pl <= 1 + n_def_t + n_mid_t:
                        return "MID"
                    else:
                        return "FWD"
            # TM/ESPN pos_hints fallback — new signings without ESPN place data
            if pos_hints:
                pos = _lookup_pos(p, pos_hints)
                if pos is not None:
                    return pos
            return _strict_pos(p)

        slots = _slots_for_formation_parts(forced_parts)
        xi_ordered = _assign_players_to_slots(
            pool,
            slots,
            pos_hints=pos_hints,
            place_hints=place_hints,
        )
        if len(xi_ordered) < 11:
            used_names = {_player_name(p) for p in xi_ordered}
            for player in sorted(pool, key=_total_mins, reverse=True):
                if _player_name(player) in used_names:
                    continue
                fallback = dict(player)
                fallback["_slot"] = slots[len(xi_ordered)] if len(xi_ordered) < len(slots) else "CM"
                fallback["_pos_override"] = _slot_category(fallback["_slot"])
                xi_ordered.append(fallback)
                used_names.add(_player_name(player))
                if len(xi_ordered) == 11:
                    break

        mid_count = sum(forced_parts[1:-1]) if len(forced_parts) > 2 else forced_parts[1]
        use_parts = forced_parts if len(forced_parts) > 3 else None
        coords = _formation_coords(
            n_def_t,
            mid_count,
            n_fwd_t,
            mid_players=[p for p in xi_ordered if p.get("_pos_override") == "MID"],
            forced_formation_parts=use_parts,
        )

        result = []
        for player, (x, y) in zip(xi_ordered, coords):
            result.append({
                "player":   _player_name(player),
                "minutes":  int(_total_mins(player)),
                "position": player.get("_pos_override") or _abbr_category(_abbr_for_player(player, pos_hints)),
                "role":     player.get("_slot") or _abbr_for_player(player, pos_hints),
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
    place_hints:      dict[str, float] | None = None,
) -> bytes:
    font    = get_font()
    primary = team_color(team_name)

    if not players:
        return _no_data_png(team_name, season_label, font)

    xi, formation = build_xi(players, pos_hints=pos_hints,
                             forced_formation=forced_formation,
                             place_hints=place_hints)
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
