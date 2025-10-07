"""
Database Initialization Script

Initializes the TimescaleDB schema for the Icarus Trading System.
"""
import asyncio
import asyncpg
import argparse
import sys
from pathlib import Path


async def check_schema_exists(conn):
    """Check if schema is already initialized"""
    result = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'market_data'
        )
    """)
    return result


async def init_db(force=False):
    """Initialize database schema"""
    # Load configuration
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.core.config import get_config

    config = get_config()

    # Connection parameters
    host = config.get('database.host')
    port = config.get('database.port', 5432)
    database = config.get('database.database', 'tsdb')
    user = config.get('database.user', 'tsdbadmin')
    password = config.get('database.password')

    if not host or not password:
        print("❌ Error: Database credentials not configured")
        print("   Please set TIGER_HOST and TIGER_PASSWORD in your .env file")
        return False

    print("=" * 80)
    print("ICARUS TRADING SYSTEM - DATABASE INITIALIZATION")
    print("=" * 80)
    print(f"Host: {host}")
    print(f"Database: {database}")
    print(f"User: {user}")
    print()

    try:
        # Connect to database
        print("Connecting to database...")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            ssl='require'
        )

        # Check if schema already exists
        exists = await check_schema_exists(conn)

        if exists and not force:
            print("⚠️  Schema already exists!")
            print("   Use --force to drop and recreate all tables")
            print("   WARNING: This will delete all data!")
            await conn.close()
            return False

        if exists and force:
            print("⚠️  Force mode enabled - dropping existing schema...")
            print("   This will DELETE ALL DATA!")
            print()

            # Drop all tables
            print("Dropping existing tables...")
            await conn.execute("""
                DROP SCHEMA public CASCADE;
                CREATE SCHEMA public;
                GRANT ALL ON SCHEMA public TO tsdbadmin;
                GRANT ALL ON SCHEMA public TO public;
            """)
            print("✅ Existing schema dropped")

        # Read schema file
        schema_path = Path(__file__).parent.parent / 'sql' / 'schema.sql'
        if not schema_path.exists():
            print(f"❌ Error: Schema file not found: {schema_path}")
            await conn.close()
            return False

        print(f"Reading schema from {schema_path}...")
        schema_sql = schema_path.read_text()

        # Execute schema
        print("Creating database schema...")
        print("  - Creating TimescaleDB extension...")
        print("  - Creating tables...")
        print("  - Creating hypertables...")
        print("  - Creating indexes...")
        print("  - Creating continuous aggregates...")
        print("  - Setting up retention policies...")
        print("  - Setting up compression policies...")
        print()

        # Use psql to execute schema (handles continuous aggregates correctly)
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(schema_sql)
            temp_sql_path = f.name

        try:
            # Build psql connection string
            conn_str = f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode=require"

            # Execute using psql
            result = subprocess.run(
                ['psql', conn_str, '-f', temp_sql_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"❌ Error executing schema:")
                print(result.stderr)
                raise RuntimeError(f"Schema execution failed: {result.stderr}")

        finally:
            # Clean up temp file
            Path(temp_sql_path).unlink(missing_ok=True)

        print("✅ Database schema initialized successfully")
        print()

        # Verify setup
        print("Verifying schema...")

        # Check hypertables
        hypertables = await conn.fetch("""
            SELECT hypertable_name
            FROM timescaledb_information.hypertables
            ORDER BY hypertable_name
        """)

        print(f"  ✅ Created {len(hypertables)} hypertables:")
        for ht in hypertables:
            print(f"     - {ht['hypertable_name']}")

        # Check regular tables
        tables = await conn.fetch("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT IN (
                SELECT hypertable_name
                FROM timescaledb_information.hypertables
            )
            ORDER BY tablename
        """)

        print(f"  ✅ Created {len(tables)} regular tables:")
        for table in tables:
            print(f"     - {table['tablename']}")

        # Check continuous aggregates
        caggs = await conn.fetch("""
            SELECT view_name
            FROM timescaledb_information.continuous_aggregates
            ORDER BY view_name
        """)

        print(f"  ✅ Created {len(caggs)} continuous aggregates:")
        for cagg in caggs:
            print(f"     - {cagg['view_name']}")

        await conn.close()

        print()
        print("=" * 80)
        print("✅ DATABASE INITIALIZATION COMPLETE")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Run the system: python -m src.main")
        print("  2. Check health: python scripts/health_check.py")
        print()

        return True

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Initialize Icarus Trading System database schema'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Drop and recreate all tables (WARNING: deletes all data)'
    )

    args = parser.parse_args()

    if args.force:
        print()
        print("⚠️  WARNING: Force mode will DELETE ALL DATA!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
        print()

    success = asyncio.run(init_db(force=args.force))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
