"""
Tournament Bootstrap Script (Phase 0)

Initializes the tournament database and environment.
Run once to set up the isolated tournament system.
"""

import os
import sys
from pathlib import Path

# Add tournament root to path
TOURNAMENT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TOURNAMENT_ROOT))

from config import DATABASE_URL
from db.schema import create_all_tables


def bootstrap_tournament():
    """Initialize tournament environment."""
    print("🚀 Bootstrapping Tournament System...")
    
    # 1. Create .env if missing
    env_file = TOURNAMENT_ROOT / ".env"
    if not env_file.exists():
        print("   📝 Creating .env from .env.example...")
        example = TOURNAMENT_ROOT / ".env.example"
        if example.exists():
            import shutil
            shutil.copy(example, env_file)
            print(f"   ✅ Created {env_file}")
    
    # 2. Initialize database
    print("   📦 Initializing database...")
    
    if "sqlite" in DATABASE_URL:
        # SQLite
        import sqlite3
        db_path = DATABASE_URL.replace("sqlite:///", "")
        db_path = TOURNAMENT_ROOT / db_path if not db_path.startswith("/") else db_path
        
        conn = sqlite3.connect(str(db_path))
        create_all_tables(conn)
        conn.close()
        print(f"   ✅ Database initialized at {db_path}")
    else:
        print("   ⚠️  PostgreSQL not yet supported in Phase 0")
    
    # 3. Create test fixtures (optional)
    print("   🏀 Creating sample NBA legends...")
    # Stub for Phase 1
    
    print("\n✅ Tournament environment ready!")
    print(f"   Root: {TOURNAMENT_ROOT}")
    print(f"   DB: {DATABASE_URL}")
    print("\n📚 Next steps:")
    print("   1. Run tests: pytest tests/ -v")
    print("   2. Review engine files in engine/")
    print("   3. Begin Phase 1 UI development")


if __name__ == "__main__":
    bootstrap_tournament()
