"""
Tournament Manager (Phase 1)

CRUD operations for tournaments.
Handles: create, fill, lock, resolve, cancel, list, get details.

Lifecycle:
  draft → open (entry starts) → locked (no more entries) → resolved
  
  Auto-cancel if min entries not met 30 min before lock.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from config import TOURNAMENT_CONFIG, ROSTER_CONFIG


@dataclass
class Tournament:
    """Tournament record."""
    tournament_id: int
    sport: str  # NBA, MLB, NFL, MLS
    name: str
    tournament_type: str  # open_court, pro_court, elite_court, championship
    entry_fee: float
    status: str  # draft, open, locked, resolved, cancelled
    min_entries: int
    max_entries: int
    current_entries: int
    scheduled_start: datetime
    lock_time: datetime
    total_prize_pool: float


class TournamentManager:
    """Manage tournament lifecycle."""
    
    def __init__(self, db_connection):
        """
        Initialize manager.
        
        Args:
            db_connection: Database connection
        """
        self.conn = db_connection
        self.cursor = None
    
    def create_tournament(
        self,
        sport: str,
        name: str,
        tournament_type: str,
        entry_fee: float,
        scheduled_start: datetime,
        lock_time: datetime,
        min_entries: int = None,
        max_entries: int = None,
    ) -> int:
        """
        Create new tournament.
        
        Args:
            sport: NBA, MLB, NFL, MLS
            name: Tournament name (e.g., "Sunday Night Scorer")
            tournament_type: open_court, pro_court, elite_court, championship
            entry_fee: Entry fee in dollars
            scheduled_start: Game time
            lock_time: When entry closes
            min_entries: Min players (default 12)
            max_entries: Max players (default 32)
        
        Returns:
            tournament_id
        """
        if min_entries is None:
            min_entries = TOURNAMENT_CONFIG["min_field_size"]
        if max_entries is None:
            max_entries = TOURNAMENT_CONFIG["max_field_size"]
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tournaments (
                sport, name, tournament_type, entry_fee, status,
                min_entries, max_entries, current_entries,
                scheduled_start, lock_time, total_prize_pool, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sport, name, tournament_type, entry_fee, "draft",
            min_entries, max_entries, 0,
            scheduled_start, lock_time, 0.0, datetime.now()
        ))
        self.conn.commit()
        
        tournament_id = cursor.lastrowid
        cursor.close()
        return tournament_id
    
    def open_tournament(self, tournament_id: int) -> bool:
        """
        Open tournament for entry.
        Status: draft → open
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET status = 'open'
            WHERE tournament_id = ?
        """, (tournament_id,))
        self.conn.commit()
        cursor.close()
        return True
    
    def add_entry(
        self,
        tournament_id: int,
        user_id: int,
        roster: List[Dict[str, Any]],
        entry_fee_paid: float
    ) -> int:
        """
        Add entry to tournament.
        
        Args:
            tournament_id: Tournament ID
            user_id: User ID
            roster: [{player_id, position, salary}, ...]
            entry_fee_paid: Amount paid
        
        Returns:
            entry_id
        """
        # Validate roster
        total_salary = sum(p["salary"] for p in roster)
        if total_salary < ROSTER_CONFIG["salary_floor_active"]:
            raise ValueError(f"Roster salary ({total_salary}) below floor ({ROSTER_CONFIG['salary_floor_active']})")
        if total_salary > ROSTER_CONFIG["salary_cap_active"] + ROSTER_CONFIG["salary_cap_legend"]:
            raise ValueError(f"Roster salary ({total_salary}) exceeds cap")
        
        # Insert entry
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO entries (
                tournament_id, user_id, roster_json,
                salary_spent, entry_fee_paid, entry_time, entry_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tournament_id, user_id, json.dumps(roster),
            total_salary, entry_fee_paid, datetime.now(), "active"
        ))
        self.conn.commit()
        
        entry_id = cursor.lastrowid
        
        # Increment tournament entries
        cursor.execute("""
            UPDATE tournaments
            SET current_entries = current_entries + 1,
                total_prize_pool = current_entries * ?
            WHERE tournament_id = ?
        """, (entry_fee_paid, tournament_id))
        self.conn.commit()
        cursor.close()
        
        return entry_id
    
    def remove_entry(self, tournament_id: int, entry_id: int) -> bool:
        """
        Remove entry (before lock).
        
        Returns:
            True if removed, False if not found/locked
        """
        cursor = self.conn.cursor()
        
        # Check tournament status
        cursor.execute("SELECT status FROM tournaments WHERE tournament_id = ?", (tournament_id,))
        row = cursor.fetchone()
        if not row or row[0] != "open":
            return False
        
        # Remove entry
        cursor.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
        self.conn.commit()
        
        # Decrement tournament entries
        cursor.execute("""
            UPDATE tournaments
            SET current_entries = current_entries - 1
            WHERE tournament_id = ?
        """, (tournament_id,))
        self.conn.commit()
        cursor.close()
        
        return True
    
    def auto_cancel_if_underfilled(self, tournament_id: int) -> bool:
        """
        Check if tournament should be auto-cancelled (30 min before lock).
        If underfilled → cancel + refund all entries.
        
        Returns:
            True if cancelled, False otherwise
        """
        cursor = self.conn.cursor()
        
        # Get tournament
        cursor.execute("""
            SELECT tournament_id, lock_time, current_entries, min_entries, status
            FROM tournaments
            WHERE tournament_id = ?
        """, (tournament_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return False
        
        tid, lock_time, current_entries, min_entries, status = row
        
        # Is it within 30 min of lock?
        now = datetime.now()
        time_to_lock = lock_time - now
        is_near_lock = time_to_lock < timedelta(minutes=30)
        
        # If near lock AND underfilled → cancel
        if is_near_lock and current_entries < min_entries and status == "open":
            cursor.execute("""
                UPDATE tournaments
                SET status = 'cancelled'
                WHERE tournament_id = ?
            """, (tid,))
            self.conn.commit()
            
            # Mark all entries as cancelled (for refund processing)
            cursor.execute("""
                UPDATE entries
                SET entry_status = 'cancelled'
                WHERE tournament_id = ?
            """, (tid,))
            self.conn.commit()
            
            cursor.close()
            return True
        
        cursor.close()
        return False
    
    def lock_tournament(self, tournament_id: int) -> bool:
        """
        Lock tournament (no more entries accepted).
        Status: open → locked
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET status = 'locked'
            WHERE tournament_id = ?
        """, (tournament_id,))
        self.conn.commit()
        cursor.close()
        return True
    
    def resolve_tournament(
        self,
        tournament_id: int,
        entry_scores: List[Dict[str, Any]],
        seed_int: int
    ) -> bool:
        """
        Resolve tournament (set scores, calculate payouts).
        
        Args:
            tournament_id: Tournament ID
            entry_scores: [{entry_id, total_fp}, ...]
            seed_int: Tournament seed
        
        Returns:
            True if resolved
        """
        cursor = self.conn.cursor()
        
        # Update seed
        cursor.execute("""
            UPDATE tournaments
            SET status = 'resolved', seed_int = ?, resolution_time = ?
            WHERE tournament_id = ?
        """, (seed_int, datetime.now(), tournament_id))
        self.conn.commit()
        
        # Update entry scores
        for score_rec in entry_scores:
            cursor.execute("""
                UPDATE entries
                SET total_fantasy_points = ?
                WHERE entry_id = ?
            """, (score_rec["total_fp"], score_rec["entry_id"]))
        self.conn.commit()
        
        # Rank entries
        cursor.execute("""
            SELECT entry_id FROM entries
            WHERE tournament_id = ?
            ORDER BY total_fantasy_points DESC
        """, (tournament_id,))
        
        rows = cursor.fetchall()
        for placement, (entry_id,) in enumerate(rows, 1):
            cursor.execute("""
                UPDATE entries
                SET placement = ?
                WHERE entry_id = ?
            """, (placement, entry_id))
        self.conn.commit()
        
        cursor.close()
        return True
    
    def cancel_tournament(self, tournament_id: int) -> bool:
        """
        Cancel tournament (all entries eligible for refund).
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET status = 'cancelled'
            WHERE tournament_id = ?
        """, (tournament_id,))
        self.conn.commit()
        cursor.close()
        return True
    
    def get_tournament(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """Get tournament details."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                tournament_id, sport, name, tournament_type, entry_fee,
                status, min_entries, max_entries, current_entries,
                scheduled_start, lock_time, total_prize_pool, created_at
            FROM tournaments
            WHERE tournament_id = ?
        """, (tournament_id,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            return None
        
        return {
            "tournament_id": row[0],
            "sport": row[1],
            "name": row[2],
            "tournament_type": row[3],
            "entry_fee": row[4],
            "status": row[5],
            "min_entries": row[6],
            "max_entries": row[7],
            "current_entries": row[8],
            "scheduled_start": row[9],
            "lock_time": row[10],
            "total_prize_pool": row[11],
            "created_at": row[12],
        }
    
    def get_tournament_entries(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all entries for a tournament."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                entry_id, tournament_id, user_id, roster_json,
                salary_spent, total_fantasy_points, placement,
                prize_awarded, lp_awarded, entry_status
            FROM entries
            WHERE tournament_id = ?
            ORDER BY placement
        """, (tournament_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        
        entries = []
        for row in rows:
            entries.append({
                "entry_id": row[0],
                "tournament_id": row[1],
                "user_id": row[2],
                "roster": json.loads(row[3]),
                "salary_spent": row[4],
                "total_fantasy_points": row[5],
                "placement": row[6],
                "prize_awarded": row[7],
                "lp_awarded": row[8],
                "entry_status": row[9],
            })
        
        return entries
    
    def get_user_entries(self, user_id: int, sport: str = "NBA") -> List[Dict[str, Any]]:
        """Get all entries for a user in a sport."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                e.entry_id, e.tournament_id, t.name, t.sport, t.status,
                e.total_fantasy_points, e.placement, e.prize_awarded
            FROM entries e
            JOIN tournaments t ON e.tournament_id = t.tournament_id
            WHERE e.user_id = ? AND t.sport = ?
            ORDER BY t.lock_time DESC
        """, (user_id, sport))
        
        rows = cursor.fetchall()
        cursor.close()
        
        entries = []
        for row in rows:
            entries.append({
                "entry_id": row[0],
                "tournament_id": row[1],
                "tournament_name": row[2],
                "sport": row[3],
                "status": row[4],
                "total_fantasy_points": row[5],
                "placement": row[6],
                "prize_awarded": row[7],
            })
        
        return entries
    
    def list_tournaments(
        self,
        sport: str = "NBA",
        status: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List tournaments."""
        query = "SELECT * FROM tournaments WHERE sport = ?"
        params = [sport]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY lock_time DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        
        tournaments = []
        for row in rows:
            tournaments.append({
                "tournament_id": row[0],
                "sport": row[1],
                "name": row[2],
                "tournament_type": row[3],
                "entry_fee": row[4],
                "status": row[5],
                "current_entries": row[7],
                "max_entries": row[8],
                "lock_time": row[11],
            })
        
        return tournaments


if __name__ == "__main__":
    import sqlite3
    
    # Test
    conn = sqlite3.connect(":memory:")
    from db.schema import create_all_tables
    create_all_tables(conn)
    
    manager = TournamentManager(conn)
    
    # Create tournament
    tid = manager.create_tournament(
        sport="NBA",
        name="Sunday Night Scorer",
        tournament_type="pro_court",
        entry_fee=5.0,
        scheduled_start=datetime.now() + timedelta(hours=1),
        lock_time=datetime.now() + timedelta(hours=30),
    )
    print(f"✅ Created tournament {tid}")
    
    # Get tournament
    tourney = manager.get_tournament(tid)
    print(f"✅ Retrieved: {tourney['name']} (status: {tourney['status']})")
