# Bug Fixes and Improvements - Parallel Execution Plan

## Overview
This document outlines 13 fixes needed after Day 1 implementation, organized for parallel execution by 3 agents.

**Total Estimated Time**: 2-3 hours (sequential) → **~1 hour (parallel)**

---

## Agent 1: Core Infrastructure & Entry Points (4 tasks, ~1 hour)

### Task 1.1: Create Main Entry Point
**File**: `src/main.py` (NEW)
**Priority**: CRITICAL
**Estimated Time**: 25 minutes

**Description**: Create the main orchestration script that starts all agents.

**Requirements**:
- Initialize logging from config
- Initialize database manager and run connection test
- Create global event bus instance
- Instantiate all 7 agents:
  - MarketDataAgent (with symbols from config)
  - MomentumStrategy (if enabled in config)
  - MACDStrategy (if enabled in config)
  - ExecutionAgent (with initial capital from config)
  - MetaStrategyAgent (with strategy list)
  - ForkManagerAgent (with parent service ID from config)
  - RiskMonitorAgent (with risk config)
- Start all agents with asyncio.gather()
- Handle graceful shutdown (SIGTERM, SIGINT)
- Cleanup: close event bus, close database connections, stop all agents

**Example Structure**:
```python
async def main():
    # Load config
    config = load_config()

    # Setup logging
    setup_logging(config)

    # Initialize database
    db = await get_db_manager()
    await db.initialize()

    # Create event bus
    event_bus = get_event_bus_sync()

    # Create agents
    agents = [
        MarketDataAgent(event_bus, config['trading']['symbols']),
        MomentumStrategy(...),
        # ... etc
    ]

    # Start all agents
    tasks = [agent.run() for agent in agents]
    await asyncio.gather(*tasks)
```

**Verification**:
- Run `python -m src.main` and verify all agents start
- Check logs show "Starting agent: {name}" for each agent
- Press Ctrl+C and verify graceful shutdown

---

### Task 1.2: Create Database Initialization Script
**File**: `scripts/init_db.py` (NEW)
**Priority**: CRITICAL
**Estimated Time**: 15 minutes

**Description**: Create script to initialize database schema on first run.

**Requirements**:
- Connect to database using config
- Check if `market_data` table exists (probe for existing schema)
- If not exists, read and execute `sql/schema.sql`
- Handle errors gracefully
- Print success/failure message
- Support `--force` flag to drop and recreate all tables

**Example**:
```python
import asyncio
import asyncpg
from pathlib import Path
from src.core.config import get_config

async def check_schema_exists(conn):
    result = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'market_data'
        )
    """)
    return result

async def init_db(force=False):
    config = get_config()
    conn = await asyncpg.connect(...)

    exists = await check_schema_exists(conn)

    if exists and not force:
        print("Schema already exists. Use --force to recreate.")
        return

    schema_sql = Path('sql/schema.sql').read_text()
    await conn.execute(schema_sql)
    print("Database schema initialized successfully")
```

**Verification**:
- Run `python scripts/init_db.py` on fresh database
- Verify all tables created: `SELECT tablename FROM pg_tables WHERE schemaname='public'`
- Run again and verify it detects existing schema

---

### Task 1.3: Create Environment Variables Documentation
**File**: `.env.example` (NEW) and update `README.md`
**Priority**: HIGH
**Estimated Time**: 10 minutes

**Description**: Document all required environment variables.

**`.env.example` Contents**:
```bash
# Tiger Cloud Database Configuration
TIGER_HOST=your-service.tsdb.cloud.timescale.com
TIGER_PORT=5432
TIGER_DATABASE=tsdb
TIGER_USER=tsdbadmin
TIGER_PASSWORD=your_password_here

# Tiger Cloud Service ID (for forking)
TIGER_SERVICE_ID=abc123xyz

# Binance API (optional for Phase 1 paper trading)
# BINANCE_API_KEY=your_api_key
# BINANCE_API_SECRET=your_api_secret
```

