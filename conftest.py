"""Root conftest to prevent tournament package imports during testing"""
import sys
import pytest
from unittest.mock import MagicMock
from pathlib import Path

# Block all heavy imports before they load
sys.modules['streamlit'] = MagicMock()
sys.modules['st'] = MagicMock()
sys.modules['nba_api'] = MagicMock()
sys.modules['nba_api.stats'] = MagicMock()
sys.modules['nba_api.stats.endpoints'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['pd'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['np'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.ensemble'] = MagicMock()
sys.modules['xgboost'] = MagicMock()
sys.modules['catboost'] = MagicMock()
sys.modules['fastapi'] = MagicMock()
sys.modules['uvicorn'] = MagicMock()
sys.modules['flask'] = MagicMock()
sys.modules['aiohttp'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['bs4.element'] = MagicMock()
sys.modules['BeautifulSoup4'] = MagicMock()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Prevent tournament package from auto-importing."""
    # Make tournament a namespace package without __init__.py execution
    tournament_init = Path(__file__).parent / "tournament" / "__init__.py"
    if tournament_init.exists():
        sys.modules['tournament'] = MagicMock()
        sys.modules['tournament.bootstrap'] = MagicMock()
        sys.modules['tournament.database'] = MagicMock()
        sys.modules['tournament.events'] = MagicMock()
        sys.modules['tournament.exports'] = MagicMock()
        sys.modules['tournament.gate'] = MagicMock()
        sys.modules['tournament.jobs'] = MagicMock()
        sys.modules['tournament.legends'] = MagicMock()
        sys.modules['tournament.manager'] = MagicMock()
        sys.modules['tournament.payout'] = MagicMock()
