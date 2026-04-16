"""NBA sport adapter for tournament routing."""

from __future__ import annotations

SPORT_CODE = "nba"
SPORT_LABEL = "NBA"


def normalize_stat_line(line: dict) -> dict:
    return {
        "points": int(line.get("points", 0) or 0),
        "rebounds": int(line.get("rebounds", 0) or 0),
        "assists": int(line.get("assists", 0) or 0),
        "steals": int(line.get("steals", 0) or 0),
        "blocks": int(line.get("blocks", 0) or 0),
        "turnovers": int(line.get("turnovers", 0) or 0),
        "threes": int(line.get("threes", 0) or 0),
    }


def score_line(line: dict) -> float:
    stat = normalize_stat_line(line)
    return round(
        (stat["points"] * 1.0)
        + (stat["rebounds"] * 1.2)
        + (stat["assists"] * 1.5)
        + (stat["steals"] * 3.0)
        + (stat["blocks"] * 3.0)
        + (stat["threes"] * 0.5)
        - (stat["turnovers"] * 1.5),
        2,
    )
