"""
🏆 My Profile (Page 19 - Phase 1) - Main App Integration

Wrapper that loads profile with mode check.
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

# Load the actual profile page from the tournament package
exec(open(TOURNAMENT_ROOT / "pages" / "19_🏆_My_Profile.py").read())
