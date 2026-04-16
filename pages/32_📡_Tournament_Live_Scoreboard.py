import json
import time

import streamlit as st

from tournament import get_tournament_scoreboard, list_tournaments

st.set_page_config(page_title="Tournament Live Scoreboard", page_icon="📡", layout="wide")
st.title("📡 Tournament Live Scoreboard (Standalone)")
st.caption("Reads only from the isolated tournament subsystem.")

with st.sidebar:
    st.subheader("Refresh")
    auto_refresh = st.checkbox("Auto refresh every 15s", value=False)
    if auto_refresh:
        st.caption("Refreshing...")
        time.sleep(15)
        st.rerun()

tournaments = list_tournaments(status=None)
if not tournaments:
    st.warning("No tournaments found yet.")
    st.stop()

ids = [t["tournament_id"] for t in tournaments]
default_tid = st.session_state.get("tournament_selected_id", ids[0])
if default_tid not in ids:
    default_tid = ids[0]

selected_tid = st.selectbox("Tournament", ids, index=ids.index(default_tid), format_func=lambda x: f"#{x}")
st.session_state["tournament_selected_id"] = selected_tid
selected = [t for t in tournaments if t["tournament_id"] == selected_tid][0]

st.subheader(f"#{selected['tournament_id']} {selected['tournament_name']}")
st.write(
    f"Tier: {selected['court_tier']} | Fee: ${selected['entry_fee']:.2f} | "
    f"Status: {selected['status']}"
)

if selected.get("environment_json"):
    env = json.loads(selected["environment_json"])
    st.info(
        f"Environment: {env.get('environment_label', 'n/a')} | "
        f"Spread {env.get('vegas_spread', 'n/a')} | Total {env.get('game_total', 'n/a')}"
    )

board = get_tournament_scoreboard(int(selected_tid))
if not board:
    st.info("No entries scored yet.")
else:
    top3 = board[:3]
    if top3:
        c1, c2, c3 = st.columns(3)
        slots = [c1, c2, c3]
        for idx, row in enumerate(top3):
            with slots[idx]:
                place = row.get("rank") or (idx + 1)
                st.metric(
                    f"#{place}",
                    row.get("display_name") or row.get("user_email"),
                    f"{float(row.get('total_score', 0.0)):.2f} FP",
                )

    st.dataframe(
        [
            {
                "rank": row.get("rank"),
                "name": row.get("display_name") or row.get("user_email"),
                "score": row.get("total_score"),
                "lp": row.get("lp_awarded"),
                "payout": row.get("payout_amount"),
            }
            for row in board
        ],
        use_container_width=True,
        hide_index=True,
    )
