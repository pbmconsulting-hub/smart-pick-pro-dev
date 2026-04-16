"""
📜 Record Books (Page 20 - Phase 1D wired)

All-time records, championships, season awards, leaderboards, Hall of Fame.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Add parent to path
TOURNAMENT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TOURNAMENT_ROOT))

from manager import (  # noqa: E402
    get_all_time_records,
    get_championship_overview,
    get_season_awards_snapshot,
    list_badge_leaders,
    list_championship_history,
    list_hall_of_fame_candidates,
)


@st.cache_data(ttl=30)
def _load_record_books_data() -> dict:
    try:
        return {
            "overview": get_championship_overview(),
            "history": list_championship_history(limit=30),
            "awards": get_season_awards_snapshot(),
            "records": get_all_time_records(),
            "badge_leaders": list_badge_leaders(limit=20),
            "hof": list_hall_of_fame_candidates(limit=20),
            "error": "",
        }
    except Exception as exc:
        return {
            "overview": {},
            "history": [],
            "awards": {},
            "records": {},
            "badge_leaders": [],
            "hof": [],
            "error": str(exc),
        }


st.set_page_config(
    page_title="Record Books - Smart Pick Pro",
    page_icon="📜",
    layout="wide",
)

st.markdown(
    """
<style>
    .record-row {
        display: grid;
        grid-template-columns: 70px 220px 170px 150px 120px;
        gap: 12px;
        padding: 12px;
        border-bottom: 1px solid #333;
        align-items: center;
        font-size: 14px;
    }
    .record-row:hover {
        background: #1a1a2e;
    }
    .record-rank {
        font-weight: bold;
        text-align: center;
        color: #34c759;
    }
    .record-value {
        font-weight: bold;
        color: #ffd700;
        font-size: 16px;
    }
    .award-card {
        border: 1px solid #444;
        border-radius: 8px;
        padding: 16px;
        background: #0f1419;
        margin-bottom: 12px;
    }
    .award-name {
        font-weight: bold;
        font-size: 16px;
        color: #fff;
    }
    .award-winner {
        color: #34c759;
        font-weight: bold;
        margin-top: 8px;
    }
    .hof-card {
        border: 2px solid #ffd700;
        border-radius: 8px;
        padding: 16px;
        background: #1a1811;
        margin-bottom: 12px;
    }
    .hof-stat {
        display: flex;
        justify-content: space-between;
        border-bottom: 1px solid #333;
        padding: 8px 0;
        font-size: 14px;
    }
    .championship-banner {
        border: 2px solid #ffd700;
        border-radius: 8px;
        padding: 16px;
        background: linear-gradient(135deg, #1a1811 0%, #2a2518 100%);
        margin-bottom: 12px;
        box-shadow: 0 0 12px rgba(255, 215, 0, 0.2);
    }
    .championship-banner h3 {
        color: #ffd700;
        margin: 0 0 8px 0;
    }
    .championship-banner .banner-detail {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        font-size: 13px;
    }
    .career-level-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        background: #ffd700;
        color: #000;
        margin-left: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown("# 📜 Record Books")
st.markdown("Track championship history, awards, and all-time records for Smart Pick Pro.")

if st.button("🔄 Refresh Record Books"):
    _load_record_books_data.clear()

data = _load_record_books_data()
if data.get("error"):
    st.warning(f"Record books data unavailable: {data['error']}")


tab_champs, tab_awards, tab_records, tab_badge_leaders, tab_hof = st.tabs(
    ["🏆 Championships", "🎖️ Season Awards", "🏅 All-Time Records", "🌟 Badge Leaders", "🏛️ Hall of Fame"]
)

with tab_champs:
    st.markdown("## 🏆 Championship History")

    overview = data.get("overview") or {}
    latest = (overview or {}).get("latest_tournament") or {}
    active_status = str(latest.get("status", "No Championship Yet")).title()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estimated Purse", f"${float(overview.get('estimated_purse', 0.0) or 0.0):,.2f}")
    with col2:
        st.metric("Entries", f"{int(overview.get('active_entries', 0) or 0):,}")
    with col3:
        st.metric("Status", active_status)

    st.caption(
        f"Resolved championships: {int(overview.get('resolved_championships', 0) or 0)} / "
        f"Total championships: {int(overview.get('total_championships', 0) or 0)}"
    )

    st.markdown("---")
    st.markdown("### Past Championships")

    st.markdown(
        """
        <div class="record-row" style="background: #1a1a2e; font-weight: bold; border-bottom: 2px solid #34c759;">
            <div>Season</div>
            <div>Champion</div>
            <div>Final Score</div>
            <div>Prize</div>
            <div>Date</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    history = data.get("history") or []
    if not history:
        st.info("No championship history yet. Resolve a Championship-tier tournament to populate this table.")
    for row in history:
        season = str(row.get("season_label") or f"Championship #{row.get('championship_id', '?')}")
        champ = str(row.get("winner_display_name") or row.get("winner_email") or "Unknown")
        score = float(row.get("winning_score", 0.0) or 0.0)
        prize = float(row.get("payout_amount", 0.0) or 0.0)
        created_at = str(row.get("created_at", ""))
        roster = row.get("roster") or []
        roster_names = ", ".join(str(p.get("player_name", p.get("name", "?"))) for p in roster[:5])
        if len(roster) > 5:
            roster_names += f" +{len(roster) - 5} more"
        st.markdown(
            f"""
            <div class="championship-banner">
                <h3>🏆 {season}</h3>
                <div class="banner-detail">
                    <span style="color: #ffd700; font-weight: bold;">👑 {champ}</span>
                    <span style="color: #34c759; font-weight: bold;">{score:,.2f} FP</span>
                </div>
                <div class="banner-detail">
                    <span style="color: #999;">Prize</span>
                    <span style="color: #ffd700; font-weight: bold;">${prize:,.2f}</span>
                </div>
                <div class="banner-detail">
                    <span style="color: #999;">Roster</span>
                    <span style="color: #ccc; font-size: 12px;">{roster_names}</span>
                </div>
                <div class="banner-detail">
                    <span style="color: #999;">Date</span>
                    <span style="color: #999;">{created_at}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_awards:
    st.markdown("## 🎖️ Season Awards")

    awards = data.get("awards") or {}
    mvp = awards.get("mvp") or {}
    dpoy = awards.get("dpoy") or {}
    gm = awards.get("gm_of_the_year") or {}
    clutch_aw = awards.get("clutch_award") or {}
    sharp = awards.get("sharp") or {}
    money = awards.get("money_maker") or {}
    volume = awards.get("volume_grinder") or {}

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🏆 MVP")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Most Valuable Player</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Highest average tournament score (3+ samples)</div>
                <div class="award-winner">{mvp.get('winner') or 'TBD'} ({float(mvp.get('average_score', 0.0) or 0.0):.2f} avg)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 🛡️ DPOY")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Defensive Player of the Year</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Highest steals+blocks fantasy points across tournaments</div>
                <div class="award-winner">{dpoy.get('winner') or 'TBD'} ({float(dpoy.get('defensive_fp', 0.0) or 0.0):.2f} defensive FP)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 💰 Money Maker")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Most Profitable</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Highest lifetime tournament earnings</div>
                <div class="award-winner">{money.get('winner') or 'TBD'} (${float(money.get('earnings', 0.0) or 0.0):,.2f})</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("### 📋 GM of the Year")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Best Roster Builder</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Best salary efficiency (avg score, 3+ entries)</div>
                <div class="award-winner">{gm.get('winner') or 'TBD'} ({float(gm.get('avg_score', 0.0) or 0.0):.2f} avg)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 🔥 Clutch Award")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Clutch Performer</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Most wins by less than 3 FP margin</div>
                <div class="award-winner">{clutch_aw.get('winner') or 'TBD'} ({int(clutch_aw.get('clutch_wins', 0) or 0)} clutch wins)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 🎯 Sharp")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Sharpest Player</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Best win rate with at least 5 entries</div>
                <div class="award-winner">{sharp.get('winner') or 'TBD'} ({float(sharp.get('win_rate', 0.0) or 0.0) * 100:.1f}%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 🏃 Volume Grinder")
        st.markdown(
            f"""
            <div class="award-card">
                <div class="award-name">Most Active Competitor</div>
                <div style="color: #999; font-size: 12px; margin-top: 8px;">Most tournament entries completed</div>
                <div class="award-winner">{volume.get('winner') or 'TBD'} ({int(volume.get('entries', 0) or 0)} entries)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_records:
    st.markdown("## 🏅 All-Time Records")
    records = data.get("records") or {}

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Scoring Records")
        st.markdown(
            """
            <div class="record-row" style="background: #1a1a2e; font-weight: bold; border-bottom: 2px solid #34c759;">
                <div>Rank</div>
                <div>Achievement</div>
                <div>Holder</div>
                <div>Value</div>
                <div>Samples</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for idx, row in enumerate(records.get("scoring", []), start=1):
            samples = int(row.get("sample_size", 0) or 0)
            sample_text = str(samples) if samples > 0 else "-"
            st.markdown(
                f"""
                <div class="record-row">
                    <div style="text-align: center; font-weight: bold;">#{idx}</div>
                    <div>{row.get('name', '-')}</div>
                    <div>{row.get('holder', '-')}</div>
                    <div class="record-value">{float(row.get('value', 0.0) or 0.0):,.2f}</div>
                    <div>{sample_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown("### Gameplay Records")
        st.markdown(
            """
            <div class="record-row" style="background: #1a1a2e; font-weight: bold; border-bottom: 2px solid #34c759;">
                <div>Rank</div>
                <div>Achievement</div>
                <div>Holder</div>
                <div>Value</div>
                <div>Samples</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for idx, row in enumerate(records.get("gameplay", []), start=1):
            name = str(row.get("name", ""))
            raw_value = row.get("value", 0)
            if "Win %" in name:
                val_text = f"{float(raw_value or 0.0) * 100:.1f}%"
            elif "Winnings" in name:
                val_text = f"${float(raw_value or 0.0):,.2f}"
            elif "ROI" in name:
                val_text = f"{float(raw_value or 0.0) * 100:.1f}%"
            else:
                val_text = f"{int(raw_value or 0):,}"
            samples = int(row.get("sample_size", 0) or 0)
            sample_text = str(samples) if samples > 0 else "-"
            st.markdown(
                f"""
                <div class="record-row">
                    <div style="text-align: center; font-weight: bold;">#{idx}</div>
                    <div>{name}</div>
                    <div>{row.get('holder', '-')}</div>
                    <div class="record-value">{val_text}</div>
                    <div>{sample_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tab_badge_leaders:
    st.markdown("## 🌟 Badge Leaders (Top Badge Collectors)")

    st.markdown(
        """
        <div class="record-row" style="background: #1a1a2e; font-weight: bold; border-bottom: 2px solid #34c759;">
            <div>Rank</div>
            <div>Player</div>
            <div>Badges</div>
            <div>Milestone</div>
            <div>Last Badge</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    leaders = data.get("badge_leaders") or []
    if not leaders:
        st.info("No badge data yet. Badge grants in awards_log will automatically populate this table.")

    for row in leaders:
        st.markdown(
            f"""
            <div class="record-row">
                <div class="record-rank">#{int(row.get('rank', 0) or 0)}</div>
                <div>{row.get('display_name', row.get('user_email', '-'))}</div>
                <div style="font-weight: bold; color: #ffd700;">{int(row.get('badge_count', 0) or 0)} 🎖️</div>
                <div style="color: #34c759;">{row.get('milestone', '-')}</div>
                <div style="color: #999;">{row.get('last_badge_at', '-')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_hof:
    st.markdown("## 🏛️ Hall of Fame")
    st.markdown(
        """
        Inducted after meeting **all** thresholds:
        **2,000+ LP** · **5+ Championship wins** · **50+ lifetime wins**
        """
    )

    hof_rows = data.get("hof") or []
    if not hof_rows:
        st.info("No Hall of Fame members yet. Players are inducted when they reach 2,000+ LP, 5+ Championships, and 50+ wins.")

    for row in hof_rows:
        champ_wins = int(row.get("championship_wins", 0) or 0)
        st.markdown(
            f"""
            <div class="hof-card">
                <h3 style="margin: 0; color: #ffd700;">🏛️ {row.get('display_name', row.get('user_email', '-'))}</h3>
                <div class="hof-stat">
                    <span>Lifetime Wins</span>
                    <span style="color: #34c759; font-weight: bold;">{int(row.get('lifetime_wins', 0) or 0):,}</span>
                </div>
                <div class="hof-stat">
                    <span>Championship Wins</span>
                    <span style="color: #ffd700; font-weight: bold;">{champ_wins:,} 🏆</span>
                </div>
                <div class="hof-stat">
                    <span>Career LP</span>
                    <span style="color: #34c759; font-weight: bold;">{int(row.get('lifetime_lp', 0) or 0):,}</span>
                </div>
                <div class="hof-stat">
                    <span>Total Winnings</span>
                    <span style="color: #ffd700; font-weight: bold;">${float(row.get('lifetime_earnings', 0.0) or 0.0):,.2f}</span>
                </div>
                <div class="hof-stat">
                    <span>Win Rate</span>
                    <span style="color: #34c759; font-weight: bold;">{float(row.get('win_rate', 0.0) or 0.0) * 100:.1f}%</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Profile", use_container_width=True):
        st.switch_page("pages/19_🏆_My_Profile.py")

with col2:
    st.markdown("")

with col3:
    if st.button("🏟️ Back to Lobby →", use_container_width=True):
        st.switch_page("pages/16_🏟️_Tournament_Lobby.py")
