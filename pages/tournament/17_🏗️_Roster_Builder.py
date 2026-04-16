"""
🏗️ Roster Builder (Page 17 - Phase 1) - Main App Integration

Wrapper that loads tournament roster builder with mode check.
"""

import streamlit as st
import sys
from pathlib import Path

# Add tournament root to path
TOURNAMENT_ROOT = Path(__file__).parent.parent.parent / "tournament"
sys.path.insert(0, str(TOURNAMENT_ROOT))

from utils.tournament_mode import is_tournament_mode_active, render_tournament_toggle

# Check if in tournament mode
if not is_tournament_mode_active():
    st.warning("⚠️ Tournament Mode is disabled. Use the toggle in the main app sidebar.")
    st.stop()

# Load the actual roster builder page from the tournament package
exec(open(TOURNAMENT_ROOT / "pages" / "17_🏗️_Roster_Builder.py").read())
