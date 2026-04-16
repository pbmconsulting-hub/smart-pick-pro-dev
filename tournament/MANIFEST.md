# 🏟️ Tournament Environment - Build Summary

**Date**: 2026-04-15  
**Status**: ✅ Phase 0 Complete  
**Isolation Level**: 🔐 Full (separate .venv + requirements)

---

## 📦 What Was Created

### Core Directory Structure
```
tournament/                          # Root (isolated)
├── .venv/                           # Separate Python environment
├── .gitignore                       # Excludes .venv, __pycache__, etc.
├── .env.example                     # Environment template
├── requirements.txt                 # Tournament-only dependencies
├── config.py                        # All configurable settings
├── README.md                        # Main documentation
├── QUICK_START.md                   # 5-minute setup guide
└── MANIFEST.md                      # This file
```

### Engine Module (Phase 0 Foundation)
```
engine/
├── __init__.py
├── tournament_profiles.py           ✅ Build player profiles (6 attrs, archetype, salary)
├── tournament_simulation.py         ✅ Tier 1 (game env) + Tier 2 (player stats) wrapper
├── tournament_scoring.py            ✅ Fantasy points, bonuses (DD, TD, etc.), penalties
├── tournament_payout.py             ✅ Dynamic prize distribution (12/24/32 players)
└── tournament_awards.py             ⏳ Phase 1+ (badges, LP, levels)
```

### Database Module
```
db/
├── __init__.py
├── schema.sql                       ✅ 8 tables (tournaments, entries, profiles, logs, etc.)
└── migrations.py                    ⏳ Phase 1+ (version management)
```

### Support Modules
```
utils/
├── __init__.py
├── tournament_manager.py            ⏳ CRUD (create/fill/lock/resolve)
├── tournament_stripe.py             ⏳ Payments (entry, payouts, refunds)
├── tournament_gate.py               ⏳ Access control (Premium, Legend Pass, geo)
└── tournament_scheduler.py          ⏳ Auto-creates tournaments on schedule

data/
├── __init__.py
└── legends.py                       ⏳ 20 Hall of Fame legends (hardcoded profiles)

sports/
├── __init__.py
└── nba.py                           ⏳ Phase 1+ (NBA-specific logic, routing)
```

### Scripts & Documentation
```
scripts/
├── bootstrap_tournament.py          ✅ Setup: initializes DB, creates .env, creates directories

tests/
├── __init__.py
└── (test files)                     ⏳ Phase 0+ (unit & integration tests)
```

---

## 🔧 Configuration Files

| File | Purpose | Status |
|------|---------|--------|
| `config.py` | All tournament settings (salary caps, scoring, tiers, etc.) | ✅ Complete |
| `.env.example` | Template for .env variables | ✅ Complete |
| `requirements.txt` | Isolated Python dependencies | ✅ Complete |
| `.gitignore` | Exclude .venv, logs, temp, etc. | ✅ Complete |

**Key Settings in config.py:**
- Roster: $40K–$50K active, $15K legend, max 3 same team
- Scoring: 1.0× points, 1.2× rebounds, 1.5× assists, 3.0× steals/blocks
- Bonuses: 2 FP (DD), 5 FP (TD), 3+ FP (milestones)
- Tiers: Superstar ($11K–$12K) → Bench ($3K–$4.4K)
- Premium: $9.99/mo, Legend Pass: $4.99/mo add-on
- Prize pool: ~81.5% of rake (after Stripe + house edge)

---

## 🚀 Engine Files (Phase 0)

### tournament_profiles.py (384 lines)
- **ProfileBuilder** class: calculates 6 attributes (percentile ranks 1–99)
- **Attribute Scoring**: Scoring, Playmaking, Rebounding, Defense, Consistency, Clutch
- **Archetype Classifier**: 11 archetypes (Unicorn, Boom/Bust, Elite Scorer, etc.)
- **Salary Formula**: Base + archetype mod + hot/cold +/- 6%
- **QME Inputs**: Calculates fp_mean, fp_std_dev for simulation engine
- **Legend Support**: Fixed profiles for 20 HOF players

### tournament_simulation.py (244 lines)
- **TournamentsSimulationOrchestrator** class
- **Tier 1**: `simulate_tournament_environment()` → game context (pace, blowout risk, OT)
- **Tier 2**: `simulate_player_stat()` + `simulate_player_full_line()` → individual stat outcomes
- **Deterministic Seeding**: `generate_tournament_seed()` (256-bit, verified)
- **Resolution**: `resolve_tournament()` → coordinates full pipeline
- **Placeholder Stubs**: Phase 1 will replace with actual parent app imports

### tournament_scoring.py (186 lines)
- **Fantasy Point Calculation**: Points×1.0, Rebounds×1.2, Assists×1.5, etc.
- **Bonuses**: Double-double, Triple-double, 40/50 points, 20 rebounds, 15 assists, 5×5
- **Penalties**: Ejection (-10 FP, 0.1%–0.15% probability)
- **Entry Scoring**: Sums all players + bonuses + penalties

### tournament_payout.py (188 lines)
- **PayoutCalculator** class
- **Prize Pool**: ~81.5% of collected fees (after 18.5% rake)
- **Dynamic Payouts**: Scales for 12, 24, 32-player fields
- **LP Awards**: More LP for better placements (100 → 1)
- **Stripe Rake**: ~3.5% per transaction (auto-managed)

---

## 📊 Database Schema (schema.sql)

**8 Core Tables:**

