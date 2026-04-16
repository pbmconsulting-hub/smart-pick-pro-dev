"""Tournament player profile builder.

All logic is isolated in the standalone tournament subsystem.
"""

from __future__ import annotations

import math

from tournament.legends import LEGEND_PROFILES

ATTRIBUTE_MIN = 1
ATTRIBUTE_MAX = 99


def _safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _percentile_rank(values: list[float], value: float) -> int:
    if not values:
        return 50
    ordered = sorted(values)
    at_or_below = sum(1 for v in ordered if v <= value)
    pct = int(round((at_or_below / len(ordered)) * 99))
    return int(_clamp(pct, ATTRIBUTE_MIN, ATTRIBUTE_MAX))


def _weighted_overall(attrs: dict) -> int:
    overall = (
        attrs["attr_scoring"] * 0.30
        + attrs["attr_playmaking"] * 0.20
        + attrs["attr_rebounding"] * 0.15
        + attrs["attr_defense"] * 0.15
        + attrs["attr_consistency"] * 0.10
        + attrs["attr_clutch"] * 0.10
    )
    return int(round(_clamp(overall, 30, 99)))


def classify_archetype(profile: dict) -> str:
    scoring = int(profile.get("attr_scoring", 50))
    playmaking = int(profile.get("attr_playmaking", 50))
    rebounding = int(profile.get("attr_rebounding", 50))
    defense = int(profile.get("attr_defense", 50))
    consistency = int(profile.get("attr_consistency", 50))
    overall = int(profile.get("overall_rating", 50))
    age = int(profile.get("age", 27) or 27)
    apg = _safe_float(profile.get("apg"), 0.0)
    rpg = _safe_float(profile.get("rpg"), 0.0)
    threes_pg = _safe_float(profile.get("threes_pg"), 0.0)

    if overall >= 92 and min(scoring, playmaking, rebounding, defense) >= 70:
        return "Unicorn"
    if scoring >= 90 and consistency < 45:
        return "Boom/Bust"
    if scoring >= 90:
        return "Elite Scorer"
    if playmaking >= 85 and apg >= 7:
        return "Floor General"
    if rebounding >= 90 and rpg >= 10:
        return "Glass Cleaner"
    if scoring >= 75 and defense >= 80:
        return "Two-Way Star"
    if defense >= 90 and scoring < 70:
        return "Lockdown Defender"
    if threes_pg >= 3.0:
        return "Sharpshooter"
    if age <= 23 and overall >= 75:
        return "Rising Star"
    if all(55 <= int(profile.get(k, 50)) <= 79 for k in (
        "attr_scoring", "attr_playmaking", "attr_rebounding", "attr_defense", "attr_consistency", "attr_clutch"
    )):
        return "Glue Guy"
    return "Versatile"


def rarity_tier(overall_rating: int, is_legend: bool = False) -> str:
    if is_legend:
        return "Legend"
    if overall_rating >= 92:
        return "Superstar"
    if overall_rating >= 82:
        return "Star"
    if overall_rating >= 70:
        return "Starter"
    if overall_rating >= 55:
        return "Role Player"
    return "Bench"


def _archetype_modifier(archetype: str) -> float:
    modifiers = {
        "Boom/Bust": 0.92,
        "Unicorn": 1.05,
        "Glue Guy": 0.90,
        "Sharpshooter": 1.02,
        "Two-Way Star": 1.03,
    }
    return modifiers.get(archetype, 1.0)


def salary_from_profile(profile: dict) -> int:
    overall = int(profile.get("overall_rating", 50))
    is_legend = bool(profile.get("is_legend", False))
    archetype = str(profile.get("archetype", "Versatile"))
    hot_cold_label = str(profile.get("hot_cold_label", "neutral"))

    base = 2000 + (overall * 100)
    adjusted = base * _archetype_modifier(archetype)
    if hot_cold_label == "hot":
        adjusted *= 1.06
    elif hot_cold_label == "cold":
        adjusted *= 0.94

    rounded = int(round(adjusted / 100.0) * 100)
    if is_legend:
        return int(_clamp(rounded, 12000, 15000))
    return int(_clamp(rounded, 3000, 12000))


