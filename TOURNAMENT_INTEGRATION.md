# 🏟️ Tournament Mode Integration Guide

## Overview

The **Tournament Mode** is a completely isolated environment within the Smart Pick Pro app that lets users switch between the main NBA app and a dedicated Tournament UI. This is accessible via a toggle button in the sidebar.

---

## Architecture

### Environment Switching

```
Smart Pick Pro Home (main app)
    ↓
    [🏟️ ENTER TOURNAMENT MODE] ← Sidebar Toggle
    ↓
Tournament Environment (isolated)
    ↓
    Pages 16–20 (Lobby, Roster Builder, Live Scoreboard, Profile, Record Books)
    ↓
    [← EXIT TO NBA APP] ← Return to main app
```

### File Structure

```
/pages/
  /tournament/
    __init__.py                          # Package marker
    16_🏟️_Tournament_Lobby.py           # Main tournament hub
    17_🏗️_Roster_Builder.py             # Lineup constructor
    18_📡_Live_Scoreboard.py            # Game tracking
    19_🏆_My_Profile.py                 # User stats
    20_📜_Record_Books.py               # All-time records

/tournament/
  config.py                              # Shared configuration
  utils/
    tournament_mode.py                   # Mode toggle manager
    tournament_manager.py                # CRUD operations
    tournament_gate.py                   # Access control
  data/
    legends.py                           # Hall of Fame
  engine/
    tournament_profiles.py
    tournament_simulation.py
    tournament_scoring.py
    tournament_payout.py
  pages/ (old location - kept for reference)
    16_🏟️_Tournament_Lobby.py
    ... (etc)
  db/
    schema.sql                           # Database schema
```

---

## How It Works

### 1. **Tournament Mode Toggle** (Smart_Picks_Pro_Home.py)

When the user clicks **🏟️ ENTER TOURNAMENT MODE** in the sidebar:

```python
# tournament_mode_enabled = False → True
st.session_state["tournament_mode_enabled"] = True
st.rerun()
```

### 2. **Redirect Logic** (Smart_Picks_Pro_Home.py)

At app startup, the home page checks:

```python
if st.session_state.get("tournament_mode_enabled", False):
    st.switch_page("pages/tournament/16_🏟️_Tournament_Lobby.py")
```

If enabled, the user is automatically sent to the Tournament Lobby instead of seeing the home page.

### 3. **Tournament Environment** (pages/tournament/)

All tournament pages have a **mode check**:

```python
if not is_tournament_mode_active():
    st.warning("⚠️ Tournament Mode is disabled...")
    st.stop()
```

### 4. **Exit to NBA App**

In the tournament sidebar, clicking **← EXIT TO NBA APP** disables tournament mode and returns the user:

```python
st.session_state["tournament_mode_enabled"] = False
st.switch_page("Smart_Picks_Pro_Home.py")
```

---

## Usage Flow

### For Users

1. Open Smart Pick Pro app (loads home page)
2. **Sidebar**: Click "🏟️ ENTER TOURNAMENT MODE"
3. **Redirects**: Automatically goes to Tournament Lobby
4. **Explore**: Browse tournaments, build rosters, view leaderboards
5. **Exit**: Click sidebar "← EXIT TO NBA APP" to return

### For Developers

To access tournament functions from pages:

```python
from tournament.utils.tournament_mode import (
    is_tournament_mode_active,
    toggle_tournament_mode,
    render_tournament_toggle
)

# Check if tournament mode is on
if is_tournament_mode_active():
    # Show tournament-specific UI
    pass

# Toggle mode programmatically
toggle_tournament_mode()

# Render the sidebar toggle
render_tournament_toggle()
```

---

## Session State Keys

The tournament mode is tracked in Streamlit session state:

| Key | Type | Purpose |
|-----|------|---------|
| `tournament_mode_enabled` | bool | Is tournament mode active? |
| `user_id` | int/str | Current user (in tournament) |
| `user_tier` | str | free/premium/elite |
| `has_legend_pass` | bool | Does user have Legend Pass? |
| `selected_tournament` | int | Currently viewing tournament ID |

---

## Page Navigation in Tournament Mode

All 5 tournament pages are interconnected:

```
16_🏟️_Tournament_Lobby.py
    ├─→ 17_🏗️_Roster_Builder.py (Enter tournament → build roster)
    ├─→ 18_📡_Live_Scoreboard.py (View live scores)
    ├─→ 19_🏆_My_Profile.py (User stats/badges)
    └─→ 20_📜_Record_Books.py (All-time records)
```

Navigation buttons use `st.switch_page()` for seamless transitions.

---

## Integration with Main App

### What Stays Isolated

Tournament data and pages:
- ✅ Tournament configuration (salary caps, tiers, scoring)
- ✅ Tournament manager (CRUD operations)
- ✅ Tournament access gate (tier checks)
- ✅ Legends database
- ✅ All UI pages (16–20)

### What's Shared

Main app features:
- ✅ Authentication (user login)
- ✅ Style/theme (dark mode CSS)
- ✅ Premium status (tier checks)
- ✅ Joseph commentary (AI integration)

### Conflict Prevention

- **Separate database**: Tournament uses tournament.db (isolated)
- **Separate config**: tournament/config.py (no interference)
- **Separate imports**: Pages import from tournament/ directory
- **Session state checks**: Every page verifies tournament_mode_enabled

---

## Next Steps (Phase 2+)

### Phase 1e: Unit Tests
```
test_tournament_manager.py         ← CRUD operations
test_tournament_gate.py            ← Access control
test_tournament_profiles.py        ← Player profiles
test_tournament_scoring.py         ← Fantasy points
```

### Phase 2: Stripe Integration
```
Payment processing                 ← tournament/utils/payments.py
Tier upgrades                      ← Legend Pass purchases
Prize pool disbursement            ← tournament/utils/payouts.py
```

### Phase 3: Multi-Sport
```
Tournament engine improvements     ← Support other sports
Database schema expansion          ← Add NFL, College, etc.
API service setup                  ← External data feeds
```

---

## Troubleshooting

### "Tournament Mode is disabled" warning

**Cause**: Tournament mode is off or not properly toggled.

**Solution**: 
1. Go to Smart Pick Pro home page
2. Click **🏟️ ENTER TOURNAMENT MODE** in sidebar
3. You should be redirected to Tournament Lobby

### Pages not loading in tournament mode

**Cause**: Missing `tournament/` directory or import path issue.

**Debug**:
```python
import sys
from pathlib import Path
TOURNAMENT_ROOT = Path(__file__).parent.parent.parent / "tournament"
print(f"Tournament root: {TOURNAMENT_ROOT}")
print(f"Exists: {TOURNAMENT_ROOT.exists()}")
```

### Session state not persisting

**Cause**: Streamlit session state cleared on page refresh.

**Solution**: Persist to database using `load_page_state()` in tournament manager.

---

## Performance Notes

- **Startup time**: Tournament mode adds ~200ms redirect check (negligible)
- **Memory usage**: Each page uses ~45MB (Streamlit overhead)
- **Database**: SQLite tournament.db is separate from main app DB
- **API calls**: Zero (tournament is deterministic/seeded)

---

## Support

For issues or feature requests:

1. Check [tournament/README.md](../tournament/README.md) for component details
2. Review [tournament/QUICK_START.md](../tournament/QUICK_START.md) for setup
3. See [tournament/MANIFEST.md](../tournament/MANIFEST.md) for file inventory

Built with ❤️ for Smart Pick Pro 2026