**README.md Addition**:
```markdown
## Quick Start

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Tiger Cloud credentials

3. Initialize database:
   ```bash
   python scripts/init_db.py
   ```

4. Run the system:
   ```bash
   python -m src.main
   ```
```

**Verification**:
- Check `.env.example` has all variables from `config/app.yaml`
- Verify README has clear setup instructions

---

### Task 1.4: Fix Database Manager Async Usage
**Files**:
- `src/agents/market_data.py:82`
- `src/agents/execution.py:219`

**Priority**: HIGH
**Estimated Time**: 10 minutes

**Description**: Fix incorrect database manager access in async context.

**Current Bug**:
```python
db = get_db_manager()  # ❌ Returns coroutine, not manager
conn = await db.get_connection()
```

**Fix**:
```python
db = get_db_manager_sync()  # ✅ Synchronous singleton access
conn = await db.get_connection()
```

**Changes**:
1. `src/agents/market_data.py` line 82: Change to `get_db_manager_sync()`
2. `src/agents/execution.py` line 219: Change to `get_db_manager_sync()`

**Verification**:
- Grep for `get_db_manager()` usage without await
- Run tests: `pytest tests/test_agents/test_market_data.py tests/test_agents/test_execution.py`

---

## Agent 2: Risk Monitor & Event Fixes (4 tasks, ~45 minutes)

### Task 2.1: Fix RiskAlertEvent Field Names
**File**: `src/agents/risk_monitor.py`
**Priority**: CRITICAL
**Estimated Time**: 10 minutes

**Description**: Replace all `risk_type=` with `alert_type=` to match event schema.

**Locations to Fix** (5 occurrences):
- Line 174: `risk_type='position_size'` → `alert_type='position_size'`
- Line 190: `risk_type='position_size'` → `alert_type='position_size'`
- Line 236: `risk_type='exposure'` → `alert_type='exposure'`
- Line 254: `risk_type='exposure'` → `alert_type='exposure'`
- Line 379: `risk_type='strategy_drawdown'` → `alert_type='strategy_drawdown'`
- Line 342: `risk_type='daily_loss'` → `alert_type='daily_loss'`

**Fix Method**: Global find-replace in file:
```python
# Old:
RiskAlertEvent(
    severity='critical',
    risk_type='position_size',  # ❌
    ...
)

# New:
RiskAlertEvent(
    alert_type='position_size',  # ✅
    severity='critical',
    ...
)
```

**Verification**:
- Search file for `risk_type=` - should find 0 occurrences
- Search file for `alert_type=` - should find 6 occurrences
- Run: `pytest tests/test_agents/test_risk_monitor.py`

---

### Task 2.2: Fix EmergencyHaltEvent Structure
**File**: `src/agents/risk_monitor.py:321-331`
**Priority**: CRITICAL
**Estimated Time**: 5 minutes

**Description**: Fix EmergencyHaltEvent to use correct fields.

**Current Bug**:
```python
await self.publish(EmergencyHaltEvent(
    reason=f"Daily loss {abs(daily_loss_pct):.2f}% exceeds limit "
          f"{self.max_daily_loss_pct}%",
    severity='critical',  # ❌ Not a field
    metadata={...}  # ❌ Not a field
))
```

**Fix**:
```python
await self.publish(EmergencyHaltEvent(
    reason=f"Daily loss {abs(daily_loss_pct):.2f}% exceeds limit "
          f"{self.max_daily_loss_pct}%",
    triggered_by='risk_monitor',  # ✅ Required field
    affected_strategies=None  # ✅ Optional but good to include
))
```

**Also Add to Message**: Log the metadata separately:
```python
logger.critical(
    f"EMERGENCY HALT: Daily loss {abs(daily_loss_pct):.2f}% "
    f"exceeds {self.max_daily_loss_pct}% "
    f"(start: ${self.daily_start_value}, current: ${current_value})"
)
```