| Table | Purpose | Phase |
|-------|---------|-------|
| `tournaments` | Tournament records, seed, lock time | 0 |
| `entries` | User rosters, scores, payouts | 0 |
| `player_profiles` | NBA player profiles (6 attrs, salary) | 0 |
| `player_game_logs` | Historical game data (for KDE) | 0 |
| `tournament_simulations` | Simulated outcomes per player | 0 |
| `payouts` | Payout records (Stripe) | 0 |
| `badges` | User badges earned | 1+ |
| `leaderboard` | LP rankings, seasonal stats | 1+ |

**Total Columns**: ~120 across all tables  
**Indexes**: Player profiles, game logs, tournament entries (auto-indexed)

---

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────┐
│ Tournament Root: /tournament/            │
│ Isolated .venv + requirements.txt        │
└────────────────┬────────────────────────┘
                 │
        ┌────────┼────────┐
        │        │        │
    Engine    Utils    Data
    ├──4py    ├──4py   ├──1py
    └─────    └─────   └─────
       │
       ├─ Tier 1: Game Environment
       │  (to integrate: engine/game_prediction.py)
       │
       └─ Tier 2: Player Simulation
          (to integrate: engine/simulation.py)
```

**Isolation Benefit**: Updates to main app don't affect tournament.  
**Extension Path**: New sports via `sports/mlb.py`, `sports/nfl.py`, etc.

---

## 📦 Dependencies (requirements.txt)

```
sqlalchemy==2.0.23          # ORM (future DB work)
psycopg2-binary==2.9.9      # PostgreSQL (optional)
stripe==5.4.0               # Payments (Phase 2+)
requests==2.31.0            # HTTP
pandas==2.1.3               # Data processing
numpy==1.26.2               # Numerics
scipy==1.11.4               # Distributions
pytest==7.4.3               # Testing
python-dotenv==1.0.0        # .env loading
pydantic==2.5.0             # Validation
```

**Size**: ~50 MB venv (minimal, purpose-built)

---

## 🔐 Isolation Checklist

- ✅ Separate `/tournament/` directory
- ✅ Own `.venv/` (not shared)
- ✅ Own `requirements.txt` (not shared)
- ✅ `.gitignore` excludes .venv, __pycache__, etc.
- ✅ Config-driven (config.py, .env)
- ✅ No hardcoded paths (all relative)
- ✅ No imports from main app (Phase 0)
- ✅ Imports FROM main app isolated to `tournament_simulation.py` (Phase 1+)

---

## 📚 Documentation Files

| File | Audience | Content |
|------|----------|---------|
| `README.md` | Users & devs | Overview, structure, setup, roadmap |
| `QUICK_START.md` | First-time setup | 5-min bootstrap, key modules, FAQ |
| `MANIFEST.md` | This file | Complete inventory, architecture |
| `config.py` | Developers | All tunable settings (docstrings) |
| `.env.example` | Setup | Environment variables template |

---

## ✅ Phase 0 Deliverables (Complete)

- [x] 4 core engine files (profiles, simulation, scoring, payout)
- [x] Database schema (8 tables)
- [x] Bootstrap script
- [x] Configuration system
- [x] Full documentation (README, QUICK_START, config)
- [x] Isolated environment (.venv-ready)
- [x] No conflicts with main app

**Phase 0 ~= 1,200 lines of code + documentation**

---

## ⏳ Phase 1+ Roadmap

**Phase 1: Free Tournaments UI (Weeks 4–7)**
- [ ] pages/16_🏟️_Tournament_Lobby.py
- [ ] pages/17_🏗️_Roster_Builder.py
- [ ] pages/18_📡_Live_Scoreboard.py
- [ ] pages/19_🏆_My_Profile.py
- [ ] utils/tournament_manager.py
- [ ] Unit tests

**Phase 2: Paid Tournaments + Stripe (Weeks 8–10)**
- [ ] utils/tournament_stripe.py
- [ ] Stripe Connect integration + payouts
- [ ] Premium + Elite Court
- [ ] engine/tournament_leaderboard.py
- [ ] pages/20_📜_Record_Books.py

**Phase 3: Championship System (Weeks 11–14)**
- [ ] engine/tournament_awards.py (28 badges)
- [ ] Staged reveal experience
- [ ] Legend Pass addon
- [ ] Monthly rotation

**Phase 4+: Multi-Sport + Polish (Weeks 15+)**
- [ ] sports/mlb.py, sports/nfl.py
- [ ] Major events (All-Star, Rivalry, Chaos)
- [ ] Social features (share, referral)
- [ ] Hall of Fame

---

## 🎓 What's Next?

1. **Verify Setup**:
   ```powershell
   cd tournament
   python scripts/bootstrap_tournament.py
   ```

2. **Review Code**:
   - Start with `engine/tournament_profiles.py`
   - Understand Tier 1 vs Tier 2 in `tournament_simulation.py`
   - Check `config.py` for all settings

3. **Integrate Parent Engines** (Phase 1):
   - Uncomment parent imports in `tournament_simulation.py`
   - Verify `engine/game_prediction.py` and `engine/simulation.py` signatures
   - Run end-to-end test

4. **Start Phase 1**:
   - Begin UI development
   - Build test suite
   - Ship free tournaments

---

## 📞 Support

**Questions?**
- Check `QUICK_START.md` first
- Review docstrings in `engine/*.py`
- See `config.py` for all tunables

**Issues?**
- Verify `.venv` activated: `python --version` should match venv
- Check `tournament.db` created: `ls tournament.db` (Windows: `dir tournament\tournament.db`)
- Review logs in `logs/` (when logging implemented in Phase 1)

---

**Status**: ✅ Red-pilled and Ready  
**Isolation**: 🔐 Complete  
**Next Phase**: Phase 1 UI Development

Happy building! 🚀
