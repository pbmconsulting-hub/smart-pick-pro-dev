"""Phase 4 Special Events system for the Smart Pick Pro tournament."""

from __future__ import annotations

import random
from typing import Any

from tournament.config import ROSTER_CONFIG, SCORING_CONFIG
from tournament.events import log_event
from tournament.scoring import (
    calculate_fantasy_points,
    check_bonuses,
    check_penalties,
    score_player_total,
)

# ---------------------------------------------------------------------------
# Event type definitions
# ---------------------------------------------------------------------------

SPECIAL_EVENT_TYPES: dict[str, dict[str, Any]] = {
    "all_star_captain": {
        "name": "All-Star Captain Mode",
        "description": "Designate one captain who receives ×1.5 stats and ×1.5 salary.",
        "month": 2,  # February
        "entry_fee": 50.0,
        "field_size": 32,
        "prizes": {1: 500.0, 2: 200.0, 3: 100.0},
        "salary_cap": ROSTER_CONFIG["salary_cap_active"],  # standard $50K
        "salary_floor": ROSTER_CONFIG["salary_floor_active"],
        "scoring_multiplier": 1.0,
        "captain_multiplier": 1.5,
        "captain_salary_multiplier": 1.5,
        "position_requirements": True,
        "ownership_cap": ROSTER_CONFIG["max_player_ownership_pct"],
    },
    "holiday_showcase": {
        "name": "Holiday Showcase",
        "description": "All scoring receives a ×1.25 multiplier.",
        "month": None,  # any holiday window
        "entry_fee": 20.0,
        "field_size": 24,
        "prizes": {1: 200.0, 2: 80.0, 3: 40.0},
        "salary_cap": ROSTER_CONFIG["salary_cap_active"],
        "salary_floor": ROSTER_CONFIG["salary_floor_active"],
        "scoring_multiplier": 1.25,
        "captain_multiplier": 1.0,
        "captain_salary_multiplier": 1.0,
        "position_requirements": True,
        "ownership_cap": ROSTER_CONFIG["max_player_ownership_pct"],
    },
    "rivalry_night": {
        "name": "Rivalry Night",
        "description": "16-player bracket with head-to-head elimination rounds.",
        "month": None,
        "entry_fee": 30.0,
        "field_size": 16,
        "prizes": {1: 240.0, 2: 100.0, 3: 50.0, 4: 50.0},
        "salary_cap": ROSTER_CONFIG["salary_cap_active"],
        "salary_floor": ROSTER_CONFIG["salary_floor_active"],
        "scoring_multiplier": 1.0,
        "captain_multiplier": 1.0,
        "captain_salary_multiplier": 1.0,
        "position_requirements": True,
        "ownership_cap": ROSTER_CONFIG["max_player_ownership_pct"],
    },
    "chaos_night": {
        "name": "Chaos Night",
        "description": "$35K salary cap, no position requirements, 20% ownership cap.",
        "month": None,
        "entry_fee": 30.0,
        "field_size": 24,
        "prizes": {1: 300.0, 2: 120.0, 3: 60.0},
        "salary_cap": 35000,
        "salary_floor": 25000,
        "scoring_multiplier": 1.0,
        "captain_multiplier": 1.0,
        "captain_salary_multiplier": 1.0,
        "position_requirements": False,
        "ownership_cap": 0.20,
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def get_special_event_config(event_type: str) -> dict:
    """Return configuration for a special event type.

    Parameters
    ----------
    event_type:
        Key into ``SPECIAL_EVENT_TYPES`` (e.g. ``"chaos_night"``).

    Returns
    -------
    dict
        A *copy* of the event configuration so callers cannot mutate the
        canonical definition.

    Raises
    ------
    ValueError
        If *event_type* is not a recognised special event.
    """
    if event_type not in SPECIAL_EVENT_TYPES:
        raise ValueError(
            f"Unknown special event type '{event_type}'. "
            f"Valid types: {', '.join(sorted(SPECIAL_EVENT_TYPES))}"
        )
    return dict(SPECIAL_EVENT_TYPES[event_type])


def validate_special_event_roster(
    roster: list[dict],
    event_type: str,
    field_size: int,
) -> dict:
    """Validate a roster against special-event rules.

    Checks salary cap / floor, ownership limits, and (optionally) position
    requirements.  For *Chaos Night* the position check is skipped and the
    tighter $35K cap and 20 % ownership cap are enforced.

    Parameters
    ----------
    roster:
        List of player dicts.  Each dict must contain at least ``"salary"``
        (int) and ``"player_id"`` (str).  If position requirements are
        active the dict must also contain ``"position"`` (str).
    event_type:
        Key into ``SPECIAL_EVENT_TYPES``.
    field_size:
        Current number of entries in the tournament (used to compute the
        ownership limit).

    Returns
    -------
    dict
        ``{"valid": True}`` on success, or
        ``{"valid": False, "errors": [str, ...]}`` listing every failed
        check.
    """
    cfg = get_special_event_config(event_type)
    errors: list[str] = []

    # -- salary bounds -------------------------------------------------------
    total_salary = sum(int(p.get("salary", 0)) for p in roster)

    if total_salary > cfg["salary_cap"]:
        errors.append(
            f"Total salary ${total_salary:,} exceeds cap ${cfg['salary_cap']:,}."
        )
    if total_salary < cfg["salary_floor"]:
        errors.append(
            f"Total salary ${total_salary:,} below floor ${cfg['salary_floor']:,}."
        )

    # -- ownership cap -------------------------------------------------------
    if field_size > 0:
        from collections import Counter

        ids = Counter(p.get("player_id") for p in roster)
        max_allowed = max(1, int(cfg["ownership_cap"] * field_size))
        for pid, count in ids.items():
            if count > max_allowed:
                errors.append(
                    f"Player {pid} appears {count} times; max allowed is "
                    f"{max_allowed} ({cfg['ownership_cap']:.0%} of {field_size})."
                )

    # -- position requirements -----------------------------------------------
    if cfg["position_requirements"]:
        required_positions = {"PG", "SG", "SF", "PF", "C"}
        filled = {p.get("position", "").upper() for p in roster}
        missing = required_positions - filled
        if missing:
            errors.append(
                f"Missing required positions: {', '.join(sorted(missing))}."
            )

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True}


def apply_captain_multiplier(
    line: dict,
    captain_player_id: str,
    multiplier: float = 1.5,
) -> dict:
    """Apply captain-mode stat multiplier to the designated captain's line.

    Only the stat columns used by the scoring formula are scaled.  The
    returned dict is a *new* dict – the original is not mutated.

    Parameters
    ----------
    line:
        Simulated stat-line dict for a single player.
    captain_player_id:
        The ``player_id`` of the designated captain.
    multiplier:
        Multiplicative factor applied to every scoring stat (default 1.5).

    Returns
    -------
    dict
        A copy of *line* with scoring stats scaled if the player is the
        captain, or an unmodified copy otherwise.
    """
    result = dict(line)
    if str(result.get("player_id", "")) != str(captain_player_id):
        return result

    stat_keys = list(SCORING_CONFIG.keys())  # points, rebounds, …
    for key in stat_keys:
        if key in result:
            result[key] = round(float(result[key]) * multiplier, 2)
    return result


def apply_scoring_multiplier(fantasy_points: float, event_type: str) -> float:
    """Apply the event-wide scoring multiplier.

    For most events the multiplier is 1.0 (no change).  Holiday Showcase
    uses ×1.25.

    Parameters
    ----------
    fantasy_points:
        Raw fantasy-point total *before* the event multiplier.
    event_type:
        Key into ``SPECIAL_EVENT_TYPES``.

    Returns
    -------
    float
        Adjusted fantasy points rounded to two decimal places.
    """
    cfg = get_special_event_config(event_type)
    return round(fantasy_points * cfg["scoring_multiplier"], 2)


def generate_rivalry_bracket(
    entries: list[dict],
    seed: int,
) -> list[dict]:
    """Generate seeded H2H bracket matchups for Rivalry Night.

    Entries are shuffled deterministically using *seed*, then paired
    sequentially (1 v 2, 3 v 4, …).  If the entry count is not a power of
    two the highest-seeded surplus entries receive a bye.

    Parameters
    ----------
    entries:
        List of entry dicts.  Each must contain at least ``"entry_id"``.
    seed:
        Deterministic RNG seed for reproducible bracket generation.

    Returns
    -------
    list[dict]
        List of matchup dicts, each with keys ``"match_id"`` (int, 1-based),
        ``"entry_a"`` and ``"entry_b"`` (entry dicts or ``None`` for a bye),
        and ``"round"`` (always ``1``).

    Raises
    ------
    ValueError
        If fewer than 2 entries are provided.
    """
    if len(entries) < 2:
        raise ValueError("Need at least 2 entries to generate a bracket.")

    rng = random.Random(seed)
    shuffled = list(entries)
    rng.shuffle(shuffled)

    # Pad to next power of two so byes work cleanly.
    bracket_size = 1
    while bracket_size < len(shuffled):
        bracket_size *= 2

    padded: list[dict | None] = list(shuffled)
    while len(padded) < bracket_size:
        padded.append(None)

    matchups: list[dict] = []
    for i in range(0, bracket_size, 2):
        matchups.append(
            {
                "match_id": (i // 2) + 1,
                "round": 1,
                "entry_a": padded[i],
                "entry_b": padded[i + 1],
            }
        )
    return matchups


def resolve_rivalry_round(
    matchups: list[dict],
    sim_results: dict,
) -> list[dict]:
    """Resolve one round of H2H matchups, returning winners.

    Parameters
    ----------
    matchups:
        List of matchup dicts as produced by :func:`generate_rivalry_bracket`
        or a previous call to this function.
    sim_results:
        Mapping of ``entry_id`` → ``total_fp`` (float) representing each
        entry's simulated score for the round.

    Returns
    -------
    list[dict]
        Next-round matchup dicts with ``"round"`` incremented.  Winners
        are paired in order.  If there is a single winner the list
        contains one matchup whose ``"entry_b"`` is ``None`` (champion).
    """
    winners: list[dict] = []

    for mu in matchups:
        a = mu.get("entry_a")
        b = mu.get("entry_b")

        if a is None and b is None:
            continue  # dead matchup – shouldn't happen

        # Bye: the present entry advances automatically.
        if b is None:
            winners.append(a)  # type: ignore[arg-type]
            continue
        if a is None:
            winners.append(b)
            continue

        score_a = float(sim_results.get(a["entry_id"], 0.0))
        score_b = float(sim_results.get(b["entry_id"], 0.0))

        # Tiebreak: lower entry_id wins (earliest submission).
        if score_a >= score_b:
            winners.append(a)
        else:
            winners.append(b)

    if len(winners) <= 1:
        # Tournament resolved – return a single "champion" matchup.
        return [
            {
                "match_id": 1,
                "round": int(matchups[0].get("round", 1)) + 1,
                "entry_a": winners[0] if winners else None,
                "entry_b": None,
            }
        ]

    next_round_num = int(matchups[0].get("round", 1)) + 1
    next_matchups: list[dict] = []
    for i in range(0, len(winners), 2):
        entry_b = winners[i + 1] if i + 1 < len(winners) else None
        next_matchups.append(
            {
                "match_id": (i // 2) + 1,
                "round": next_round_num,
                "entry_a": winners[i],
                "entry_b": entry_b,
            }
        )
    return next_matchups


def score_special_event_entry(
    profile: dict,
    line: dict,
    seed: int,
    event_type: str,
    captain_player_id: str | None = None,
) -> dict:
    """Score a player line with all special-event modifiers applied.

    Applies, in order:

    1. Captain stat multiplier (All-Star Captain Mode only).
    2. Standard scoring (base FP + bonuses + penalties via
       :func:`score_player_total`).
    3. Event-wide scoring multiplier (Holiday Showcase ×1.25, etc.).

    Parameters
    ----------
    profile:
        Player profile dict (passed through to penalty checks).
    line:
        Simulated stat-line dict.
    seed:
        Deterministic RNG seed.
    event_type:
        Key into ``SPECIAL_EVENT_TYPES``.
    captain_player_id:
        If the event supports captain mode, the ``player_id`` of the
        captain.  Ignored for events without captain mechanics.

    Returns
    -------
    dict
        Scoring breakdown identical to :func:`score_player_total` output,
        with additional keys ``"event_type"`` (str),
        ``"scoring_multiplier"`` (float), and ``"adjusted_total_fp"``
        (float) reflecting the post-multiplier total.
    """
    cfg = get_special_event_config(event_type)
    modified_line = dict(line)

    # 1) Captain stat boost
    is_captain = False
    if captain_player_id and cfg["captain_multiplier"] != 1.0:
        modified_line = apply_captain_multiplier(
            modified_line,
            captain_player_id,
            multiplier=cfg["captain_multiplier"],
        )
        is_captain = str(line.get("player_id", "")) == str(captain_player_id)

    # 2) Standard scoring pipeline
    result = score_player_total(profile, modified_line, seed)

    # 3) Event-wide multiplier
    raw_total = float(result["total_fp"])
    adjusted = apply_scoring_multiplier(raw_total, event_type)

    result["event_type"] = event_type
    result["scoring_multiplier"] = cfg["scoring_multiplier"]
    result["adjusted_total_fp"] = adjusted
    result["is_captain"] = is_captain

    return result
