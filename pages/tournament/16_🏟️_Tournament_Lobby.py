"""
🏟️ Tournament Lobby (Page 16 - Phase 1)

Tonight's tournaments, upcoming, past results, leaderboard, Joseph commentary.
INTEGRATED INTO MAIN APP VIA TOURNAMENT MODE TOGGLE

Tabs:
  - 🎮 Tonight: Live tournaments + entry
  - 📅 Upcoming: Schedule for next week
  - 📜 Results: Past tournament outcomes
  - 🏆 Leaderboard: Season LP standings
  - 🎙️ Joseph's Desk: Preview & commentary
"""

import streamlit as st
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# Add tournament root to path for imports
TOURNAMENT_ROOT = Path(__file__).parent.parent.parent / "tournament"
sys.path.insert(0, str(TOURNAMENT_ROOT))

from config import TOURNAMENT_CONFIG, PREMIUM_TIERS
from utils.tournament_manager import TournamentManager
from utils.tournament_gate import TournamentGate
from data.legends import get_available_legends_for_month
from utils.tournament_mode import is_tournament_mode_active, render_tournament_toggle, toggle_tournament_mode
from engine.joseph_brain import (
    joseph_tournament_overpriced_call,
    joseph_tournament_ownership_reaction,
    joseph_tournament_preview,
    joseph_tournament_sleeper_pick,
)


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Tournament Lobby - Smart Pick Pro",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CHECK IF IN TOURNAMENT MODE
# ============================================================================

if not is_tournament_mode_active():
    st.warning("⚠️ Tournament Mode is disabled. Use the toggle in the sidebar to enter Tournament Mode.")
    st.stop()

# ============================================================================
# SESSION STATE INIT
# ============================================================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_tier" not in st.session_state:
    st.session_state.user_tier = "free"
if "has_legend_pass" not in st.session_state:
    st.session_state.has_legend_pass = False
if "user_state" not in st.session_state:
    st.session_state.user_state = "CA"  # Default


# ============================================================================
# STYLE
# ============================================================================