**Verification**:
- Check EmergencyHaltEvent signature in `src/models/events.py:285-289`
- Run: `pytest tests/test_agents/test_risk_monitor.py -k halt`

---

### Task 2.3: Add Strategy Performance Persistence
**File**: `src/agents/execution.py`
**Priority**: HIGH
**Estimated Time**: 20 minutes

**Description**: Add periodic strategy performance calculation and persistence.

**Requirements**:
- Add new method `_calculate_strategy_performance(strategy_name)` to ExecutionAgent
- Calculate metrics for last 7 days:
  - Total trades
  - Winning trades (PnL > 0)
  - Losing trades (PnL < 0)
  - Win rate
  - Total PnL
  - Sharpe ratio (if enough data)
  - Max drawdown
  - Current drawdown
- Persist to `strategy_performance` table every 15 minutes
- Add new async task `_performance_tracking_loop()` to run this periodically

**Implementation**:
```python
async def _performance_tracking_loop(self):
    """Calculate and persist strategy performance metrics"""
    while self._running:
        await asyncio.sleep(900)  # 15 minutes

        for strategy_name in self.strategy_portfolios.keys():
            try:
                await self._calculate_and_persist_performance(strategy_name)
            except Exception as e:
                self.logger.error(f"Error calculating performance for {strategy_name}: {e}")

async def _calculate_and_persist_performance(self, strategy_name: str):
    """Calculate performance metrics for a strategy"""
    db = get_db_manager_sync()
    conn = await db.get_connection()

    try:
        # Query trades for last 7 days
        trades = await conn.fetch("""
            SELECT side, quantity, price, fee, time
            FROM trades
            WHERE strategy_name = $1
              AND time >= NOW() - INTERVAL '7 days'
            ORDER BY time ASC
        """, strategy_name)

        if not trades:
            return

        # Calculate metrics
        total_pnl = Decimal('0')
        winning_trades = 0
        losing_trades = 0

        # Group into round-trip trades (buy -> sell pairs)
        # ... implement P&L calculation logic ...

        win_rate = winning_trades / len(trades) if trades else 0

        # Insert into strategy_performance
        await conn.execute("""
            INSERT INTO strategy_performance (
                time, strategy_name, total_trades, winning_trades,
                losing_trades, win_rate, total_pnl
            ) VALUES (NOW(), $1, $2, $3, $4, $5, $6)
        """, strategy_name, len(trades), winning_trades,
            losing_trades, win_rate, total_pnl)

    finally:
        await db.release_connection(conn)
```

**Update `start()` method**:
```python
async def start(self):
    # ... existing code ...

    # Run event loops concurrently
    await asyncio.gather(
        self._process_signals(signal_queue),
        self._process_allocations(allocation_queue),
        self._track_prices(market_queue),
        self._performance_tracking_loop()  # ✅ Add this
    )
```

**Verification**:
- Run system for 15+ minutes
- Query: `SELECT * FROM strategy_performance ORDER BY time DESC LIMIT 10`
- Verify rows inserted with calculated metrics

---

### Task 2.4: Fix Position Size Risk Calculation
**File**: `src/agents/execution.py:98-99`
**Priority**: MEDIUM
**Estimated Time**: 10 minutes

**Description**: Make position sizing respect risk limits and be configurable.

**Current Issue**:
```python
# Uses 20% of remaining cash
cash_to_use = portfolio['cash'] * Decimal('0.2')
```

**Problem**: If strategy has $5k allocated and $4k cash remaining, 20% of cash = $800, which is 16% of original allocation. But after a few trades, 20% of remaining cash might be too small OR too large relative to risk limits.