def _derive_ts_pct(player: dict) -> float:
    ts_pct = _safe_float(player.get("ts_pct"), 0.0)
    if ts_pct > 0:
        return ts_pct
    fg_pct = _safe_float(player.get("fg_pct"), _safe_float(player.get("fg_pct_avg"), 0.46))
    ft_pct = _safe_float(player.get("ft_pct"), _safe_float(player.get("ft_pct_avg"), 0.75))
    return _clamp((fg_pct * 0.75) + (ft_pct * 0.25), 0.42, 0.70)


def _extract_base(player: dict) -> dict:
    return {
        "player_id": str(player.get("player_id", player.get("id", ""))),
        "player_name": str(player.get("name", player.get("player_name", "Unknown"))),
        "team": str(player.get("team", "")),
        "position": str(player.get("position", "UTIL")),
        "age": int(_safe_float(player.get("age", 27), 27)),
        "ppg": _safe_float(player.get("ppg", player.get("points_avg", 0.0))),
        "rpg": _safe_float(player.get("rpg", player.get("rebounds_avg", 0.0))),
        "apg": _safe_float(player.get("apg", player.get("assists_avg", 0.0))),
        "spg": _safe_float(player.get("spg", player.get("steals_avg", 0.0))),
        "bpg": _safe_float(player.get("bpg", player.get("blocks_avg", 0.0))),
        "tpg": _safe_float(player.get("tpg", player.get("turnovers_avg", 0.0))),
        "threes_pg": _safe_float(player.get("threes_pg", player.get("threes_avg", 0.0))),
        "fg_pct": _safe_float(player.get("fg_pct", player.get("fg_pct_avg", 0.0))),
        "ft_pct": _safe_float(player.get("ft_pct", player.get("ft_pct_avg", 0.0))),
        "ts_pct": _derive_ts_pct(player),
        "usage_rate": _safe_float(player.get("usage_rate", 0.0)),
        "minutes_pg": _safe_float(player.get("minutes_pg", player.get("minutes_avg", 0.0))),
        "points_std": _safe_float(player.get("points_std", 0.0)),
        "rebounds_std": _safe_float(player.get("rebounds_std", 0.0)),
        "assists_std": _safe_float(player.get("assists_std", 0.0)),
        "hot_cold_label": str(player.get("hot_cold_label", "neutral")),
        "is_legend": bool(player.get("is_legend", False)),
    }


def _fp_mean_std(base: dict) -> tuple[float, float]:
    fp_mean = (
        base["ppg"]
        + 1.2 * base["rpg"]
        + 1.5 * base["apg"]
        + 3.0 * base["spg"]
        + 3.0 * base["bpg"]
        + 0.5 * base["threes_pg"]
        - 1.5 * base["tpg"]
    )

    if base["points_std"] > 0 or base["rebounds_std"] > 0 or base["assists_std"] > 0:
        fp_std = math.sqrt(
            max(0.0, base["points_std"]) ** 2
            + (1.2 * max(0.0, base["rebounds_std"])) ** 2
            + (1.5 * max(0.0, base["assists_std"])) ** 2
        )
    else:
        fp_std = max(4.0, fp_mean * 0.28)

    return round(fp_mean, 2), round(fp_std, 2)