st.markdown("""
<style>
    .tournament-card {
        border: 1px solid #1f77b4;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
    }
    .tournament-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .tournament-name {
        font-size: 18px;
        font-weight: bold;
        color: #ffffff;
    }
    .tournament-entry-fee {
        font-size: 16px;
        font-weight: bold;
        color: #34c759;
    }
    .tournament-meta {
        font-size: 12px;
        color: #999;
        margin-bottom: 8px;
    }
    .fill-meter {
        height: 8px;
        background: #333;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 8px;
    }
    .fill-meter-bar {
        height: 100%;
        background: linear-gradient(90deg, #34c759, #00ff88);
        transition: width 0.3s ease;
    }
    .entry-btn {
        width: 100%;
        padding: 8px;
        background: #1f77b4;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-weight: bold;
    }
    .entry-btn:hover {
        background: #2590e8;
    }
    .entry-btn-locked {
        background: #666;
        cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SIDEBAR: TOURNAMENT MODE + USER INFO
# ============================================================================

with st.sidebar:
    st.markdown("## 🏟️ Tournament Environment")
    render_tournament_toggle()
    
    st.markdown("---")
    st.markdown("## 👤 User Info")
    
    if st.session_state.user_id:
        st.success(f"✅ Logged in (Demo User {st.session_state.user_id})")
        
        tier_badge = {
            "free": "🔵 Free",
            "premium": "🟠 Premium",
        }
        st.info(f"{tier_badge.get(st.session_state.user_tier, 'Unknown')}")
        
        if st.session_state.has_legend_pass:
            st.success("⚡ Legend Pass Active")
    else:
        st.warning("👤 Not logged in (Demo mode)")
        st.session_state.user_id = 1  # Auto-login for demo
        st.session_state.user_tier = "premium"
        st.session_state.has_legend_pass = True
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### 📊 Season Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("League Points", "1,250")
    with col2:
        st.metric("Tournaments", "23")
    
    st.markdown("---")
    
    # Ads / Upgrades
    if st.session_state.user_tier == "free":
        st.markdown("### 💎 Upgrade")
        st.info("**Premium: $9.99/mo**\n- Unlock Pro Court\n- Unlock Elite Court")
        if st.button("Upgrade to Premium"):
            st.info("🔄 Redirecting to Stripe checkout...")


# ============================================================================
# MAIN PAGE
# ============================================================================

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("# 🏟️ Tournament Lobby")
with col2:
    st.markdown(f"**{datetime.now().strftime('%A, %B %d, %Y')}**")

# Tabs
tab_tonight, tab_upcoming, tab_results, tab_leaderboard, tab_joseph = st.tabs([
    "🎮 Tonight",
    "📅 Upcoming",
    "📜 Results",
    "🏆 Leaderboard",
    "🎙️ Joseph's Desk"
])


# ============================================================================
# TAB 1: TONIGHT
# ============================================================================

with tab_tonight:
    st.markdown("## Tonight's Tournaments")
    
    # Mock data (in production, fetch from DB)
    tonight_tournaments = [
        {
            "tournament_id": 1,
            "name": "🎯 Sunday Night Scorer",
            "type": "pro_court",
            "entry_fee": 5.0,
            "current_entries": 18,
            "max_entries": 24,
            "lock_time_minutes": 45,
            "prize_pool": 100.0,
            "description": "High-scoring showdown. LeBron vs Luka matchup.",
        },
        {
            "tournament_id": 2,
            "name": "💰 Elite Court Championship",
            "type": "elite_court",
            "entry_fee": 25.0,
            "current_entries": 8,
            "max_entries": 12,
            "lock_time_minutes": 60,
            "prize_pool": 200.0,
            "description": "Premium competition. Top scorers only.",
        },
        {
            "tournament_id": 3,
            "name": "🏀 Open Court Free Play",
            "type": "open_court",
            "entry_fee": 0.0,
            "current_entries": 42,
            "max_entries": 100,
            "lock_time_minutes": 30,
            "prize_pool": 0.0,
            "description": "No entry fee. Perfect for learning.",
        },
    ]
    
    for tourney in tonight_tournaments:
        st.markdown(f"""
        <div class="tournament-card">
            <div class="tournament-card-header">
                <div class="tournament-name">{tourney['name']}</div>
                <div class="tournament-entry-fee">${tourney['entry_fee']}</div>
            </div>
            <div class="tournament-meta">
                🕐 Locks in {tourney['lock_time_minutes']} min | 
                💰 ${tourney['prize_pool']} Prize Pool | 
                🏆 {tourney['type'].upper()}
            </div>
            <p>{tourney['description']}</p>
        """, unsafe_allow_html=True)
        
        # Fill meter
        fill_pct = tourney["current_entries"] / tourney["max_entries"]
        st.markdown(f"""
            <div class="fill-meter">
                <div class="fill-meter-bar" style="width: {fill_pct * 100}%"></div>
            </div>
            <small>{tourney['current_entries']}/{tourney['max_entries']} entries</small>
        """, unsafe_allow_html=True)
        
        # Entry button
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("📝 View Details", key=f"details_{tourney['tournament_id']}"):
                st.session_state.selected_tournament = tourney['tournament_id']
                st.info(f"View detailed rosters for {tourney['name']}")
        with col2:
            if st.button("✅ Enter", key=f"enter_{tourney['tournament_id']}"):
                st.session_state.show_roster_builder = True
                st.session_state.selected_tournament = tourney['tournament_id']
                st.success(f"✅ Entering {tourney['name']}... (Roster Builder →)")
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("")


# ============================================================================
# TAB 2: UPCOMING
# ============================================================================

with tab_upcoming:
    st.markdown("## Upcoming Tournaments")
    
    upcoming_tournaments = [
        {
            "name": "🌙 Monday Night Matchup",
            "start_time": "Monday, 7:30 PM ET",
            "entry_fee": 5.0,
            "tournament_type": "Pro Court",
        },
        {
            "name": "🔥 Mid-Week Grind",
            "start_time": "Wednesday, 7:00 PM ET",
            "entry_fee": 10.0,
            "tournament_type": "Elite Court",
        },
        {
            "name": "🏀 Friday Night Lights",
            "start_time": "Friday, 8:00 PM ET",
            "entry_fee": 5.0,
            "tournament_type": "Pro Court",
        },
    ]
    
    for tourney in upcoming_tournaments:
        st.markdown(f"""
        **{tourney['name']}**
        - 🕐 {tourney['start_time']}
        - 💰 ${tourney['entry_fee']} entry
        - 🏆 {tourney['tournament_type']}
        """)
        st.markdown("---")


# ============================================================================
# TAB 3: RESULTS
# ============================================================================

with tab_results:
    st.markdown("## Past Tournament Results")
    
    past_results = [
        {
            "name": "Sunday Night Scorer #47",
            "date": "Yesterday",
            "placement": 3,
            "prize": 45.50,
            "lp": 35,
        },
        {
            "name": "Pro Court Weekend",
            "date": "2 days ago",
            "placement": 1,
            "prize": 150.00,
            "lp": 100,
        },
    ]
    
    for result in past_results:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Tournament", result["name"].split("#")[0], result["date"])
        with col2:
            st.metric("Placement", f"#{result['placement']}", result['date'])
        with col3:
            st.metric("Prize", f"${result['prize']}", f"+{result['lp']} LP")
        with col4:
            st.markdown("")


# ============================================================================
# TAB 4: LEADERBOARD
# ============================================================================

with tab_leaderboard:
    st.markdown("## Season Leaderboard")
    
    leaderboard_data = [
        {"rank": 1, "user": "SaberMetrics_Pro", "lp": 5230, "tournaments": 47},
        {"rank": 2, "user": "DFS_Grinder", "lp": 4950, "tournaments": 52},
        {"rank": 3, "user": "YourName", "lp": 1250, "tournaments": 23},
        {"rank": 4, "user": "NbaStatsGuy", "lp": 1180, "tournaments": 19},
        {"rank": 5, "user": "Fantasy_Killer", "lp": 980, "tournaments": 16},
    ]
    
    cols = st.columns(4)
    cols[0].markdown("**Rank**")
    cols[1].markdown("**Player**")
    cols[2].markdown("**League Points**")
    cols[3].markdown("**Tournaments**")
    st.markdown("---")
    
    for row in leaderboard_data:
        cols = st.columns(4)
        cols[0].markdown(f"#{row['rank']}")
        cols[1].markdown(f"**{row['user']}**" if row['rank'] == 3 else row['user'])
        cols[2].markdown(f"{row['lp']:,}")
        cols[3].markdown(f"{row['tournaments']}")


# ============================================================================
# TAB 5: JOSEPH'S DESK
# ============================================================================

with tab_joseph:
    st.markdown("## 🎙️ Joseph's Desk")

    featured_tournament = tonight_tournaments[0] if tonight_tournaments else {}
    tier_map = {
        "open_court": "Open",
        "pro_court": "Pro",
        "elite_court": "Elite",
        "championship": "Championship",
    }
    preview_payload = {
        "tournament_name": featured_tournament.get("name", "Tonight's Tournament"),
        "court_tier": tier_map.get(featured_tournament.get("type", ""), "Open"),
        "entry_fee": featured_tournament.get("entry_fee", 0.0),
        "max_entries": featured_tournament.get("max_entries", 24),
    }
    top_players = [
        {"player_name": "LeBron James", "salary": 11800},
        {"player_name": "Jayson Tatum", "salary": 11200},
        {"player_name": "Anthony Davis", "salary": 10400},
    ]
    ownership_data = [
        {"player_name": "LeBron James", "ownership_pct": 58},
        {"player_name": "Jayson Tatum", "ownership_pct": 34},
        {"player_name": "Derrick Jones Jr.", "ownership_pct": 15},
    ]

    st.markdown("### 🏀 Tonight's Commissioner Preview")
    st.markdown(joseph_tournament_preview(preview_payload, top_players))

    st.markdown("### 📊 My Sleeper")
    st.success(
        joseph_tournament_sleeper_pick(
            "Derrick Jones Jr.",
            5200,
            "Defensive matchup leverage and low projected ownership make this a clean tournament pivot.",
        )
    )

    st.markdown("### 🔥 Boom/Bust Watch")
    st.warning(
        joseph_tournament_overpriced_call(
            "Kristaps Porzingis",
            9100,
            "Foul-trouble volatility makes that tag too rich for this field.",
        )
    )

    st.markdown("### 💡 Ownership Report")
    st.info(joseph_tournament_ownership_reaction(preview_payload, ownership_data))
    
    # Expert tips
    st.markdown("---")
    st.markdown("### 📚 Tournament Tips")
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **Ownership Matters**
        - Avoid chalk (>40% owned) unless you're stacking.
        - 15–25% owned is the sweet spot for upside.
        - Contrarian plays win close tournaments.
        """)
    with col2:
        st.warning("""
        **Late Swaps**
        - You get 1 free swap if a player is ruled OUT.
        - Use it strategically (swap to a cheaper player to lock salary).
        - Swaps lock 5 min before tournament lock.
        """)


# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; font-size: 12px; color: #999;">
  <p>Smart Pick Pro Tournament Lobby | Phase 1 (MVP) | 2026-04-15</p>
  <p>Built with ❤️ for DFS enthusiasts</p>
</div>
""", unsafe_allow_html=True)
