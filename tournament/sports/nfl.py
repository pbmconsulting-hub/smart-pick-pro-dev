"""NFL sport adapter scaffold for tournament routing."""

from __future__ import annotations

SPORT_CODE = "nfl"
SPORT_LABEL = "NFL"


def normalize_stat_line(line: dict) -> dict:
    return {
        "pass_yards": int(line.get("pass_yards", 0) or 0),
        "pass_tds": int(line.get("pass_tds", 0) or 0),
        "rush_yards": int(line.get("rush_yards", 0) or 0),
        "rush_tds": int(line.get("rush_tds", 0) or 0),
        "receptions": int(line.get("receptions", 0) or 0),
        "rec_yards": int(line.get("rec_yards", 0) or 0),
        "rec_tds": int(line.get("rec_tds", 0) or 0),
        "turnovers": int(line.get("turnovers", 0) or 0),
    }


def score_line(line: dict) -> float:
    stat = normalize_stat_line(line)
    return round(
        (stat["pass_yards"] * 0.04)
        + (stat["pass_tds"] * 4.0)
        + (stat["rush_yards"] * 0.1)
        + (stat["rush_tds"] * 6.0)
        + (stat["receptions"] * 1.0)
        + (stat["rec_yards"] * 0.1)
        + (stat["rec_tds"] * 6.0)
        - (stat["turnovers"] * 2.0),
        2,
    )
