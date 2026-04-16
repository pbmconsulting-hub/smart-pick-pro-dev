"""Shared fixtures for tournament integration tests.

Every test gets an isolated temporary SQLite database via monkeypatch so
no test mutates the real ``db/tournament.db``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock parent‑engine modules so integration imports resolve without the full app.
# These MUST execute before any tournament.* import.
# ---------------------------------------------------------------------------
_mock_game_pred = MagicMock()
_mock_game_pred.BLOWOUT_MARGIN_THRESHOLD = 15
_mock_game_pred.LEAGUE_AVG_DRTG = 110.0
_mock_game_pred.LEAGUE_AVG_ORTG = 110.0
_mock_game_pred.LEAGUE_AVG_PACE = 100.0
_mock_game_pred._calculate_expected_possessions = MagicMock(return_value=100.0)
_mock_game_pred._score_from_possession_model = MagicMock(return_value=105.0)
_mock_game_pred._simulate_single_game = MagicMock(return_value=(108, 102, False))

_mock_engine_sim = MagicMock()
_mock_engine_sim.run_quantum_matrix_simulation = MagicMock(
    return_value={"simulated_results": list(range(10, 40))}
)

sys.modules.setdefault("engine", MagicMock())
sys.modules["engine.game_prediction"] = _mock_game_pred
sys.modules["engine.simulation"] = _mock_engine_sim

_mock_data = MagicMock()
_mock_data.data_manager = MagicMock()
_mock_data.data_manager.load_players_data = MagicMock(return_value=[])
sys.modules.setdefault("data", _mock_data)
sys.modules.setdefault("data.data_manager", _mock_data.data_manager)
sys.modules.setdefault("tracking", MagicMock())
sys.modules.setdefault("tracking.database", MagicMock())

# Mock stripe so import doesn't fail
sys.modules.setdefault("stripe", MagicMock())

# ---------------------------------------------------------------------------
# Now safe to import the real tournament code
# ---------------------------------------------------------------------------
import tournament.database as tdb  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect tournament DB to a temp directory for every test."""
    monkeypatch.setattr(tdb, "DB_DIRECTORY", tmp_path)
    monkeypatch.setattr(tdb, "TOURNAMENT_DB_PATH", tmp_path / "tournament.db")
    assert tdb.initialize_tournament_database()
    yield tmp_path
