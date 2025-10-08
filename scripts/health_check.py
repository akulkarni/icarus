"""
Health Check Script

Verifies system is running correctly.
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta, timezone
from src.core.config import get_config


async def check_database():
    """Check database connectivity"""
    print("Checking database connection...")
    config = get_config()

    try:
        conn = await asyncpg.connect(
            host=config.get('database.host'),
            port=config.get('database.port'),
            database=config.get('database.database'),
            user=config.get('database.user'),
            password=config.get('database.password'),
            ssl='require'
        )

        version = await conn.fetchval('SELECT version()')
        print(f"✅ Connected to: {version[:50]}...")
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


async def check_schema():
    """Check required tables exist"""
    print("\nChecking database schema...")
    config = get_config()

    try:
        conn = await asyncpg.connect(
            host=config.get('database.host'),
            port=config.get('database.port'),
            database=config.get('database.database'),
            user=config.get('database.user'),
            password=config.get('database.password'),
            ssl='require'
        )

        required_tables = [
            'market_data', 'trades', 'positions', 'trading_signals',
            'strategy_performance', 'agent_status', 'fork_tracking'
        ]

        all_exist = True
        for table in required_tables:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = $1
                )
            """, table)

            if exists:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
                all_exist = False

        await conn.close()
        return all_exist
    except Exception as e:
        print(f"❌ Schema check failed: {e}")
        return False


async def check_agents():
    """Check agent status"""
    print("\nChecking agent status...")
    config = get_config()

    try:
        conn = await asyncpg.connect(
            host=config.get('database.host'),
            port=config.get('database.port'),
            database=config.get('database.database'),
            user=config.get('database.user'),
            password=config.get('database.password'),
            ssl='require'
        )

        # Get agents updated in last 2 minutes
        agents = await conn.fetch("""
            SELECT agent_name, status, last_heartbeat
            FROM agent_status
            WHERE last_heartbeat >= NOW() - INTERVAL '2 minutes'
        """)

        if not agents:
            print("⚠️  No active agents found (system may not be running)")
            await conn.close()
            return False

        for agent in agents:
            now = datetime.now(timezone.utc)
            elapsed = (now - agent['last_heartbeat']).total_seconds()
            print(f"✅ {agent['agent_name']}: {agent['status']} (heartbeat {elapsed:.0f}s ago)")

        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Agent check failed: {e}")
        return False


async def check_activity():
    """Check recent system activity"""
    print("\nChecking recent activity...")
    config = get_config()

    try:
        conn = await asyncpg.connect(
            host=config.get('database.host'),
            port=config.get('database.port'),
            database=config.get('database.database'),
            user=config.get('database.user'),
            password=config.get('database.password'),
            ssl='require'
        )

        # Count recent events
        trade_count = await conn.fetchval("""
            SELECT COUNT(*) FROM trades
            WHERE time >= NOW() - INTERVAL '1 hour'
        """)
        print(f"📊 Trades (last hour): {trade_count}")

        signal_count = await conn.fetchval("""
            SELECT COUNT(*) FROM trading_signals
            WHERE time >= NOW() - INTERVAL '1 hour'
        """)
        print(f"📊 Signals (last hour): {signal_count}")

        tick_count = await conn.fetchval("""
            SELECT COUNT(*) FROM market_data
            WHERE time >= NOW() - INTERVAL '5 minutes'
        """)
        print(f"📊 Market ticks (last 5 min): {tick_count}")

        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Activity check failed: {e}")
        return False


async def main():
    """Run all health checks"""
    print("=" * 60)
    print("ICARUS TRADING SYSTEM - HEALTH CHECK")
    print("=" * 60)

    checks = [
        check_database(),
        check_schema(),
        check_agents(),
        check_activity()
    ]

    results = await asyncio.gather(*checks, return_exceptions=True)

    all_passed = all(r is True for r in results if not isinstance(r, Exception))

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
