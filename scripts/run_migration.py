#!/usr/bin/env python3
"""
Database Migration Runner

Runs SQL migration files in order.
Tracks applied migrations in migrations_history table.
"""
import asyncio
import asyncpg
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_config


async def ensure_migrations_table(conn):
    """Create migrations_history table if it doesn't exist"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations_history (
            migration_id TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            success BOOLEAN NOT NULL,
            error_message TEXT
        )
    """)


async def get_applied_migrations(conn):
    """Get list of successfully applied migrations"""
    rows = await conn.fetch("""
        SELECT migration_id
        FROM migrations_history
        WHERE success = TRUE
        ORDER BY migration_id
    """)
    return {row['migration_id'] for row in rows}


async def apply_migration(conn, migration_file: Path):
    """Apply a single migration file"""
    migration_id = migration_file.stem

    print(f"Applying migration: {migration_id}")

    # Read migration SQL
    sql = migration_file.read_text()

    try:
        # Execute migration
        await conn.execute(sql)

        # Record success
        await conn.execute("""
            INSERT INTO migrations_history (migration_id, success)
            VALUES ($1, TRUE)
        """, migration_id)

        print(f"✅ Migration {migration_id} applied successfully")
        return True

    except Exception as e:
        # Record failure
        await conn.execute("""
            INSERT INTO migrations_history (migration_id, success, error_message)
            VALUES ($1, FALSE, $2)
            ON CONFLICT (migration_id) DO UPDATE
            SET success = FALSE, error_message = $2, applied_at = NOW()
        """, migration_id, str(e))

        print(f"❌ Migration {migration_id} failed: {e}")
        return False


async def run_migrations(migration_dir: Path = None):
    """Run all pending migrations"""
    config = get_config()

    # Default migration directory
    if migration_dir is None:
        migration_dir = Path(__file__).parent.parent / 'sql' / 'migrations'

    if not migration_dir.exists():
        print(f"Migration directory not found: {migration_dir}")
        return False

    print("=" * 80)
    print("DATABASE MIGRATION RUNNER")
    print("=" * 80)
    print()

    # Connect to database
    print("Connecting to database...")
    conn = await asyncpg.connect(
        host=config.get('database.host'),
        port=config.get('database.port'),
        database=config.get('database.database'),
        user=config.get('database.user'),
        password=config.get('database.password'),
        ssl='require'
    )

    try:
        # Ensure migrations table exists
        await ensure_migrations_table(conn)

        # Get already applied migrations
        applied = await get_applied_migrations(conn)
        print(f"Already applied: {len(applied)} migrations")
        print()

        # Find migration files
        migration_files = sorted(migration_dir.glob('*.sql'))

        if not migration_files:
            print("No migration files found")
            return True

        print(f"Found {len(migration_files)} migration files")
        print()

        # Apply pending migrations
        pending = [f for f in migration_files if f.stem not in applied]

        if not pending:
            print("✅ All migrations already applied")
            return True

        print(f"Pending migrations: {len(pending)}")
        print()

        success_count = 0
        for migration_file in pending:
            success = await apply_migration(conn, migration_file)
            if success:
                success_count += 1
            else:
                print()
                print("❌ Migration failed. Stopping.")
                return False

        print()
        print("=" * 80)
        print(f"✅ Applied {success_count}/{len(pending)} migrations successfully")
        print("=" * 80)
        return True

    finally:
        await conn.close()


if __name__ == '__main__':
    success = asyncio.run(run_migrations())
    sys.exit(0 if success else 1)
