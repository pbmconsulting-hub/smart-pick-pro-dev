"""MLB sport adapter scaffold for tournament routing."""

from __future__ import annotations

SPORT_CODE = "mlb"
SPORT_LABEL = "MLB"


def normalize_stat_line(line: dict) -> dict:
    return {
        "hits": int(line.get("hits", 0) or 0),
        "runs": int(line.get("runs", 0) or 0),
        "rbi": int(line.get("rbi", 0) or 0),
        "home_runs": int(line.get("home_runs", 0) or 0),
        "stolen_bases": int(line.get("stolen_bases", 0) or 0),
    }


def score_line(line: dict) -> float:
    stat = normalize_stat_line(line)
    return round(
        (stat["hits"] * 3.0)
        + (stat["runs"] * 2.0)
        + (stat["rbi"] * 2.0)
        + (stat["home_runs"] * 5.0)
        + (stat["stolen_bases"] * 4.0),
        2,
    )
