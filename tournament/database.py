"""Standalone tournament database layer.

Uses a dedicated SQLite file to keep tournament features isolated.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_DIRECTORY = Path(__file__).resolve().parent.parent / "db"
TOURNAMENT_DB_PATH = DB_DIRECTORY / "tournament.db"

CREATE_PLAYER_PROFILES_SQL = """
CREATE TABLE IF NOT EXISTS player_profiles (
    player_id TEXT PRIMARY KEY,
    player_name TEXT NOT NULL,
    team TEXT,
    position TEXT,
    overall_rating INTEGER DEFAULT 50,
    archetype TEXT DEFAULT 'Versatile',
    rarity_tier TEXT DEFAULT 'Bench',
    salary INTEGER DEFAULT 3000,
    profile_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_TOURNAMENTS_SQL = """
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_name TEXT NOT NULL,
    sport TEXT NOT NULL DEFAULT 'nba',
    court_tier TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    entry_fee REAL NOT NULL DEFAULT 0.0,
    max_entries INTEGER NOT NULL,
    min_entries INTEGER NOT NULL,
    lock_time TEXT NOT NULL,
    reveal_mode TEXT DEFAULT 'instant',
    payout_structure_json TEXT,
    raw_seed TEXT,
    seed_int INTEGER,
    environment_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT
);
"""

CREATE_USER_SUBSCRIPTION_STATUS_SQL = """
CREATE TABLE IF NOT EXISTS user_subscription_status (
    user_email TEXT PRIMARY KEY,
    premium_active INTEGER DEFAULT 0,
    legend_pass_active INTEGER DEFAULT 0,
    premium_expires_at TEXT,
    legend_pass_expires_at TEXT,
    source TEXT DEFAULT 'manual',
    raw_json TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_TOURNAMENT_ENTRIES_SQL = """
CREATE TABLE IF NOT EXISTS tournament_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,
    display_name TEXT,
    roster_json TEXT NOT NULL,
    total_score REAL DEFAULT 0.0,
    rank INTEGER,
    lp_awarded INTEGER DEFAULT 0,
    payout_amount REAL DEFAULT 0.0,
    stripe_payment_intent_id TEXT,
    stripe_refund_id TEXT,
    stripe_transfer_id TEXT,
    refund_status TEXT DEFAULT 'none',
    payout_status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (tournament_id, user_email),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE
);
"""

CREATE_SIMULATED_SCORES_SQL = """
CREATE TABLE IF NOT EXISTS simulated_scores (
    sim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT,
    line_json TEXT NOT NULL,
    fantasy_points REAL DEFAULT 0.0,
    bonuses_json TEXT,
    penalties_json TEXT,
    total_fp REAL DEFAULT 0.0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (tournament_id, player_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE
);
"""

CREATE_USER_CAREER_STATS_SQL = """
CREATE TABLE IF NOT EXISTS user_career_stats (
    user_email TEXT PRIMARY KEY,
    display_name TEXT,
    lifetime_entries INTEGER DEFAULT 0,
    lifetime_wins INTEGER DEFAULT 0,
    lifetime_top5 INTEGER DEFAULT 0,
    lifetime_earnings REAL DEFAULT 0.0,
    lifetime_lp INTEGER DEFAULT 0,
    career_level INTEGER DEFAULT 1,
    badges_json TEXT,
    stripe_connect_account_id TEXT,
    stripe_connect_onboarding_status TEXT DEFAULT 'not_started',
    stripe_connect_details_submitted INTEGER DEFAULT 0,
    stripe_connect_payouts_enabled INTEGER DEFAULT 0,
    stripe_connect_requirements_json TEXT,
    stripe_connect_kyc_verified INTEGER DEFAULT 0,
    stripe_connect_kyc_verified_at TEXT,
    stripe_connect_last_synced_at TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_CHAMPIONSHIP_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS championship_history (
    championship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_label TEXT,
    tournament_id INTEGER,
    winner_email TEXT NOT NULL,
    winner_display_name TEXT,
    winning_score REAL,
    payout_amount REAL DEFAULT 0.0,
    roster_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_AWARDS_LOG_SQL = """
CREATE TABLE IF NOT EXISTS awards_log (
    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    award_type TEXT NOT NULL,
    award_key TEXT NOT NULL,
    award_name TEXT NOT NULL,
    context_json TEXT,
    granted_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_TOURNAMENT_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS tournament_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER,
    entry_id INTEGER,
    user_email TEXT,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    message TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_STRIPE_CHECKOUT_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS stripe_checkout_sessions (
    session_id TEXT PRIMARY KEY,
    tournament_id INTEGER,
    user_email TEXT,
    payment_intent_id TEXT,
    payment_status TEXT DEFAULT 'unknown',
    stripe_event_id TEXT,
    raw_event_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_PENDING_PAID_ENTRIES_SQL = """
CREATE TABLE IF NOT EXISTS pending_paid_entries (
    pending_id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkout_session_id TEXT UNIQUE NOT NULL,
    tournament_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,
    display_name TEXT,
    roster_json TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    payment_intent_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

TOURNAMENT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tournaments_status_lock ON tournaments(status, lock_time)",
    "CREATE INDEX IF NOT EXISTS idx_entries_tid ON tournament_entries(tournament_id)",
    "CREATE INDEX IF NOT EXISTS idx_entries_user ON tournament_entries(user_email)",
    "CREATE INDEX IF NOT EXISTS idx_scores_tid ON simulated_scores(tournament_id)",
    "CREATE INDEX IF NOT EXISTS idx_profile_tier ON player_profiles(rarity_tier)",
    "CREATE INDEX IF NOT EXISTS idx_awards_user ON awards_log(user_email, granted_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_tid_time ON tournament_events(tournament_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_checkout_tid ON stripe_checkout_sessions(tournament_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_checkout_email ON stripe_checkout_sessions(user_email, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_pending_tid_status ON pending_paid_entries(tournament_id, status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_pending_email_status ON pending_paid_entries(user_email, status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_sub_status_active ON user_subscription_status(premium_active, legend_pass_active, updated_at)",
)


def initialize_tournament_database() -> bool:
    """Initialize the standalone tournament DB and schema."""
    DB_DIRECTORY.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(TOURNAMENT_DB_PATH), check_same_thread=False, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(CREATE_PLAYER_PROFILES_SQL)
            conn.execute(CREATE_TOURNAMENTS_SQL)
            conn.execute(CREATE_TOURNAMENT_ENTRIES_SQL)
            conn.execute(CREATE_SIMULATED_SCORES_SQL)
            conn.execute(CREATE_USER_CAREER_STATS_SQL)
            conn.execute(CREATE_CHAMPIONSHIP_HISTORY_SQL)
            conn.execute(CREATE_AWARDS_LOG_SQL)
            conn.execute(CREATE_TOURNAMENT_EVENTS_SQL)
            conn.execute(CREATE_STRIPE_CHECKOUT_SESSIONS_SQL)
            conn.execute(CREATE_PENDING_PAID_ENTRIES_SQL)
            conn.execute(CREATE_USER_SUBSCRIPTION_STATUS_SQL)

            # Backward-compatible migrations for existing standalone DB files.
            try:
                conn.execute("ALTER TABLE tournament_entries ADD COLUMN stripe_refund_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE tournament_entries ADD COLUMN stripe_transfer_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE tournament_entries ADD COLUMN refund_status TEXT DEFAULT 'none'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE tournament_entries ADD COLUMN payout_status TEXT DEFAULT 'pending'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE tournaments ADD COLUMN sport TEXT NOT NULL DEFAULT 'nba'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_onboarding_status TEXT DEFAULT 'not_started'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_details_submitted INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_payouts_enabled INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_requirements_json TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_kyc_verified INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_kyc_verified_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE user_career_stats ADD COLUMN stripe_connect_last_synced_at TEXT")
            except sqlite3.OperationalError:
                pass

            for idx_sql in TOURNAMENT_INDEXES:
                conn.execute(idx_sql)
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def get_tournament_connection() -> sqlite3.Connection:
    """Return a connection to the standalone tournament DB."""
    initialize_tournament_database()
    conn = sqlite3.connect(str(TOURNAMENT_DB_PATH), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def upsert_player_profiles(profiles: list[dict]) -> int:
    """Persist player profiles to the standalone tournament DB."""
    if not profiles:
        return 0

    inserted = 0
    with get_tournament_connection() as conn:
        for p in profiles:
            conn.execute(
                """
                INSERT INTO player_profiles
                    (player_id, player_name, team, position, overall_rating, archetype,
                     rarity_tier, salary, profile_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(player_id) DO UPDATE SET
                    player_name=excluded.player_name,
                    team=excluded.team,
                    position=excluded.position,
                    overall_rating=excluded.overall_rating,
                    archetype=excluded.archetype,
                    rarity_tier=excluded.rarity_tier,
                    salary=excluded.salary,
                    profile_json=excluded.profile_json,
                    updated_at=datetime('now')
                """,
                (
                    str(p.get("player_id", "")),
                    str(p.get("player_name", "")),
                    str(p.get("team", "")),
                    str(p.get("position", "")),
                    int(p.get("overall_rating", 50)),
                    str(p.get("archetype", "Versatile")),
                    str(p.get("rarity_tier", "Bench")),
                    int(p.get("salary", 3000)),
                    json.dumps(p),
                ),
            )
            inserted += 1
        conn.commit()
    return inserted
