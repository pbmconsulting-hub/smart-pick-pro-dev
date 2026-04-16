# 🏟️ Tournament Mode - Quick Reference Card

## 🎮 User Guide

### Start Tournament Mode
```
1. Open Smart Pick Pro
2. Sidebar → Click "🏟️ ENTER TOURNAMENT MODE"
3. ✨ Auto-redirects to Tournament Lobby
```

### Tournament Lobby (Page 16)
```
🎮 Tonight............Tournaments available today
📅 Upcoming...........Next week's schedule
📜 Results............Your tournament history
🏆 Leaderboard........Season standings
🎙️ Joseph's Desk.....Expert picks & commentary
```

### Build Entry (Page 17)
```
💰 Salary Dashboard...Active ($50K) + Legend ($15K)
🎯 Player Grid.......Filter by position/team/price
🔒 Ownership Caps....33% active, 25% legends
⚡ Legends............Hall of Fame (Premium+Pass)
```

### Live Tracking (Page 18)
```
🎬 Live Games.........Real-time scores
📊 Your Entries......Active entries with FP tracking
🏅 Leaderboard.......Tournament standings
📝 Joseph............Live analysis
```

### Your Stats (Page 19)
```
👤 Overview...........Bio, tier, season highlights
🏆 Trophy Case........Badges earned + achievements
📜 History............Past tournament results
🤝 Head-to-Head......Vs specific players
🎯 Best Rosters......Top lineups analysis
📈 Progression........Rank trajectory
```

### Records & Hall of Fame (Page 20)
```
🏆 Championships.....Past winners
🎖️ Season Awards.....MVP, Breakthrough, etc.
🏅 All-Time Records..Highest scores, most wins
🌟 Badge Leaders.....Achievement rankings
🏛️ Hall of Fame.....Legendary players
```

### Exit Tournament Mode
```
Sidebar → Click "← EXIT TO NBA APP"
Return to main NBA app
```

---

## 🛠️ Developer Guide

### Import Tournament Mode Functions
```python
from tournament.utils.tournament_mode import (
    initialize_tournament_mode,
    is_tournament_mode_active,
    toggle_tournament_mode,
    render_tournament_toggle
)
```

### Check If User Is In Tournament Mode
```python
if is_tournament_mode_active():
    # Show tournament UI
    pass
else:
    # Show NBA app UI
    pass
```

### Add Tournament Toggle to Any Page
```python
with st.sidebar:
    render_tournament_toggle()
```

### Toggle Mode Programmatically
```python
if st.button("Switch to Tournament"):
    toggle_tournament_mode()
    st.rerun()
```

---

## 📊 Session State Keys

```python
st.session_state["tournament_mode_enabled"]   # bool: Is tournament on?
st.session_state["user_id"]                   # str: Current user
st.session_state["user_tier"]                 # str: free/premium/elite
st.session_state["has_legend_pass"]          # bool: Legend Pass active?
st.session_state["selected_tournament"]      # int: Tournament ID
```

---

## 🚀 Page Navigation

From Tournament Lobby (Page 16):
```
→ Page 17 (Roster Builder) - Build lineups
→ Page 18 (Live Scoreboard) - Track live scores
→ Page 19 (My Profile) - View your stats
→ Page 20 (Record Books) - See all-time records
```

All pages can navigate to any other page via buttons.

---

## 🔒 Access Control

### Free Tier
- ✅ Open Court tournaments ($0)
- ❌ Pro Court tournaments
- ❌ Elite Court tournaments
- ❌ Legends (need Legend Pass add-on)

### Premium Tier
- ✅ Open Court tournaments
- ✅ Pro Court tournaments
- ✅ Elite Court tournaments
- ❌ Legends (need $4.99/mo Legend Pass)

### Premium + Legend Pass
- ✅ All courts
- ✅ All legends
- ✅ Championship access

---

## 💾 Isolated Data

Tournament mode uses **separate** systems:

```
NBA App                    Tournament
─────────────────────────────────────
users.db                   tournament.db
/data/nba_live_fetcher.py  /data/legends.py
/engine/predictions.py     /engine/tournament_simulation.py
/pages/0_Home.py           /pages/tournament/16_Lobby.py
```

**No data conflicts.** Each system is independent.

---

## 🎯 Entry Fee Payment

| Court | Entry Fee | Players | Prize Pool |
|-------|-----------|---------|-----------|
| Open | $0 | 100 max | $0 |
| Pro | $5 | 24 max | $80 |
| Elite | $25 | 12 max | $200 |

(Prices are examples - configured in `tournament/config.py`)

---

## 🏆 Prize Distribution

Example 24-player Pro Court tournament:
```
Entry Fees:        24 × $5 = $120
House Edge:        18.5% rake = $22.20
Prize Pool:        81.5% = $97.80

Payout Structure:
  1st Place (top 10%):    $24.45 (25% of pool)
  2nd Place (top 20%):    $14.67 (15% of pool)
  3rd Place (top 50%):     $9.78 (10% of pool)
  4-10 Place (top 50%):    $4.89 each
  LP (all entries):        35 LP per entry
```

Updated in `tournament/engine/tournament_payout.py`

---

## 🧪 Testing Tournament Mode

**Test Entry Flow:**

```python
# 1. User clicks "ENTER TOURNAMENT MODE"
st.session_state["tournament_mode_enabled"] = True
st.rerun()  # Redirects to page 16

# 2. User selects tournament from list
st.session_state["selected_tournament"] = 1
st.switch_page("pages/tournament/17_🏗️_Roster_Builder.py")

# 3. User builds roster and clicks "Lock & Submit"
# Calls tournament_manager.add_entry(tournament_id, user_id, roster)

# 4. User checks Live Scoreboard
st.switch_page("pages/tournament/18_📡_Live_Scoreboard.py")

# 5. User returns to NBA app
st.session_state["tournament_mode_enabled"] = False
st.switch_page("Smart_Picks_Pro_Home.py")
```

---

## 📞 Common Issues

| Issue | Solution |
|-------|----------|
| "Tournament mode disabled" warning | Click sidebar toggle to enable |
| Pages won't load | Check `tournament/` folder exists |
| Session state resets | Use `load_page_state()` to persist |
| Salary cap not enforcing | Check `ROSTER_CONFIG` in config.py |
| Ownership locked | 33% active / 25% legends hit limit |

---

## ✅ Checklist: Verify Setup

- [ ] Smart_Picks_Pro_Home.py has tournament toggle in sidebar
- [ ] Pages `/tournament/` directory exists
- [ ] `tournament/utils/tournament_mode.py` exists
- [ ] `tournament/config.py` has ROSTER_CONFIG
- [ ] `tournament/data/legends.py` has 20 legends
- [ ] Running `streamlit run Smart_Picks_Pro_Home.py` works
- [ ] Sidebar shows "🏟️ ENTER TOURNAMENT MODE" button
- [ ] Clicking button redirects to Tournament Lobby
- [ ] "← EXIT TO NBA APP" button returns to home

---

**Last Updated**: April 15, 2026
**Status**: ✅ Tournament integration complete
**Next Phase**: Unit tests or Stripe integration
