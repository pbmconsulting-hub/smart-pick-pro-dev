"""
Tournament Mode Manager

Manages switching between the main NBA app and the isolated tournament environment.
This is the central hub for environment toggling.
"""

import streamlit as st


def initialize_tournament_mode():
    """Initialize tournament mode session state on app startup."""
    if "tournament_mode_enabled" not in st.session_state:
        st.session_state["tournament_mode_enabled"] = False
    if "tournament_mode_previous_page" not in st.session_state:
        st.session_state["tournament_mode_previous_page"] = None


def toggle_tournament_mode():
    """Toggle between NBA app and tournament mode."""
    st.session_state["tournament_mode_enabled"] = not st.session_state["tournament_mode_enabled"]


def is_tournament_mode_active() -> bool:
    """Check if tournament mode is currently active."""
    return st.session_state.get("tournament_mode_enabled", False)


def render_tournament_toggle():
    """Render the tournament mode toggle button in the sidebar."""
    initialize_tournament_mode()
    
    if is_tournament_mode_active():
        # Active state: show tournament environment badge + exit button
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
            border: 2px solid rgba(255, 215, 0, 0.5);
            border-radius: 12px;
            padding: 14px;
            text-align: center;
            margin-bottom: 12px;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.25);
        ">
            <div style="
                color: #000;
                font-weight: 700;
                font-size: 0.95rem;
                margin-bottom: 4px;
            ">🏟️ TOURNAMENT MODE</div>
            <div style="
                color: rgba(0, 0, 0, 0.70);
                font-size: 0.80rem;
            ">Isolated Tournament Environment</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("← Exit to NBA App", use_container_width=True, type="secondary"):
            toggle_tournament_mode()
            st.rerun()
    
    else:
        # Inactive state: show tournament entry button
        st.markdown("""
        <div style="
            background: rgba(255, 215, 0, 0.08);
            border: 1px solid rgba(255, 215, 0, 0.25);
            border-radius: 12px;
            padding: 14px;
            text-align: center;
            margin-bottom: 12px;
        ">
            <div style="
                color: #999;
                font-size: 0.80rem;
                margin-bottom: 8px;
            ">💡 Try the new 2024 feature</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🏟️ Enter Tournament Mode", use_container_width=True, type="primary"):
            toggle_tournament_mode()
            st.rerun()


def redirect_to_tournament_lobby():
    """Redirect to tournament lobby if tournament mode is active."""
    if is_tournament_mode_active():
        st.switch_page("pages/tournament/16_🏟️_Tournament_Lobby.py")


def get_tournament_pages():
    """Get list of tournament pages for multipage navigation."""
    return [
        "pages/tournament/16_🏟️_Tournament_Lobby.py",
        "pages/tournament/17_🏗️_Roster_Builder.py",
        "pages/tournament/18_📡_Live_Scoreboard.py",
        "pages/tournament/19_🏆_My_Profile.py",
        "pages/tournament/20_📜_Record_Books.py",
    ]
