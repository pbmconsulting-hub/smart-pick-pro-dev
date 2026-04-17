# Tournament System — Development Plan

> **Generated**: April 15, 2026
> **Current State**: Phase 0 ✅ Complete | Phase 1e Tests ✅ 87/87 Passing (97% coverage)

---

## Status Summary

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 0** | Backend foundation (17 modules, ~4,000 LOC) | ✅ Complete |
| **Phase 1e** | Unit test suite (87 tests, 6 modules) | ✅ Complete |
| **Phase 1** | Integration tests + wire UI to real backends | 🔜 Next |
| **Phase 2** | Stripe payment flow + subscription management | Planned |
| **Phase 3** | Championship system, badges, LP leaderboard | Planned |
| **Phase 4** | Multi-sport expansion | 🚧 4A in progress |

---

## Phase 1: Integration & UI Wiring

### 1A — Integration Tests Against Real Backend (Priority: CRITICAL)

Current tests use **mock classes** in `tests/conftest.py`. Phase 1A writes integration tests that import and exercise the **real** tournament modules.

| # | Test File | Covers Module | Key Scenarios |
|---|-----------|---------------|---------------|
| 1 | `test_integration_database.py` | `database.py` | Initialize DB, upsert profiles, read/write tournaments, entries CRUD, connection cleanup |
| 2 | `test_integration_manager.py` | `manager.py` | Full lifecycle (create→open→add_entry→lock→resolve→cancel), auto-cancel underfilled, entry validation |
| 3 | `test_integration_scoring.py` | `scoring.py` | `score_player_total()` with real stat lines, bonus edge cases, penalty stacking |
| 4 | `test_integration_gate.py` | `gate.py` | `evaluate_tournament_access()` with all state/tier/age combos |
| 5 | `test_integration_payout.py` | `payout.py` + `payout_runner.py` | `compute_scaled_payouts()` for 12/24/32 fields, LP distribution, refund flow |
| 6 | `test_integration_simulation.py` | `simulation.py` | Seed generation, determinism, `simulate_tournament_environment()` (may need parent engine mocking) |
| 7 | `test_integration_profiles.py` | `profiles.py` | `build_player_profiles()` with real NBA stats, archetype classification, salary formula |
| 8 | `test_integration_events.py` | `events.py` + `notifications.py` | `log_event()`, `list_events()`, `send_notification()`, `list_user_notifications()` |
| 9 | `test_integration_scheduler.py` | `scheduler.py` + `jobs.py` | `create_weekly_schedule()`, `resolve_locked_tournaments()`, `run_tournament_jobs()` |
| 10 | `test_integration_exports.py` | `exports.py` | CSV export for entries, scores, events |

**Dependency**: These tests need `tournament/database.py` + SQLite. No Streamlit/pandas/numpy required. Should work with Python 3.12 directly.

**Estimated**: ~600-800 lines of test code, 50-70 new tests

---

### 1B — Wire Lobby Page to Real Backend (Priority: HIGH)

**File**: `pages/16_🏟️_Tournament_Lobby.py` (~400 lines, framework exists)

| Task | Description |
|------|-------------|
| Replace mock data | Swap hardcoded tournament lists with `database.py` queries |
| Wire entry flow | User clicks "Enter" → `gate.evaluate_tournament_access()` → `stripe.create_tournament_entry_checkout_session()` → `manager.create_entry()` |
| Live tournament status | Read `tournaments` table status field, show countdown to lock_time |
| Results tab | Query resolved tournaments + entries with placements/prizes |
| Leaderboard tab | Query `leaderboard` table for LP rankings |
| Joseph's Desk tab | Generate preview commentary from upcoming tournament data |

---

### 1C — Wire Roster Builder to Real Backend (Priority: HIGH)

**File**: `pages/17_🏗️_Roster_Builder.py` (framework exists)

| Task | Description |
|------|-------------|
| Player pool | Load real profiles from `player_profiles` table via `database.py` |
| Salary enforcement | Wire `ROSTER_CONFIG` salary_cap/floor validation to add/remove actions |
| Position slots | Enforce 8 active + 1 LEGEND slot structure |
| Team limits | Max 3 players from same team |
| Legend cards | Load from `data/legends.py` → `get_available_legends_for_month()` |
| Submit roster | Validate → `manager.add_entry()` → redirect to Lobby confirmation |

---

### 1D — Wire Remaining Pages (Priority: MEDIUM)

| Page | Key Integration |
|------|----------------|
| `18_📡_Live_Scoreboard.py` | Real-time score display from active tournament entries. Poll `tournament_simulations` table or use Streamlit auto-refresh. |
| `19_🏆_My_Profile.py` | User career stats, tournament history, badges from `entries` + `badges` + `leaderboard` tables. |
| `20_📜_Record_Books.py` | Historical leaderboard, season standings, tournament archive from DB. |

---

## Phase 2: Payments & Subscriptions

### 2A — Stripe Entry Flow (Priority: CRITICAL)

| Task | Description |
|------|-------------|
| Checkout session | `stripe.create_tournament_entry_checkout_session()` → redirect to Stripe hosted page |
| Webhook handler | Receive `checkout.session.completed` → confirm entry in DB |
| Refund flow | `stripe.create_tournament_refund()` for cancelled tournaments |
| Payout flow | `stripe.create_winner_payout_transfer()` via Stripe Connect |
| Test with Stripe CLI | Use `stripe listen --forward-to localhost:8501/webhook` for local testing |

### 2B — Subscription Management (Priority: HIGH)

