"""
🏆 My Profile (Page 19 - Phase 1)

User profile hub with tournament history, achievements, season stats.

Tabs:
  - 👤 Overview: Bio, tier status, season highlights
  - 🏆 Trophy Case: Badges, badges unlocked, achievement tracking
  - 📜 History: Tournament history, ROI tracking
  - 🤝 Head-to-Head: Matchup stats vs other players
  - 🎯 Best Rosters: Top-performing lineups, Boom/Bust analysis
  - 📈 Progression: Rank progression chart, skill breakdown
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent to path
TOURNAMENT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TOURNAMENT_ROOT))

from manager import (
    get_user_best_rosters,
    get_user_career_stats,
    get_user_head_to_head,
    get_user_progression_snapshot,
    list_career_leaderboard,
    list_user_entries,
)
from legal import get_dfs_disclaimer_markdown


def _resolve_user_email() -> str:
    for key in ("user_email", "email"):
        value = str(st.session_state.get(key, "") or "").strip().lower()
        if value:
            return value
    qp = st.query_params
    value = str(qp.get("user", "") or qp.get("email", "")).strip().lower()
    if value:
        return value
    return "you@smartpick.local"


@st.cache_data(ttl=20)
def _load_profile_state(user_email: str) -> dict:
    career = get_user_career_stats(user_email)
    entries = list_user_entries(user_email, limit=100)
    board = list_career_leaderboard(limit=500)
    rank = next((int(row.get("rank", 0) or 0) for row in board if str(row.get("user_email", "")).lower() == user_email), 0)
    head_to_head = get_user_head_to_head(user_email, limit=25)
    rosters = get_user_best_rosters(user_email, limit=5)
    progression = get_user_progression_snapshot(user_email, limit=40)
    return {
        "career": career,
        "entries": entries,
        "rank": rank,
        "head_to_head": head_to_head,
        "best_rosters": rosters,
        "progression": progression,
    }


def _build_milestone_badges(career: dict) -> tuple[list[dict], list[dict]]:
    entries = int(career.get("lifetime_entries", 0) or 0)
    wins = int(career.get("lifetime_wins", 0) or 0)
    earnings = float(career.get("lifetime_earnings", 0.0) or 0.0)
    lp = int(career.get("lifetime_lp", 0) or 0)

    earned = []
    if wins >= 1:
        earned.append({"emoji": "🏅", "name": "First Win", "earned": "Unlocked"})
    if wins >= 3:
        earned.append({"emoji": "🔥", "name": "Hot Streak", "earned": "Unlocked"})
    if earnings >= 500:
        earned.append({"emoji": "💰", "name": "Money Maker", "earned": "Unlocked"})
    if lp >= 500:
        earned.append({"emoji": "🚀", "name": "LP Climber", "earned": "Unlocked"})
    if entries >= 25:
        earned.append({"emoji": "🧠", "name": "Grinder", "earned": "Unlocked"})

    locked = []
    if wins < 10:
        locked.append({"emoji": "🏆", "name": "Champion", "progress": f"{wins} / 10 wins"})
    if earnings < 5000:
        locked.append({"emoji": "🌟", "name": "Legend Earner", "progress": f"${earnings:,.0f} / $5,000"})
    if lp < 2000:
        locked.append({"emoji": "⚡", "name": "Elite Circuit", "progress": f"{lp:,} / 2,000 LP"})

    return earned, locked


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="My Profile - Smart Pick Pro",
    page_icon="🏆",
    layout="wide",
)

# ============================================================================
# STYLE
# ============================================================================

st.markdown("""
<style>
    .profile-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        border: 1px solid #444;
    }
    .stat-box {
        text-align: center;
        padding: 16px;
        background: #0f1419;
        border: 1px solid #333;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .stat-value {
        font-size: 32px;
        font-weight: bold;
        color: #34c759;
    }
    .stat-label {
        font-size: 12px;
        color: #999;
        margin-top: 8px;
    }
    .badge-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
        gap: 12px;
        margin-top: 12px;
    }
    .badge-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 16px;
        background: #0f1419;
        border: 1px solid #333;
        border-radius: 8px;
        min-height: 120px;
        text-align: center;
        font-size: 12px;
        color: #999;
        cursor: pointer;
        transition: border 0.2s;
    }
    .badge-item:hover {
        border-color: #34c759;
        background: #1a2a1f;
    }
    .badge-item-earned {
        border: 2px solid #ffd700;
        background: #1a1811;
        color: #fff;
    }
    .badge-icon {
        font-size: 32px;
        margin-bottom: 8px;
    }
    .tournament-row {
        display: grid;
        grid-template-columns: 100px 150px 100px 80px 100px 80px;
        gap: 12px;
        padding: 12px;
        border-bottom: 1px solid #333;
        align-items: center;
    }
    .tournament-row:hover {
        background: #1a1a2e;
    }
    .tier-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .tier-free {
        background: #333;
        color: #999;
    }
    .tier-premium {
        background: #34c759;
        color: #000;
    }
    .tier-legend {
        background: #ffd700;
        color: #000;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HEADER + TABS
# ============================================================================

st.markdown("# 🏆 My Profile")

active_user_email = _resolve_user_email()
profile_state = _load_profile_state(active_user_email)
career = profile_state.get("career") or {}
history_rows = profile_state.get("entries") or []
global_rank = int(profile_state.get("rank", 0) or 0)
head_to_head_rows = profile_state.get("head_to_head") or []
best_rosters = profile_state.get("best_rosters") or {}
progression_snapshot = profile_state.get("progression") or {}

total_fees = sum(float(item.get("entry_fee", 0.0) or 0.0) for item in history_rows)
total_payout = sum(float(item.get("payout_amount", 0.0) or 0.0) for item in history_rows)
roi_pct = ((total_payout - total_fees) / total_fees * 100.0) if total_fees > 0 else 0.0
earned_badges, available_badges = _build_milestone_badges(career)

tab_overview, tab_trophies, tab_history, tab_h2h, tab_rosters, tab_progression = st.tabs([
    "👤 Overview",
    "🏆 Trophy Case",
    "📜 History",
    "🤝 Head-to-Head",
    "🎯 Best Rosters",
    "📈 Progression"
])


# ============================================================================
# TAB 1: OVERVIEW
# ============================================================================

with tab_overview:
    st.markdown("## 👤 Profile Overview")
    
    display_name = str(career.get("display_name") or active_user_email)
    st.markdown(f"""
    <div class="profile-header">
        <div style="display: grid; grid-template-columns: 100px 1fr; gap: 24px; align-items: start;">
            <div style="font-size: 64px; text-align: center;">🎰</div>
            <div>
                <h2 style="margin: 0;">{display_name}</h2>
                <div style="color: #999; font-size: 14px; margin: 8px 0;">{active_user_email}</div>
                <div style="display: flex; gap: 12px; margin-top: 12px;">
                    <span class="tier-badge tier-premium">💎 Premium</span>
                    <span class="tier-badge tier-legend">🌟 Legend Pass</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Season stats
    st.markdown("### 📊 Season Stats")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-value">{int(career.get('lifetime_entries', 0) or 0)}</div>
            <div class="stat-label">Tournaments</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-value">${float(career.get('lifetime_earnings', 0.0) or 0.0):,.0f}</div>
            <div class="stat-label">Winnings</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-value">{roi_pct:.1f}%</div>
            <div class="stat-label">ROI</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-value">{int(career.get('lifetime_lp', 0) or 0):,}</div>
            <div class="stat-label">Loyalty Points</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        rank_text = f"#{global_rank}" if global_rank > 0 else "-"
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-value">{rank_text}</div>
            <div class="stat-label">Global Rank</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Tier info
    st.markdown("### 💎 Tier Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **Current: Premium ($9.99/mo)**
        - ✅ Pro Court tournaments
        - ✅ Elite Court tournaments
        - ✅ 5% Rake discount (-0.5% total)
        - ⏳ Legend Pass: $4.99/mo add-on
        """)
    
    with col2:
        st.markdown("""
        **Next Tier: Pro Elite**
        - $19.99/mo
        - 10% Rake discount
        - Exclusive events
        - Free Legend Pass
        """)
    
    with col3:
        lp_now = int(career.get("lifetime_lp", 0) or 0)
        progress = min(100, int(lp_now / 2000 * 100)) if lp_now > 0 else 0
        st.metric("Progress to Elite", f"{progress}%", f"{lp_now:,} / 2,000 points")


# ============================================================================
# TAB 2: TROPHY CASE
# ============================================================================

with tab_trophies:
    st.markdown("## 🏆 Trophy Case & Achievements")
    
    # Badges earned
    st.markdown("### 🎖️ Unlocked Badges")
    
    st.markdown("""
    <div class="badge-grid">
    """, unsafe_allow_html=True)
    if not earned_badges:
        st.caption("No unlocked badges yet.")
    for badge in earned_badges:
        st.markdown(f"""
        <div class="badge-item badge-item-earned">
            <div class="badge-icon">{badge['emoji']}</div>
            <div style="font-weight: bold; color: #fff;">{badge['name']}</div>
            <div style="font-size: 10px; color: #999; margin-top: 4px;">{badge['earned']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Badges available
    st.markdown("### 🔓 Available Badges")
    
    st.markdown("""
    <div class="badge-grid">
    """, unsafe_allow_html=True)
    if not available_badges:
        st.caption("All currently tracked milestone badges are unlocked.")
    for badge in available_badges:
        st.markdown(f"""
        <div class="badge-item">
            <div class="badge-icon" style="opacity: 0.5;">{badge['emoji']}</div>
            <div style="font-weight: bold; color: #999;">{badge['name']}</div>
            <div style="font-size: 11px; color: #666; margin-top: 4px;">{badge['progress']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================================
# TAB 3: HISTORY
# ============================================================================

with tab_history:
    st.markdown("## 📜 Tournament History")
    
    st.markdown("""
    <div class="tournament-row" style="background: #1a1a2e; font-weight: bold; border-bottom: 2px solid #34c759;">
        <div>Date</div>
        <div>Tournament</div>
        <div>Score</div>
        <div>Place</div>
        <div>Winnings</div>
        <div>ROI</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not history_rows:
        st.info("No tournament history yet for this user.")

    for entry in history_rows:
        payout = float(entry.get("payout_amount", 0.0) or 0.0)
        fee = float(entry.get("entry_fee", 0.0) or 0.0)
        pnl = payout - fee
        roi_text = f"{pnl:+,.2f}"
        prize_color = "#34c759" if pnl >= 0 else "#ff2d55"
        score_text = f"{float(entry.get('total_score', 0.0) or 0.0):.1f}"
        rank = entry.get("rank")
        rank_text = f"{int(rank)}" if rank is not None else "-"
        st.markdown(f"""
        <div class="tournament-row">
            <div style="font-size: 12px; color: #999;">{entry.get('created_at', '-')}</div>
            <div>{entry.get('tournament_name', '-')}</div>
            <div style="font-weight: bold;">{score_text}</div>
            <div style="color: #999;">{rank_text}</div>
            <div style="color: #ffd700;">${payout:,.2f}</div>
            <div style="color: {prize_color}; font-weight: bold;">{roi_text}</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================================
# TAB 4: HEAD-TO-HEAD
# ============================================================================

with tab_h2h:
    st.markdown("## 🤝 Head-to-Head Records")
    
    st.info("Track your record against specific opponents across tournaments.")
    
    st.markdown("""
    <div class="tournament-row" style="background: #1a1a2e; font-weight: bold; border-bottom: 2px solid #34c759;">
        <div style="grid-template-columns: 1fr;">Opponent</div>
        <div>Matchups</div>
        <div>Your Avg</div>
        <div>Their Avg</div>
        <div>Win %</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not head_to_head_rows:
        st.info("Not enough shared tournaments yet to compute head-to-head stats.")

    for row in head_to_head_rows:
        st.markdown(f"""
        <div class="tournament-row">
            <div style="grid-template-columns: 1fr;">{row.get('opponent_name', row.get('opponent_email', '-'))}</div>
            <div>{int(row.get('matchups', 0) or 0)}</div>
            <div style="color: #34c759; font-weight: bold;">{float(row.get('your_avg_score', 0.0) or 0.0):.1f}</div>
            <div style="color: #999;">{float(row.get('opponent_avg_score', 0.0) or 0.0):.1f}</div>
            <div style="color: #ffd700; font-weight: bold;">{float(row.get('win_pct', 0.0) or 0.0):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================================
# TAB 5: BEST ROSTERS
# ============================================================================

with tab_rosters:
    st.markdown("## 🎯 Best Rosters (Boom vs Bust Analysis)")
    
    st.markdown("### 🔥 Top Performing Lineups")

    entries = list(best_rosters.get("entries") or [])
    if not entries:
        st.info("No resolved roster history yet.")
    for idx, entry in enumerate(entries, start=1):
        st.markdown(
            f"**#{idx}: {entry.get('tournament_name', 'Tournament')}** "
            f"(Score: {float(entry.get('score', 0.0) or 0.0):.1f})"
        )
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            players = list(entry.get("roster_players") or [])
            for p in players[:6]:
                st.markdown(f"- {p}")
            if len(players) > 6:
                st.markdown(f"- [{len(players) - 6} more...]")
        with col2:
            st.markdown(
                f"""
                **Stats:**
                - Avg FP: {float(best_rosters.get('average_score', 0.0) or 0.0):.1f}
                - Std Dev: {float(best_rosters.get('score_std_dev', 0.0) or 0.0):.1f}
                - Boom %: {float(best_rosters.get('boom_rate', 0.0) or 0.0):.1f}%
                """
            )
        with col3:
            rank_val = entry.get("rank")
            rank_text = str(int(rank_val)) if rank_val is not None else "-"
            st.markdown(
                f"""
                **Performance:**
                - Rank: {rank_text}
                - Tier: {entry.get('court_tier', '-')}
                - Prize: ${float(entry.get('payout_amount', 0.0) or 0.0):,.2f}
                """
            )
        st.markdown("---")

    st.markdown("### 📉 Volatility Snapshot")
    st.markdown(
        f"""
        - Boom Threshold: {float(best_rosters.get('boom_threshold', 0.0) or 0.0):.1f} FP
        - Bust Threshold: {float(best_rosters.get('bust_threshold', 0.0) or 0.0):.1f} FP
        - Boom Rate: {float(best_rosters.get('boom_rate', 0.0) or 0.0):.1f}%
        - Bust Rate: {float(best_rosters.get('bust_rate', 0.0) or 0.0):.1f}%
        """
    )


# ============================================================================
# TAB 6: PROGRESSION
# ============================================================================

with tab_progression:
    st.markdown("## 📈 Season Progression")
    
    # Rank progression
    st.markdown("### 📊 Global Rank Over Time")
    
    series = list(progression_snapshot.get("series") or [])
    if not series:
        st.info("Progression data appears after completed tournament entries.")
    else:
        st.line_chart(
            {
                "Cumulative LP": [int(s.get("cumulative_lp", 0) or 0) for s in series],
                "Score": [float(s.get("score", 0.0) or 0.0) for s in series],
            },
            use_container_width=True,
        )
    
    # Skill breakdown
    st.markdown("### 🎓 Skill Development")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Strengths:**
        - 🔥 Contrarian selection (92nd percentile)
        - 📊 Projections accuracy (87th percentile)
        - 💰 Money management (81st percentile)
        
        **Areas to Develop:**
        - 📉 Late-game adjustments (42nd percentile)
        - 🏀 Game flow prediction (58th percentile)
        """)
    
    with col2:
        skills = dict(progression_snapshot.get("skills") or {})
        
        if skills:
            skill_df = {"Skill": list(skills.keys()), "Percentile": list(skills.values())}
            st.bar_chart(skill_df.set_index("Skill"), use_container_width=True)
        else:
            st.caption("Skill profile unavailable until more tournament history exists.")


# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Lobby", use_container_width=True):
        st.switch_page("pages/16_🏟️_Tournament_Lobby.py")

with col2:
    st.markdown("")

with col3:
    if st.button("📜 Record Books →", use_container_width=True):
        st.switch_page("pages/20_📜_Record_Books.py")

st.markdown("---")
st.markdown(get_dfs_disclaimer_markdown())
