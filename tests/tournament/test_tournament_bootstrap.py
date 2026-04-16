from tournament.bootstrap import ensure_profile_pool


def test_ensure_profile_pool(monkeypatch):
    monkeypatch.setattr("tournament.bootstrap.initialize_tournament_database", lambda: True)
    monkeypatch.setattr("tournament.bootstrap.load_players_data", lambda: [{"player_id": "1", "name": "A", "points_avg": 10.0}])
    monkeypatch.setattr("tournament.bootstrap.build_player_profiles", lambda players, include_legends: [{"player_id": "1", "player_name": "A"}])
    monkeypatch.setattr("tournament.bootstrap.upsert_player_profiles", lambda profiles: len(profiles))

    result = ensure_profile_pool(minimum_profiles=1)
    assert result["ok"] is True
    assert result["generated_profiles"] == 1
    assert result["upserted_profiles"] == 1
