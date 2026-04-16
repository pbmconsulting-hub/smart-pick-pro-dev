"""
📡 Live Scoreboard (Page 18 - Phase 1D wired)

Live tournament snapshot view backed by tournament manager APIs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

TOURNAMENT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TOURNAMENT_ROOT))

from manager import get_tournament_live_snapshot, list_tournaments


@st.cache_data(ttl=20)
def _list_candidate_tournaments() -> list[dict]:
    live = list_tournaments(status="locked")
    open_rows = list_tournaments(status="open")
    resolved = list_tournaments(status="resolved")
    rows = []
    rows.extend(live)
    rows.extend(open_rows)
    rows.extend(resolved)

    seen: set[int] = set()
    dedup: list[dict] = []
    for row in rows:
        tid = int(row.get("tournament_id", 0) or 0)
        if tid <= 0 or tid in seen:
            continue
        seen.add(tid)
        dedup.append(row)
    return dedup


@st.cache_data(ttl=15)
def _load_snapshot(tournament_id: int, user_email: str) -> dict:
    return get_tournament_live_snapshot(tournament_id=tournament_id, user_email=user_email, top_n=50)


st.set_page_config(
    page_title="Live Scoreboard - Smart Pick Pro",
    page_icon="📡",
    layout="wide",
)

st.markdown(
    """
<style>
    .entry-card {
        border: 1px solid #1f77b4;
        border-radius: 8px;
        padding: 12px;
        background: #0f1419;
        margin-bottom: 10px;
    }
    .entry-score {
        font-size: 24px;
        font-weight: bold;
        color: #34c759;
    }
    .leaderboard-row {
        display: grid;
        grid-template-columns: 60px 220px 120px 120px 120px;
        gap: 12px;
        padding: 12px;
        border-bottom: 1px solid #333;
        align-items: center;
        font-size: 14px;
    }
    .leaderboard-row:hover {
        background: #1a1a2e;
    }
    .rank-pill {
        font-weight: bold;
        text-align: center;
        border-radius: 999px;
        padding: 6px 10px;
        background: #2b2f3a;
        color: #fff;
    }
    .live-indicator {
        color: #ff2d55;
        font-weight: bold;
    }