| Task | Description |
|------|-------------|
| Premium tier ($9.99/mo) | Gate Pro/Elite court access behind Stripe subscription |
| Legend Pass ($4.99/mo) | Add-on subscription for LEGEND roster slot |
| Tier enforcement | Wire `gate.evaluate_tournament_access()` to check live subscription status |
| Downgrade handling | Remove access to paid courts on subscription cancellation |

### 2C — Stripe Connect Onboarding (Priority: HIGH)

| Task | Description |
|------|-------------|
| Winner onboarding | Create Stripe Connect accounts for winners to receive payouts |
| KYC/1099 compliance | Required for payouts > $600/year |
| Payout scheduling | Process payouts within 24 hours of tournament resolution |

---

## Phase 3: Championship & Rewards

### 3A — Badge System (Priority: MEDIUM)

| Badge | Criteria |
|-------|----------|
| First Win | Win any tournament |
| Triple Crown | Win Open/Pro/Elite in same month |
| 5x5 Club | Score a 5x5 bonus in tournament |
| Hot Streak | Win 3+ tournaments in a row |
| Legend Slayer | Beat a lineup with LEGEND using non-LEGEND roster |

### 3B — LP Leaderboard (Priority: MEDIUM)

| Task | Description |
|------|-------------|
| LP calculation | All placements earn LP (1st=50, 2nd=40, ... last=5) |
| Season tracking | Monthly/quarterly/annual LP standings |
| Tier rewards | Top 10% earn bonus prizes at season end |
| Leaderboard page | Wire `20_📜_Record_Books.py` to LP rankings |

### 3C — Championship Night (Priority: LOW)

| Task | Description |
|------|-------------|
| Qualification | Top LP earners qualify for monthly Championship |
| Enhanced payouts | `championship_night_payout()` in `payout.py` |
| Special badges | Championship winner exclusive badges |

---

## Phase 4: Multi-Sport Expansion

### 4A — Sport Router (Priority: LOW)

| Task | Description |
|------|-------------|
| `sports/nba.py` | ✅ NBA-specific scoring and stat mapping |
| `sports/mlb.py` | ✅ Initial MLB stat mapping + scoring adapter |
| `sports/nfl.py` | ✅ Initial NFL stat mapping + scoring adapter |
| Sport selector | ✅ Tournament creation + resolution route through the sport handler |

---

## Execution Order

```
Week 1:  Phase 1A — Integration tests (database, manager, scoring, gate)
Week 2:  Phase 1A — Integration tests (payout, simulation, profiles, events)
Week 3:  Phase 1B — Wire Lobby page to real DB
Week 4:  Phase 1C — Wire Roster Builder to real DB
Week 5:  Phase 1D — Wire remaining pages (Scoreboard, Profile, Records)
Week 6:  Phase 2A — Stripe entry + webhook flow
Week 7:  Phase 2B — Subscription management
Week 8:  Phase 2C — Stripe Connect for payouts
Week 9:  Phase 3A — Badge system
Week 10: Phase 3B — LP leaderboard
Week 11: Phase 3C — Championship Night
Week 12: Phase 4A — Multi-sport router (NBA → MLB)
```

---

## Technical Debt to Address

| Item | Priority | Description |
|------|----------|-------------|
| Remove `__init__.py` rename workaround | HIGH | Tests currently require renaming `tournament/__init__.py` to `.bak` before running. Fix by cleaning up heavy imports in `__init__.py` or using lazy imports. |
| Evolve mocks → real imports | HIGH | Phase 1e tests use mock classes. Phase 1A integration tests should import real modules. Keep both suites. |
| `pytest.ini` warning | LOW | `python_paths` is not a valid pytest config key. Remove or replace with `pythonpath`. |
| Duplicate module structure | MEDIUM | Both `tournament/scoring.py` and `tournament/engine/tournament_scoring.py` exist. Clarify which is canonical. Same for manager, gate, profiles. |
| Parent engine integration | MEDIUM | `simulation.py` imports from parent `engine.game_prediction` and `engine.simulation`. Needs graceful fallback or mock when parent unavailable. |

---

## File Inventory (17 backend modules + 5 UI pages)

### ✅ Real Implementations
| File | Lines | Description |
|------|-------|-------------|
| `config.py` | ~130 | All constants (salary, scoring, tiers, premium) |
| `database.py` | ~320 | 8-table SQLite layer |
| `manager.py` | ~400 | Tournament lifecycle CRUD |
| `profiles.py` | ~400 | Player profile builder |
| `scoring.py` | ~120 | Fantasy points + bonuses + penalties |
| `simulation.py` | ~280 | Two-tier simulation wrapper |
| `payout.py` | ~80 | Dynamic payout scaling |
| `payout_runner.py` | ~250 | Stripe payout orchestration |
| `events.py` | ~90 | Audit logging |
| `notifications.py` | ~60 | User notifications |
| `legends.py` | ~100 | 20 HOF legends |
| `gate.py` | ~150 | Geo-blocking + tier access |
| `jobs.py` | ~80 | Scheduled automation |
| `scheduler.py` | ~120 | Tournament scheduling |
| `stripe.py` | ~130 | Stripe integration |
| `exports.py` | ~150 | CSV exports |
| `bootstrap.py` | ~25 | Setup script |

### ⏳ UI Pages (Framework, needs DB wiring)
| File | Description |
|------|-------------|
| `pages/16_Tournament_Lobby.py` | Tonight / Upcoming / Results / Leaderboard / Joseph |
| `pages/17_Roster_Builder.py` | Salary cap builder + legends |
| `pages/18_Live_Scoreboard.py` | Real-time tournament tracking |
| `pages/19_My_Profile.py` | Career stats + badges |
| `pages/20_Record_Books.py` | Historical results |