**Fix**: Use percentage of *allocated capital* instead:
```python
# Calculate allocated capital for this strategy
allocation_pct = self.current_allocations.get(signal.strategy_name, 0)
allocated_capital = self.initial_capital * (Decimal(str(allocation_pct)) / Decimal('100'))

# Use configured position size % (default 20% from risk config)
position_size_pct = Decimal('0.20')  # TODO: Get from config
cash_to_use = allocated_capital * position_size_pct

# But don't exceed available cash
cash_to_use = min(cash_to_use, portfolio['cash'])
```

**Also Add Config**:
In `config/app.yaml`:
```yaml
trading:
  position_size_pct: 20  # % of allocated capital per trade
```

**Verification**:
- Verify position sizes are consistent relative to allocated capital
- Check trades don't violate risk limits
- Run: `pytest tests/test_agents/test_execution.py -k position_size`

---

## Agent 3: Schema Fixes & Documentation (5 tasks, ~50 minutes)

### Task 3.1: Fix Fork Tracking Schema
**File**: `sql/schema.sql:201-215`
**Priority**: CRITICAL
**Estimated Time**: 5 minutes

**Description**: Rename `service_id` column to `parent_service_id` to match code.

**Current Schema**:
```sql
CREATE TABLE IF NOT EXISTS fork_tracking (
    fork_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,  -- ❌ Wrong name
    requesting_agent TEXT NOT NULL,
    ...
);
```

**Fixed Schema**:
```sql
CREATE TABLE IF NOT EXISTS fork_tracking (
    fork_id TEXT PRIMARY KEY,
    parent_service_id TEXT NOT NULL,  -- ✅ Matches code
    requesting_agent TEXT NOT NULL,
    ...
);
```

**Verification**:
- Check `src/agents/fork_manager.py:232` uses `parent_service_id`
- If database already initialized, run migration:
  ```sql
  ALTER TABLE fork_tracking RENAME COLUMN service_id TO parent_service_id;
  ```

---

### Task 3.2: Add Execution Mode Safeguards
**File**: `src/agents/execution.py`
**Priority**: MEDIUM
**Estimated Time**: 15 minutes

**Description**: Add validation to prevent accidental live trading.

**Requirements**:
1. Check `trade_mode` from config on startup
2. Log prominent warning if mode is "live"
3. Require explicit confirmation via environment variable for live mode
4. Make sell percentage configurable

**Implementation**:
```python
def __init__(self, event_bus, initial_capital: Decimal, config: dict):
    super().__init__("execution", event_bus)
    self.initial_capital = initial_capital
    self.trade_mode = config.get('trading', {}).get('mode', 'paper')
    self.position_exit_pct = Decimal(str(
        config.get('trading', {}).get('position_exit_pct', 50)
    )) / Decimal('100')  # Convert 50 -> 0.5

    # Safety check for live trading
    if self.trade_mode == 'live':
        if os.getenv('ALLOW_LIVE_TRADING') != 'true':
            raise RuntimeError(
                "Live trading mode requires ALLOW_LIVE_TRADING=true "
                "environment variable. This is a safety check to prevent "
                "accidental real trading."
            )
        logger.warning("=" * 80)
        logger.warning("LIVE TRADING MODE ENABLED - REAL MONEY AT RISK")
        logger.warning("=" * 80)
    else:
        logger.info("Paper trading mode enabled (simulated trades)")
```

**Update sell logic**:
```python
# Sell configurable % of position (line 173)
quantity = position_quantity * self.position_exit_pct
```

**Add to config/app.yaml**:
```yaml
trading:
  mode: paper  # paper or live
  position_exit_pct: 50  # % of position to exit on sell signal
```

**Verification**:
- Try setting `mode: live` without env var → should fail
- Set `ALLOW_LIVE_TRADING=true` → should start with warning
- Verify sell percentage is configurable

---

### Task 3.3: Add Logging Configuration
**File**: `src/core/logging_setup.py` (NEW)
**Priority**: MEDIUM
**Estimated Time**: 15 minutes

**Description**: Create proper logging setup from config.

