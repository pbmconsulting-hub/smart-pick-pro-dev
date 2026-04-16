"""Bootstrap helpers for the isolated tournament subsystem."""

from __future__ import annotations

from data.data_manager import load_players_data

from tournament.database import initialize_tournament_database, upsert_player_profiles
from tournament.profiles import build_player_profiles


def ensure_profile_pool(minimum_profiles: int = 150, include_legends: bool = True) -> dict:
    """Ensure tournament profile pool exists in isolated DB.

    Returns summary metadata for UI diagnostics.
    """
    initialize_tournament_database()

    players = load_players_data() or []
    profiles = build_player_profiles(players, include_legends=include_legends)
    inserted = upsert_player_profiles(profiles)

    return {
        "source_players": len(players),
        "generated_profiles": len(profiles),
        "upserted_profiles": inserted,
        "minimum_target": int(minimum_profiles),
        "ok": len(profiles) >= int(minimum_profiles),
    }