def build_player_profiles(active_players: list[dict], include_legends: bool = True) -> list[dict]:
    """Build normalized tournament profiles from active players plus legends."""
    if not active_players:
        active_players = []

    base_active = [_extract_base(p) for p in active_players]

    ppg_vals = [p["ppg"] for p in base_active] or [0.0]
    apg_vals = [p["apg"] for p in base_active] or [0.0]
    rpg_vals = [p["rpg"] for p in base_active] or [0.0]
    ts_vals = [p["ts_pct"] for p in base_active] or [0.0]
    usage_vals = [p["usage_rate"] for p in base_active] or [0.0]
    defense_vals = [(p["spg"] + p["bpg"]) for p in base_active] or [0.0]
    std_vals = [max(0.01, p["points_std"]) for p in base_active] or [1.0]

    profiles = []
    for base in base_active:
        assist_to = base["apg"] / max(base["tpg"], 0.8)
        scoring_signal = (base["ppg"] * 0.5) + (base["ts_pct"] * 100 * 0.3) + (base["usage_rate"] * 0.2)
        playmaking_signal = (base["apg"] * 0.5) + (assist_to * 0.3) + (base["usage_rate"] * 0.2)
        rebounding_signal = base["rpg"]
        defense_signal = base["spg"] + base["bpg"]
        consistency_signal = 1.0 / max(base["points_std"], 0.8)
        clutch_signal = (base["ppg"] * 0.6) + ((base["usage_rate"] + base["ts_pct"] * 100) * 0.4)

        attrs = {
            "attr_scoring": _percentile_rank([(v * 0.5) + (t * 100 * 0.3) + (u * 0.2) for v, t, u in zip(ppg_vals, ts_vals, usage_vals)], scoring_signal),
            "attr_playmaking": _percentile_rank([(a * 0.5) + ((a / max(0.8, _extract_base(active_players[i]).get("tpg", 0.8))) * 0.3) + (u * 0.2) for i, (a, u) in enumerate(zip(apg_vals, usage_vals))], playmaking_signal),
            "attr_rebounding": _percentile_rank(rpg_vals, rebounding_signal),
            "attr_defense": _percentile_rank(defense_vals, defense_signal),
            "attr_consistency": _percentile_rank([1.0 / max(v, 0.8) for v in std_vals], consistency_signal),
            "attr_clutch": _percentile_rank([(v * 0.6) + ((u + t * 100) * 0.4) for v, u, t in zip(ppg_vals, usage_vals, ts_vals)], clutch_signal),
        }

        fp_mean, fp_std = _fp_mean_std(base)
        profile = {
            **base,
            **attrs,
            "fp_mean": fp_mean,
            "fp_std_dev": fp_std,
            "is_active": True,
            "form_trend": base.get("hot_cold_label", "neutral"),
        }
        profile["overall_rating"] = _weighted_overall(profile)
        profile["archetype"] = classify_archetype(profile)
        profile["rarity_tier"] = rarity_tier(profile["overall_rating"], False)
        profile["salary"] = salary_from_profile(profile)
        profiles.append(profile)

    if include_legends:
        for legend in LEGEND_PROFILES:
            profile = {
                "player_id": legend["player_id"],
                "player_name": legend["player_name"],
                "team": "LEG",
                "position": legend["position"],
                "age": 30,
                "ppg": max(24.0, (legend["overall_rating"] - 70) * 0.6),
                "rpg": 6.0,
                "apg": 5.0,
                "spg": 1.4,
                "bpg": 0.9,
                "tpg": 2.8,
                "threes_pg": 1.8,
                "fg_pct": 0.50,
                "ft_pct": 0.82,
                "ts_pct": 0.58,
                "usage_rate": 31.0,
                "minutes_pg": 35.0,
                "points_std": 6.5,
                "rebounds_std": 3.0,
                "assists_std": 2.8,
                "attr_scoring": min(99, legend["overall_rating"]),
                "attr_playmaking": 85,
                "attr_rebounding": 80,
                "attr_defense": 84,
                "attr_consistency": 88,
                "attr_clutch": 95,
                "overall_rating": legend["overall_rating"],
                "archetype": legend["archetype"],
                "rarity_tier": "Legend",
                "salary": legend["salary"],
                "hot_cold_label": "neutral",
                "is_legend": True,
                "is_active": False,
                "legend_era": legend["legend_era"],
                "form_trend": "legend",
            }
            fp_mean, fp_std = _fp_mean_std(profile)
            profile["fp_mean"] = fp_mean
            profile["fp_std_dev"] = fp_std
            profiles.append(profile)

    return profiles