**Requirements**:
- Read logging config from `config/app.yaml`
- Support JSON and standard formats
- Write to file and stdout
- Different log levels per module

**Implementation**:
```python
"""
Logging Setup

Configures logging based on app config.
"""
import logging
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger

def setup_logging(config):
    """
    Setup logging configuration.

    Args:
        config: Config object with logging settings
    """
    log_level = config.get('logging.level', 'INFO')
    log_format = config.get('logging.format', 'standard')
    log_file = config.get('logging.file', 'logs/icarus.log')

    # Create logs directory
    Path(log_file).parent.mkdir(exist_ok=True)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, log_level))

    # Format
    if log_format == 'json':
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={'timestamp': '@timestamp', 'level': 'severity'}
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Logging configured successfully")
```

**Update requirements.txt**:
```
python-json-logger>=2.0.7
```

**Verification**:
- Check logs appear in both file and console
- Verify JSON format works
- Test different log levels

---

### Task 3.4: Create Quick Start Guide
**File**: `docs/QUICKSTART.md` (NEW)
**Priority**: LOW
**Estimated Time**: 10 minutes

**Description**: Create beginner-friendly setup guide.

**Contents**:
```markdown
# Quick Start Guide

## Prerequisites
- Python 3.11+
- Tiger Cloud account with PostgreSQL database
- 10 minutes of time

## Step 1: Clone and Setup
```bash
git clone <repo>
cd project-planner
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your Tiger Cloud credentials:
- Get these from https://console.tigerdata.cloud/
- Click your service → "Connection Info"
- Copy host, port, database, user, password, service_id

## Step 3: Initialize Database
```bash
python scripts/init_db.py
```

## Step 4: Run the System
```bash
python -m src.main
```

You should see:
```
2025-10-07 10:00:00 [INFO] Starting agent: market_data
2025-10-07 10:00:00 [INFO] Starting agent: momentum
...
```

## Step 5: Monitor Activity
Open another terminal:
```bash
# Watch trades
psql $DATABASE_URL -c "SELECT * FROM trades ORDER BY time DESC LIMIT 10"

# Watch signals
psql $DATABASE_URL -c "SELECT * FROM trading_signals ORDER BY time DESC LIMIT 10"

# Check allocations
psql $DATABASE_URL -c "SELECT * FROM current_allocations"
```

## Stopping
Press `Ctrl+C` in the main terminal. All agents will shut down gracefully.

## Troubleshooting

**Problem**: `FileNotFoundError: Config file not found`
**Solution**: Make sure you're in the project root directory with `config/app.yaml`

**Problem**: `connection refused` to database
**Solution**: Check your `.env` has correct `TIGER_HOST` and `TIGER_PASSWORD`

**Problem**: `table "market_data" does not exist`
**Solution**: Run `python scripts/init_db.py` first

