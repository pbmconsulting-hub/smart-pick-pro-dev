"""
Tournament Database Schema (Phase 0)

Core tables for tournament system.
Extends tracking/database.py with sport-agnostic tables.
"""

TOURNAMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport VARCHAR(20) NOT NULL DEFAULT 'NBA',  -- NBA, MLB, NFL, etc.
    name VARCHAR(255) NOT NULL,
    tournament_type VARCHAR(50),  -- open_court, pro_court, elite_court, championship
    entry_fee DECIMAL(10, 2) NOT NULL DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'draft',  -- draft, open, locked, resolved, cancelled
    
    min_entries INTEGER DEFAULT 12,
    max_entries INTEGER DEFAULT 32,
    current_entries INTEGER DEFAULT 0,
    
    scheduled_start TIMESTAMP,
    actual_start TIMESTAMP,
    lock_time TIMESTAMP NOT NULL,
    resolution_time TIMESTAMP,
    
    seed_hex VARCHAR(64),  -- Published after resolution
    seed_int INTEGER,
    
    total_prize_pool DECIMAL(10, 2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id INT,
    
    UNIQUE(tournament_id)
);
"""

ENTRIES_TABLE = """
CREATE TABLE IF NOT EXISTS entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    
    roster_json TEXT NOT NULL,  -- JSON array of {player_id, position, salary}
    entry_status VARCHAR(50) DEFAULT 'active',  -- active, cancelled, pending
    
    salary_spent DECIMAL(10, 2),
    salary_cap_active DECIMAL(10, 2) NOT NULL DEFAULT 50000,
    salary_cap_legend DECIMAL(10, 2) NOT NULL DEFAULT 15000,
    
    entry_fee_paid DECIMAL(10, 2),
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    total_fantasy_points DECIMAL(10, 2),
    placement INTEGER,
    prize_awarded DECIMAL(10, 2) DEFAULT 0.0,
    lp_awarded INTEGER DEFAULT 0,
    
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    UNIQUE(tournament_id, user_id)
);
"""

PLAYER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS player_profiles (
    player_id INTEGER PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    sport VARCHAR(20) NOT NULL DEFAULT 'NBA',
    team VARCHAR(10),
    position VARCHAR(2),
    secondary_position VARCHAR(2),
    age INTEGER,
    
    -- Season Stats
    ppg DECIMAL(5, 1),
    rpg DECIMAL(5, 1),
    apg DECIMAL(5, 1),
    spg DECIMAL(5, 2),
    bpg DECIMAL(5, 2),
    tpg DECIMAL(5, 2),
    threes_pg DECIMAL(5, 2),
    fg_pct DECIMAL(5, 3),
    ft_pct DECIMAL(5, 3),
    ts_pct DECIMAL(5, 3),
    usage_rate DECIMAL(5, 3),
    minutes_pg DECIMAL(5, 1),
    
    -- Attributes (Percentile Ranks 1–99)
    attr_scoring INTEGER,
    attr_playmaking INTEGER,
    attr_rebounding INTEGER,
    attr_defense INTEGER,
    attr_consistency INTEGER,
    attr_clutch INTEGER,
    
    overall_rating INTEGER,
    archetype VARCHAR(50),
    rarity_tier VARCHAR(50),
    salary INTEGER,
    
    -- QME Inputs
    fp_mean DECIMAL(10, 2),
    fp_std_dev DECIMAL(10, 2),
    
    -- Form
    hot_cold_label VARCHAR(20),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_legend BOOLEAN DEFAULT FALSE,
    injury_status VARCHAR(255),
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_id, sport)
);
"""

PLAYER_GAME_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS player_game_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    game_date DATE NOT NULL,
    
    points INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    steals INTEGER,
    blocks INTEGER,
    turnovers INTEGER,
    threes_made INTEGER,
    
    minutes_played DECIMAL(5, 1),
    
    FOREIGN KEY(player_id) REFERENCES player_profiles(player_id)
);
"""

TOURNAMENT_SIMULATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS tournament_simulations (
    simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    
    -- Environment (Tier 1)
    home_score INTEGER,
    away_score INTEGER,
    margin INTEGER,
    total INTEGER,
    went_to_ot BOOLEAN,
    blowout_risk_factor DECIMAL(5, 3),
    pace_adjustment_factor DECIMAL(5, 4),
    environment_label VARCHAR(100),
    
    -- Player Stats (Tier 2)
    player_id INTEGER NOT NULL,
    points_simulated INTEGER,
    rebounds_simulated INTEGER,
    assists_simulated INTEGER,
    steals_simulated INTEGER,
    blocks_simulated INTEGER,
    turnovers_simulated INTEGER,
    threes_simulated INTEGER,
    
    fantasy_points DECIMAL(10, 2),
    bonuses_applied DECIMAL(10, 2) DEFAULT 0.0,
    penalties_applied DECIMAL(10, 2) DEFAULT 0.0,
    total_fp DECIMAL(10, 2),
    
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY(player_id) REFERENCES player_profiles(player_id)
);
"""

PAYOUTS_TABLE = """
CREATE TABLE IF NOT EXISTS payouts (
    payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    entry_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    
    placement INTEGER,
    prize_amount DECIMAL(10, 2),
    lp_awarded INTEGER DEFAULT 0,
    
    payout_status VARCHAR(50) DEFAULT 'pending',  -- pending, processed, failed
    stripe_payout_id VARCHAR(255),
    payout_date TIMESTAMP,
    
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY(entry_id) REFERENCES entries(entry_id)
);
"""

BADGES_TABLE = """
CREATE TABLE IF NOT EXISTS badges (
    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    badge_name VARCHAR(100) NOT NULL,
    badge_icon VARCHAR(10),
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tournament_id INTEGER,
    
    UNIQUE(user_id, badge_name, tournament_id)
);
"""

LEADERBOARD_TABLE = """
CREATE TABLE IF NOT EXISTS leaderboard (
    leaderboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    season INTEGER DEFAULT 2026,
    
    league_points INTEGER DEFAULT 0,
    tournament_wins INTEGER DEFAULT 0,
    top_10_finishes INTEGER DEFAULT 0,
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, season)
);
"""

def create_all_tables(db_connection):
    """Create all tournament tables."""
    tables = [
        TOURNAMENTS_TABLE,
        ENTRIES_TABLE,
        PLAYER_PROFILES_TABLE,
        PLAYER_GAME_LOGS_TABLE,
        TOURNAMENT_SIMULATIONS_TABLE,
        PAYOUTS_TABLE,
        BADGES_TABLE,
        LEADERBOARD_TABLE,
    ]
    
    cursor = db_connection.cursor()
    for table_sql in tables:
        cursor.execute(table_sql)
    db_connection.commit()
    cursor.close()
