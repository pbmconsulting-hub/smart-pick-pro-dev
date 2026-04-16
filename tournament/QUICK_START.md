/**
Phase 0 Quick Start Guide

Isolated Tournament Environment for Smart Pick Pro
*/

## 🎯 What You Have

Your tournament/ folder is now a **self-contained, isolated environment** that:
✅ Has its own .venv (no conflicts with main app)
✅ Has its own requirements.txt
✅ Contains Phase 0 foundation files (profiles, simulation, scoring, payout)
✅ Is ready for integration with parent app's engines

---

## 🚀 Setup (5 minutes)

### Step 1: Create Virtual Environment

```powershell
cd tournament
python -m venv .venv
.\.venv\Scripts\activate
```

On macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Initialize Database

```powershell
python scripts/bootstrap_tournament.py
```

Expected output:
```
🚀 Bootstrapping Tournament System...
   📝 Creating .env from .env.example...
   ✅ Created .\.env
   📦 Initializing database...
   ✅ Database initialized at C:\...\tournament\tournament.db

✅ Tournament environment ready!
```

### Step 4: Verify Setup

```powershell
python -c "from engine.tournament_profiles import ProfileBuilder; print('✅ Imports working')"
```

---

## 📁 File Structure

```
tournament/
├── .venv/                       # Isolated Python env
├── engine/
│   ├── tournament_profiles.py   ✅ Player profiles, attributes, salary
│   ├── tournament_simulation.py ✅ Two-tier wrapper (Engine A + B)
│   ├── tournament_scoring.py    ✅ Fantasy points, bonuses, penalties
│   ├── tournament_payout.py     ✅ Dynamic prize distribution
│   └── tournament_awards.py     ⏳ Phase 1+
├── db/
│   ├── schema.sql               ✅ All 8 tables defined
│   └── migrations.py            ⏳ Phase 1+
├── config.py                    ✅ All tournament settings
├── config.example               ✅ Template
└── scripts/
    └── bootstrap_tournament.py  ✅ Setup script
```

---

## 🔧 Key Python Modules

### engine/tournament_profiles.py
- `ProfileBuilder` — Build player profiles from stats
- `PlayerProfile` — Data class for one player
- `Archetype` enum — 11 player archetypes
- `RarityTier` enum — 6 salary tiers

**Usage:**
```python
from engine.tournament_profiles import ProfileBuilder

all_players = [...]  # List of player dicts with season stats
builder = ProfileBuilder(all_players)

profile = builder.build_profile(player_stats)
print(f"{profile.player_name}: {profile.overall_rating} OVR")
print(f"  Archetype: {profile.archetype}")
print(f"  Salary: ${profile.salary:,}")
```

### engine/tournament_simulation.py
- `TournamentsSimulationOrchestrator` — Master simulation coordinator
- `GameEnvironment` — Tournament game conditions

**Usage:**
```python
from engine.tournament_simulation import TournamentsSimulationOrchestrator

orch = TournamentsSimulationOrchestrator()

# Generate seed (after lock)
raw_seed, seed_int = orch.generate_tournament_seed()

# Simulate environment (Tier 1)
env = orch.simulate_tournament_environment(seed_int)
print(f"Environment: {env.environment_label}")

# Simulate player (Tier 2)
stat_line = orch.simulate_player_full_line(profile, env, seed_int)
print(f"Points: {stat_line['points']}")
```

### engine/tournament_scoring.py
- `calculate_fantasy_points()` — Base FP from stats
- `check_bonuses()` — Award bonuses (DD, TD, high totals)
- `check_penalties()` — Assess penalties (ejection)
- `calculate_entry_score()` — Total score for one entry

### engine/tournament_payout.py
- `PayoutCalculator` — Dynamic prize distribution
- Scales 12 → 24 → 32 players
- Stripe rake + house edge built in

---

## 🔗 Integration with Parent App (Phase 1+)

When ready, tournament will import from parent:

```python
# From parent: engine/game_prediction.py
from engine.game_prediction import _simulate_single_game

# From parent: engine/simulation.py
from engine.simulation import run_quantum_matrix_simulation

# From parent: data/data_manager.py
from data.data_manager import load_players_data
```

**Setup:**
1. Ensure parent app root is reachable (add to PYTHONPATH or use relative imports)
2. Set `PARENT_APP_ROOT` in `.env` or config.py
3. Uncomment engine calls in `tournament_simulation.py`

---

## 🧪 Testing

Run unit tests (when available):
```powershell
pytest tests/ -v --cov=engine
```

Manual tests (scripting):
```python
from engine.tournament_profiles import ProfileBuilder

builder = ProfileBuilder([])
profile = builder.build_profile({"player_id": 1, "name": "LeBron", "team": "LAL", ...})
print(profile)
```

---

## 📝 What's NOT Yet Implemented (Phase 1+)

- ⏳ UI pages (Streamlit)
- ⏳ Stripe integration (entry fees, payouts)
- ⏳ User authentication
- ⏳ Live scoreboard
- ⏳ Badge system
- ⏳ LP leaderboard
- ⏳ Multi-sport routing

---

## 🎓 Architecture Principles

1. **Isolated**: Own .venv, own deps. No main app conflicts.
2. **Modular**: Sports-agnostic. NBA → MLB/NFL/MLS easily.
3. **Wrapper-based**: Calls parent engines, no reimplementation.
4. **Deterministic**: Same seed = same outcomes (verifiable fairness).
5. **Scalable**: Payouts scale 12 → 24 → 32 players.

---

## ❓ FAQ

**Q: Will this conflict with my main Smart Pick Pro app?**
A: No. It has its own .venv and requirements.txt. Complete isolation.

**Q: How do I reactivate the venv later?**
A: 
```powershell
cd tournament
.\.venv\Scripts\activate
```

**Q: When do I integrate with parent app engines?**
A: Phase 1+. For now, Phase 0 is standalone with placeholder logic.

**Q: How do I add more sports?**
A: Create `tournament/sports/mlb.py`, `tournament/sports/nfl.py`, etc. Main engine is agnostic.

**Q: What's the database?**
A: SQLite by default (tournament.db). Can swap to PostgreSQL in .env.

---

## 🚀 Next Steps

1. ✅ Verify bootstrap runs without errors
2. ✅ Read through engine/ files to understand the pipeline
3. ✅ Review config.py to see all customizable settings
4. ⏳ Phase 1: Begin UI development (pages/16_🏟️_Tournament_Lobby.py)
5. ⏳ Phase 2: Stripe integration for payments
6. ⏳ Phase 3: Championship system + badges + LP

**Ready to start Phase 1? See PHASE_0_CHECKLIST.md for handoff criteria.**

---

Last Updated: 2026-04-15
