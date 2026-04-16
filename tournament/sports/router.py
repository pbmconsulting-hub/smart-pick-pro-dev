"""Sport router utilities for tournament engines and pages."""

from __future__ import annotations

from tournament.sports import mlb, nba, nfl

SPORT_HANDLERS = {
    "nba": nba,
    "mlb": mlb,
    "nfl": nfl,
}


def normalize_sport_code(sport: str) -> str:
    code = str(sport or "nba").strip().lower()
    return code if code in SPORT_HANDLERS else "nba"


def get_sport_handler(sport: str):
    return SPORT_HANDLERS[normalize_sport_code(sport)]


def list_supported_sports() -> list[dict]:
    out = []
    for code, module in SPORT_HANDLERS.items():
        out.append(
            {
                "sport": code,
                "label": str(getattr(module, "SPORT_LABEL", code.upper())),
                "module": str(getattr(module, "__name__", "")),
            }
        )
    out.sort(key=lambda x: x["sport"])
    return out