## Next Steps
- Read the [Architecture Overview](../docs/plans/live-trading-system-design.md)
- Explore the [Implementation Plan](../docs/plans/implementation-plan.md)
- Check the [Blog Post](../docs/blog-post.md) to understand the vision
```

**Verification**:
- Follow the guide on a fresh checkout
- Verify each step works as documented

---

### Task 3.5: Add Health Check Utility
**File**: `scripts/health_check.py` (NEW)
**Priority**: LOW
**Estimated Time**: 15 minutes

**Description**: Create script to verify system health.

**Requirements**:
- Check database connectivity
- Verify all required tables exist
- Check if agents are running (via agent_status table)
- Display recent activity (trades, signals, alerts)
- Exit with code 0 if healthy, 1 if issues

**Implementation**:
```python
"""
Health Check Script

Verifies system is running correctly.
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta
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
    conn = await asyncpg.connect(...)

    required_tables = [
        'market_data', 'trades', 'positions', 'trading_signals',
        'strategy_performance', 'agent_status', 'fork_tracking'
    ]

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
            await conn.close()
            return False

    await conn.close()
    return True

async def check_agents():
    """Check agent status"""
    print("\nChecking agent status...")
    config = get_config()
    conn = await asyncpg.connect(...)

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
        elapsed = (datetime.now() - agent['last_heartbeat']).total_seconds()
        print(f"✅ {agent['agent_name']}: {agent['status']} (heartbeat {elapsed:.0f}s ago)")

    await conn.close()
    return True

async def check_activity():
    """Check recent system activity"""
    print("\nChecking recent activity...")
    config = get_config()
    conn = await asyncpg.connect(...)

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
```

**Verification**:
- Run while system is running: `python scripts/health_check.py` → exit 0
- Run while system is stopped → exit 1 (no active agents)

---

## Execution Instructions

### Parallel Execution Strategy

**Agent 1** (Core Infrastructure - no dependencies):
```bash
cd /path/to/project-planner
git checkout -b bugfix-agent1
# Work on Tasks 1.1, 1.2, 1.3, 1.4
git add .
git commit -m "Agent 1: Core infrastructure and entry points"
git push origin bugfix-agent1
```

**Agent 2** (Risk & Events - minimal dependencies):
```bash
cd /path/to/project-planner
git checkout -b bugfix-agent2
# Work on Tasks 2.1, 2.2, 2.3, 2.4
git add .
git commit -m "Agent 2: Risk monitor and event fixes"
git push origin bugfix-agent2
```

**Agent 3** (Schema & Docs - independent):
```bash
cd /path/to/project-planner
git checkout -b bugfix-agent3
# Work on Tasks 3.1, 3.2, 3.3, 3.4, 3.5
git add .
git commit -m "Agent 3: Schema fixes and documentation"
git push origin bugfix-agent3
```

### Integration & Testing

After all 3 agents complete:

1. **Merge all branches**:
```bash
git checkout main
git merge bugfix-agent1
git merge bugfix-agent2
git merge bugfix-agent3
# Resolve any conflicts
```

2. **Run tests**:
```bash
pytest tests/ -v
```

3. **Integration test**:
```bash
# Setup environment
cp .env.example .env
# Edit .env with real credentials

# Initialize database
python scripts/init_db.py

# Run system
python -m src.main

# In another terminal, run health check
python scripts/health_check.py
```

4. **Verify end-to-end**:
- System starts all 7 agents ✅
- Market data streams in ✅
- Strategies generate signals ✅
- Execution agent creates paper trades ✅
- Risk monitor publishes alerts ✅
- Meta-strategy reallocates after 6 hours ✅
- Fork manager creates forks on request ✅

---

## Conflict Resolution

### Potential Conflicts

**Agent 1 + Agent 2** (execution.py):
- Agent 1: Fixes line 219 (database manager)
- Agent 2: Modifies line 98-99 (position sizing) and adds performance tracking

**Resolution**: Accept both changes, they touch different parts.

**Agent 1 + Agent 3** (config/app.yaml):
- Agent 3: Adds `position_exit_pct` and updates existing fields

**Resolution**: Agent 3's changes superset Agent 1's needs.

**Agent 2 + Agent 3** (execution.py):
- Agent 2: Adds performance tracking
- Agent 3: Adds execution safeguards to `__init__`

**Resolution**: Both changes are compatible, merge both.

---

## Success Criteria

After all fixes applied:

- [ ] System starts without errors: `python -m src.main`
- [ ] All 7 agents show "started" in logs
- [ ] Database schema initialized successfully
- [ ] Health check passes: `python scripts/health_check.py`
- [ ] All tests pass: `pytest tests/`
- [ ] Market data streaming: trades, signals appearing in database
- [ ] Risk alerts publish with correct event structure
- [ ] Strategy performance metrics calculated and persisted
- [ ] Documentation complete: README, QUICKSTART, .env.example

**Estimated completion time**: 1 hour parallel → 30 minutes integration → **1.5 hours total**
