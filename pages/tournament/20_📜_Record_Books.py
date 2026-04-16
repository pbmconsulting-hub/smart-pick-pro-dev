"""
📜 Record Books (Page 20 - Phase 1) - Main App Integration

Wrapper that loads record books with mode check.
"""

import streamlit as st
import sys
from pathlib import Path

# Add tournament root to path
TOURNAMENT_ROOT = Path(__file__).parent.parent.parent / "tournament"
sys.path.insert(0, str(TOURNAMENT_ROOT))

from utils.tournament_mode import is_tournament_mode_active

# Check if in tournament mode
if not is_tournament_mode_active():
    st.warning("⚠️ Tournament Mode is disabled. Use the toggle in the main app sidebar.")
    st.stop()

# Load the actual record books page from the tournament package
exec(open(TOURNAMENT_ROOT / "pages" / "20_📜_Record_Books.py").read())
