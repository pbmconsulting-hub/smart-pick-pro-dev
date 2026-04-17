# 🏟️ Tournament System

**Isolated tournament environment for Smart Pick Pro.** Sports-agnostic design with active NBA, MLB, and NFL routing support.

## Structure

```
tournament/
├── .venv/                           # Isolated Python environment
├── engine/                          # Tournament simulation engines
│   ├── tournament_profiles.py       # Player attributes, salary formula
│   ├── tournament_simulation.py     # Tier 1 (game env) + Tier 2 (player stats)
│   ├── tournament_scoring.py        # Fantasy points, bonuses, penalties
│   ├── tournament_payout.py         # Prize distribution
│   └── tournament_awards.py         # Badge criteria (Phase 1)
├── utils/                           # Tournament utilities
├── data/                            # Data & legends
├── db/                              # Database schema & migrations
├── sports/                          # Sport-specific logic
│   ├── nba.py                       # NBA adapter
│   ├── mlb.py                       # MLB adapter
│   └── nfl.py                       # NFL adapter
├── tests/                           # Unit tests
└── scripts/                         # Bootstrap & setup scripts
```

## Quick Start

### 1. Create Isolated Environment

```bash
cd tournament
python -m venv .venv
.\.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Database

```bash
python scripts/bootstrap_tournament.py
```

## Design Principles

- **Isolated**: Own `.venv`, own `requirements.txt` — zero conflicts with main app
- **Modular**: Sports-agnostic. NBA, MLB, and NFL are currently routed through the same tournament engine
- **Wrapper-Based**: Calls parent app's `engine/simulation.py` and `engine/game_prediction.py` — no reimplementation
- **Deterministic**: Outcome seeding for fairness & verifiability
- **Stripe-Native**: Entry fees, payouts, 1099s handled directly

## Parent App Integration

Tournament imports from main app:
```python
# From parent: engine/game_prediction.py
from engine.game_prediction import _simulate_single_game

# From parent: engine/simulation.py
from engine.simulation import run_quantum_matrix_simulation

# From parent: data/data_manager.py
from data.data_manager import load_players_data
```

**Note**: Ensure main app is importable by adding parent to `PYTHONPATH`, or use relative imports carefully.

## Phase 0 Roadmap (Weeks 1–3)

- [ ] `tournament_profiles.py` — attribute calc, archetype, salary formula
- [ ] `tournament_simulation.py` — Tier 1 + Tier 2 wrappers
- [ ] `tournament_scoring.py` — FP formula + bonuses
- [ ] `tournament_payout.py` — dynamic prize distribution
- [ ] DB schema in `db/schema.sql`
- [ ] Unit tests
- [ ] Weekly profile updater

## Future Phases

- **Phase 1**: Streamlit UI (pages 16–19)
- **Phase 2**: Stripe integration, payouts, premium tiers
- **Phase 3**: Championship system, badges, LP rankings
- **Phase 4**: Expand beyond the current NBA/MLB/NFL router coverage

## Environment Variables

Create `.env` in `tournament/` root:

```env
DATABASE_URL=sqlite:///tournament.db
STRIPE_API_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
PARENT_APP_ROOT=../  # Relative path to main Smart Pick Pro
```

## Testing

```bash
pytest tests/ -v --cov=engine --cov=utils
```

## Notes

- All code assumes Python 3.10+
- Main app's engines must be stable before importing
- Deterministic seeding: outcomes are verifiable after tournament completes
- No real-time NBA API calls during simulation (uses pre-computed profiles)

---

**Next**: Review [Phase 0 Implementation Checklist](./PHASE_0_CHECKLIST.md)