</style>
""",
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("# 📡 Live Scoreboard")
with col2:
    st.markdown("<span class='live-indicator'>🔴 LIVE SNAPSHOT</span>", unsafe_allow_html=True)
with col3:
    if st.button("🔄 Refresh", use_container_width=True):
        _list_candidate_tournaments.clear()
        _load_snapshot.clear()


candidates = _list_candidate_tournaments()
if not candidates:
    st.info("No tournaments found yet. Create and enter a tournament first.")
    st.stop()

option_map = {
    f"#{int(t['tournament_id'])} | {t.get('tournament_name', 'Tournament')} | {t.get('court_tier', '-')} | {str(t.get('status', '')).upper()}": int(t["tournament_id"])
    for t in candidates
}
selected_label = st.selectbox("Tournament", options=list(option_map.keys()))
selected_tid = option_map[selected_label]
user_email = st.text_input("Filter My Entries (email)", value=str(st.session_state.get("user_email", "") or "").strip().lower())

snapshot = _load_snapshot(selected_tid, user_email)
if not snapshot.get("success"):
    st.error(str(snapshot.get("error", "Snapshot unavailable")))
    st.stop()

tournament = snapshot.get("tournament") or {}
leaderboard = list(snapshot.get("leaderboard") or [])
my_entries = list(snapshot.get("my_entries") or [])
top_players = list(snapshot.get("top_players") or [])

meta1, meta2, meta3, meta4 = st.columns(4)
with meta1:
    st.metric("Tournament", str(tournament.get("tournament_name", "-")))
with meta2:
    st.metric("Tier", str(tournament.get("court_tier", "-")))
with meta3:
    st.metric("Status", str(tournament.get("status", "-")).title())
with meta4:
    st.metric("Entries", f"{int(snapshot.get('entry_count', 0) or 0):,}")


tab_live, tab_entries, tab_leaderboard, tab_joseph = st.tabs(["🎬 Live", "📊 My Entries", "🏅 Leaderboard", "📝 Joseph"])

with tab_live:
    st.markdown("## 🎬 Top Simulated Player Performances")
    if not top_players:
        st.info("No simulated scores yet. Tournament may not be resolved.")
    for player in top_players[:15]:
        line = dict(player.get("line") or {})
        st.markdown(
            f"- **{player.get('player_name') or player.get('player_id')}**: "
            f"{float(player.get('total_fp', 0.0) or 0.0):.2f} FP "
            f"(PTS {int(line.get('points', 0) or 0)} | REB {int(line.get('rebounds', 0) or 0)} | AST {int(line.get('assists', 0) or 0)})"
        )

with tab_entries:
    st.markdown("## 📊 My Entries")
    if not user_email:
        st.info("Enter your email above to show your personal entries.")
    elif not my_entries:
        st.info("No entries found for this email in the selected tournament.")
    for row in my_entries:
        st.markdown(f"### Entry #{int(row.get('entry_id', 0) or 0)}")
        c1, c2, c3 = st.columns([2, 1, 1])
        roster = list(row.get("roster") or [])
        with c1:
            st.markdown("**Roster**")
            if not roster:
                st.caption("No roster payload.")
            for idx, player in enumerate(roster, start=1):
                legend_tag = " (LEGEND)" if bool(player.get("is_legend", False)) else ""
                st.markdown(f"{idx}. {player.get('player_name', player.get('player_id', 'Unknown'))}{legend_tag}")
        with c2:
            st.markdown(
                f"""
                <div class="entry-card" style="text-align:center;">
                    <div style="color:#999; font-size:12px;">Score</div>
                    <div class="entry-score">{float(row.get('display_score', 0.0) or 0.0):.2f}</div>
                    <div style="color:#999; font-size:12px; margin-top:10px;">Computed</div>
                    <div>{float(row.get('computed_score', 0.0) or 0.0):.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"""
                <div class="entry-card" style="text-align:center;">
                    <div style="color:#999; font-size:12px;">Rank</div>
                    <div class="entry-score">#{int(row.get('live_rank', 0) or 0)}</div>
                    <div style="color:#999; font-size:12px; margin-top:10px;">Payout</div>
                    <div>${float(row.get('payout_amount', 0.0) or 0.0):,.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tab_leaderboard:
    st.markdown("## 🏅 Tournament Leaderboard")
    st.markdown(
        """
        <div class="leaderboard-row" style="background:#1a1a2e; font-weight:bold; border-bottom:2px solid #34c759;">
            <div>#</div>
            <div>User</div>
            <div>Score</div>
            <div>LP</div>
            <div>Prize</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not leaderboard:
        st.info("No entries on this tournament yet.")

    for row in leaderboard:
        rank = int(row.get("live_rank", 0) or 0)
        rank_bg = "#34c759" if rank == 1 else ("#c0c0c0" if rank == 2 else ("#cd7f32" if rank == 3 else "#2b2f3a"))
        rank_fg = "#000" if rank in (1, 2, 3) else "#fff"
        st.markdown(
            f"""
            <div class="leaderboard-row">
                <div><span class="rank-pill" style="background:{rank_bg}; color:{rank_fg};">#{rank}</span></div>
                <div>{row.get('display_name', row.get('user_email', '-'))}</div>
                <div style="font-weight:bold; color:#34c759;">{float(row.get('display_score', 0.0) or 0.0):.2f}</div>
                <div>{int(row.get('lp_awarded', 0) or 0)}</div>
                <div style="color:#ffd700;">${float(row.get('payout_amount', 0.0) or 0.0):,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_joseph:
    st.markdown("## 📝 Joseph")
    if not leaderboard:
        st.info("Joseph is waiting for entries to generate commentary.")
    else:
        leader = leaderboard[0]
        st.markdown(
            f"""
            **Current Leader:** {leader.get('display_name', leader.get('user_email', '-'))}\

            **Score:** {float(leader.get('display_score', 0.0) or 0.0):.2f} FP\

            **Take:** Keep an eye on late-game volatility. If your lineup has low-variance profiles,
            you can climb with consistency while boom-or-bust builds fluctuate in the final minutes.
            """
        )

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("← Back to Lobby", use_container_width=True):
        st.switch_page("pages/16_🏟️_Tournament_Lobby.py")
with col2:
    if st.button("📊 View My Profile", use_container_width=True):
        st.switch_page("pages/19_🏆_My_Profile.py")
