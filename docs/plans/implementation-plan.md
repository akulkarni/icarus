# Live Trading System - Implementation Plan

**Project**: Autonomous Live Crypto Trading System
**Timeline**: 3 Days (aggressive schedule)
**Last Updated**: 2025-10-06

---

## Overview

This document provides a comprehensive, task-by-task implementation guide for building the live trading system from scratch. It assumes the engineer has **zero context** about the codebase but is a skilled developer.

### Document Structure

- **This file**: High-level overview, project structure, and daily roadmap
- **Appendices**: Detailed task breakdowns with code, tests, and instructions
  - `implementation-day1-core-mvp.md` - Event bus, database, agents, CLI
  - `implementation-day2-dashboard.md` - Web UI, advanced meta-strategy, PR agent
  - `implementation-day3-production.md` - Real trading, polish, deployment

---

## Key Principles

### Development Philosophy

**DRY (Don't Repeat Yourself)**
- Extract common patterns into base classes
- Reuse existing backtest code (momentum.py, macd.py)
- Share database query logic across agents
- Use inheritance for strategy agents

**YAGNI (You Aren't Gonna Need It)**
- Only implement features in design doc
- No premature optimization
- Start simple: instant fills, no slippage (Phase 1)
- Add complexity when needed (Phase 2+)

**TDD (Test-Driven Development)**
- Write test first → watch it fail
- Write minimal code to pass
- Refactor if needed
- Commit after each passing test

### Commit Discipline

Commit after **every task completion**. Use conventional commits:

```bash
feat: new feature
fix: bug fix
test: adding tests
refactor: code restructuring
docs: documentation
```

Examples:
- `feat(agents): add base agent class with event subscription`
- `test(core): add event bus integration tests`
- `refactor(strategies): extract common indicator calculations`

---

## Prerequisites

### Required Knowledge

Familiarize yourself with these concepts before starting:

#### 1. TimescaleDB
- PostgreSQL extension for time-series data
- **Hypertables**: Auto-partitioned time-series tables
- **Continuous Aggregates**: Pre-computed rollups (like materialized views)
- **Compression**: Automatic compression for old data
- Docs: https://docs.timescale.com/getting-started/latest/

#### 2. Tiger Cloud
- TimescaleDB cloud service
- **Database Forking**: Instant copy-on-write database clones
- Use case: Test/validate without affecting production
- CLI: `tsdb` command for managing services/forks
- Ask user for Tiger Cloud documentation

#### 3. Trading Concepts
- **OHLCV**: Open, High, Low, Close, Volume
- **Paper Trading**: Simulated trading with fake money
- **Position**: Amount of crypto held
- **Signal**: Buy/sell recommendation from strategy
- **Allocation**: % of capital assigned to strategy

#### 4. Python AsyncIO
- `async/await` for concurrent programming
- `asyncio.Queue` for message passing
- `asyncio.create_task()` for running tasks concurrently
- Docs: https://docs.python.org/3/library/asyncio.html

### Environment Setup

**Prerequisites checklist:**
- [ ] Python 3.9+ installed
- [ ] Git configured
- [ ] Tiger Cloud credentials (ask user)
- [ ] Text editor / IDE

**Installation:**

```bash
cd /Users/ajay/code/icarus/project-planner/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (create requirements.txt - see Day 1 appendix)
pip install -r requirements.txt

# Verify installation
python -c "import asyncpg, pandas, binance; print('✓ Dependencies OK')"
```

---

## Project Structure

```
project-planner/
├── config/
│   └── database.yaml          # DB credentials (gitignored)
├── sql/
│   └── schema.sql              # Database schema
├── src/
│   ├── agents/                 # All agent implementations
│   │   ├── base.py            # Base agent class
│   │   ├── market_data.py     # Market Data Agent
│   │   ├── strategy.py        # Strategy Agent base
│   │   ├── strategies/        # Individual strategies
│   │   │   ├── momentum.py
│   │   │   └── macd.py
│   │   ├── meta_strategy.py   # Meta-Strategy Agent
│   │   ├── execution.py       # Trade Execution Agent
│   │   ├── fork_manager.py    # Fork Manager Agent
│   │   ├── risk_monitor.py    # Risk Monitor Agent
│   │   └── pr_agent.py        # PR Agent
│   ├── core/                   # Core infrastructure
│   │   ├── event_bus.py       # Event bus
│   │   ├── database.py        # DB connection management
│   │   └── config.py          # Config utilities
│   ├── models/                 # Data models
│   │   ├── events.py          # Event definitions
│   │   └── trading.py         # Trading data structures
│   └── main.py                 # Entry point
├── tests/                      # All tests
│   ├── conftest.py            # Pytest fixtures
│   ├── test_agents/
│   ├── test_core/
│   └── test_models/
├── docs/plans/                 # Design docs
├── requirements.txt
└── README.md
```

---

## Phase 1: Core MVP (Day 1)

**Goal**: Working end-to-end system with 2 strategies, fork validation, CLI output

### High-Level Tasks

1. **Setup** (1 hour)
   - Create project structure
   - Install dependencies
   - Configure database
   - Deploy schema

2. **Core Infrastructure** (2 hours)
   - Event bus with tests
   - Database manager with tests
   - Data models (events, trading)
   - Config management

3. **Base Agent Framework** (1 hour)
   - Base agent class
   - Lifecycle management
   - Event subscription pattern

4. **Market Data Agent** (1.5 hours)
   - Binance WebSocket integration
   - Price streaming
   - OHLCV data ingestion
   - Tests

5. **Strategy Agents** (2 hours)
   - Base strategy class
   - Momentum strategy (reuse existing)
   - MACD strategy (reuse existing)
   - Signal generation
   - Tests

6. **Trade Execution Agent** (1.5 hours)
   - Paper trading simulation
   - Position management
   - Database persistence
   - Tests

7. **Meta-Strategy Agent** (1 hour)
   - Equal weighting allocation
   - Performance tracking
   - Allocation adjustments

8. **Fork Manager Agent** (2 hours)
   - Tiger Cloud CLI integration
   - Fork creation/destruction
   - Connection management
   - Tests

9. **Risk Monitor Agent** (1 hour)
   - Position limits
   - Daily loss tracking
   - Emergency halt logic

10. **Integration** (1 hour)
    - Main entry point
    - Agent orchestration
    - CLI output
    - End-to-end test

**Total**: ~13 hours (aggressive single day)

### Success Criteria

- [ ] All agents running concurrently
- [ ] Market data streaming from Binance
- [ ] Strategies generating signals
- [ ] Trades executed in paper mode
- [ ] Positions tracked in database
- [ ] Forks created for validation every 6 hours
- [ ] CLI shows real-time activity
- [ ] All tests passing

**Detailed tasks**: See `implementation-day1-core-mvp.md`

---

## Phase 2: Web Dashboard + Intelligence (Day 2)

**Goal**: Add web UI, advanced meta-strategy, PR agent

### High-Level Tasks

1. **Web Backend** (2 hours)
   - FastAPI application
   - REST endpoints
   - WebSocket for real-time updates
   - CORS configuration

2. **Web Frontend** (3 hours)
   - HTML/CSS/JavaScript dashboard
   - Real-time price charts
   - Portfolio display
   - Strategy performance table
   - Fork activity timeline
   - Agent status panel

3. **Advanced Meta-Strategy** (2 hours)
   - Market regime detection
   - Volatility calculation
   - Trend strength analysis
   - Fork-based scenario testing
   - Performance-based allocation

4. **PR Agent** (1.5 hours)
   - Event pattern detection
   - Narrative generation
   - Importance scoring
   - Markdown logging

5. **Additional Strategies** (2 hours)
   - Bollinger Bands strategy
   - Mean Reversion strategy
   - Integration with meta-strategy

6. **Slippage Simulation** (0.5 hours)
   - Add 0.05-0.1% slippage to fills
   - Update execution agent

7. **Testing & Integration** (1 hour)
   - Dashboard tests
   - Integration tests
   - Load testing

**Total**: ~12 hours

### Success Criteria

- [ ] Web dashboard accessible at localhost:8000
- [ ] Real-time updates via WebSocket
- [ ] Fork activity visible on dashboard
- [ ] Meta-strategy uses regime detection
- [ ] PR agent generates narratives
- [ ] 4 strategies operational
- [ ] All tests passing

**Detailed tasks**: See `implementation-day2-dashboard.md`

---

## Phase 3: Production Ready (Day 3)

**Goal**: Real trading mode, polish, deployment

### High-Level Tasks

1. **Real Trading Mode** (2 hours)
   - Binance API key integration
   - Real order execution
   - Order tracking
   - Error handling

2. **Enhanced Risk Monitor** (1 hour)
   - Circuit breakers
   - Correlation checks
   - Drawdown tracking
   - Real-time alerts

3. **Parameter Optimization** (2 hours)
   - Multi-fork parallel testing
   - Parameter grid search
   - Best parameter selection

4. **Dashboard Enhancements** (2 hours)
   - Fork lifecycle visualization
   - Performance charts
   - PR feed display
   - Export functionality

5. **Remaining Strategies** (1.5 hours)
   - Breakout strategy
   - Stochastic strategy
   - Full integration

6. **Documentation** (1 hour)
   - User guide
   - API documentation
   - Demo script

7. **Deployment** (1.5 hours)
   - Environment configuration
   - Systemd service
   - Logging setup
   - Monitoring

8. **Testing & Showcase** (1 hour)
   - End-to-end tests
   - Demo preparation
   - Performance tuning

**Total**: ~12 hours

### Success Criteria

- [ ] Real trading mode functional
- [ ] All 6 strategies operational
- [ ] Enhanced risk controls active
- [ ] Dashboard polished and complete
- [ ] Parameter optimization working
- [ ] Documentation complete
- [ ] System ready for demo

**Detailed tasks**: See `implementation-day3-production.md`

---

## Testing Strategy

### Test Types

**Unit Tests**
- Test individual functions/methods
- Mock external dependencies
- Fast execution (<1s per test)
- Run on every commit

**Integration Tests**
- Test component interactions
- Use test database
- Medium speed (1-5s per test)
- Run before commits

**End-to-End Tests**
- Test entire system
- Real database (test instance)
- Slow (10-30s per test)
- Run before phase completion

### Test Coverage Goals

- Core infrastructure: >90%
- Agents: >80%
- Web API: >70%
- Overall: >80%

### Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_agents/test_strategy.py -v

# With coverage
pytest --cov=src --cov-report=html

# Fast tests only
pytest -m "not slow"

# Integration tests
pytest -m integration
```

### Test Organization

```python
# tests/conftest.py - Shared fixtures

import pytest
import asyncio
from src.core.event_bus import EventBus
from src.core.database import DatabaseManager

@pytest.fixture
def event_bus():
    """Fresh event bus for each test"""
    bus = EventBus()
    yield bus
    asyncio.run(bus.close())

@pytest.fixture
async def db_manager():
    """Test database manager"""
    db = DatabaseManager(config_path='config/test_database.yaml')
    await db.initialize()
    yield db
    await db.close()
```

---

## Common Patterns

### Agent Structure

All agents follow this pattern:

```python
from src.agents.base import BaseAgent
from src.models.events import SomeEvent

class MyAgent(BaseAgent):
    def __init__(self, event_bus):
        super().__init__("my_agent", event_bus)
        # Agent-specific initialization

    async def start(self):
        """Start agent event loop"""
        # Subscribe to events
        queue = self.event_bus.subscribe(SomeEvent)

        # Event processing loop
        async for event in self._consume_events(queue):
            await self._handle_event(event)

    async def _handle_event(self, event):
        """Process event"""
        # Agent logic here

        # Publish response event
        response = AnotherEvent(...)
        await self.publish(response)
```

### Database Operations

```python
# Get connection
db = get_db_manager()
conn = await db.get_connection()

try:
    # Execute query
    result = await conn.fetch(
        "SELECT * FROM trades WHERE strategy_name = $1",
        strategy_name
    )

    # Insert data
    await conn.execute(
        """
        INSERT INTO trades (time, strategy_name, symbol, side, quantity, price, ...)
        VALUES ($1, $2, $3, $4, $5, $6, ...)
        """,
        time, strategy_name, symbol, side, quantity, price, ...
    )

finally:
    # Always release connection
    await db.release_connection(conn)
```

### Event Publishing

```python
# Create event
event = MarketTickEvent(
    symbol='BTC/USDT',
    price=Decimal('50000'),
    volume=Decimal('100')
)

# Publish (non-blocking)
await self.event_bus.publish(event)
```

### Error Handling

```python
import logging

logger = logging.getLogger(__name__)

try:
    # Risky operation
    result = await some_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    # Publish error event for other agents
    await self.publish(ErrorEvent(...))
except Exception as e:
    logger.exception("Unexpected error")
    # Don't crash agent - continue processing
```

---

## Configuration Management

### Database Config

**File**: `config/database.yaml` (gitignored)

```yaml
production:
  host: "YOUR_HOST.tsdb.cloud.timescale.com"
  port: 34170
  database: "tsdb"
  user: "tsdbadmin"
  password: "YOUR_PASSWORD"

test:
  host: "localhost"
  port: 5432
  database: "trading_test"
  user: "testuser"
  password: "testpass"
```

### Application Config

**File**: `config/app.yaml`

```yaml
trading:
  initial_capital: 10000
  symbols:
    - "BTC/USDT"
    - "ETH/USDT"
  trade_mode: "paper"  # or "real"

risk:
  max_position_pct: 20  # 20% of allocated capital
  max_exposure_pct: 80   # 80% of portfolio
  max_daily_loss_pct: 5  # 5% daily loss limit
  strategy_drawdown_pct: 10  # 10% strategy drawdown

meta_strategy:
  evaluation_interval_hours: 6
  initial_allocation: "equal"  # or "performance"

fork_manager:
  max_concurrent_forks: 10
  default_ttl_hours: 24
  cleanup_interval_minutes: 30

agents:
  market_data:
    update_interval_seconds: 1
  strategies:
    validation_interval_hours: 6
  risk_monitor:
    check_interval_seconds: 5
```

---

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Make sure you're in project root
cd /Users/ajay/code/icarus/project-planner/

# Activate venv
source venv/bin/activate

# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

**Database Connection Failed**
- Check credentials in `config/database.yaml`
- Verify network connectivity
- Test with: `psql "postgresql://..."`

**Tests Failing**
- Check test database is running
- Verify fixtures in `conftest.py`
- Run with `-v` for verbose output
- Check test logs

**Agent Not Receiving Events**
- Verify event subscription before publishing
- Check event type matches exactly
- Add logging to event bus
- Verify agent's event loop is running

---

## Git Workflow

### Branch Strategy

```bash
# Work on main branch for this project
git checkout main

# For each day, create commits frequently
# After Day 1:
git add .
git commit -m "feat: complete Phase 1 - Core MVP"
git push

# After Day 2:
git add .
git commit -m "feat: complete Phase 2 - Web Dashboard"
git push

# After Day 3:
git add .
git commit -m "feat: complete Phase 3 - Production Ready"
git push
```

### Commit Messages

Good:
- `feat(agents): add momentum strategy with MA crossover logic`
- `test(execution): add paper trading simulation tests`
- `fix(database): handle connection pool exhaustion`
- `refactor(strategies): extract common indicator calculations`

Bad:
- `fixed stuff`
- `updates`
- `wip`

---

## Next Steps

Ready to start implementation?

1. **Read the design doc**: `docs/plans/live-trading-system-design.md`
2. **Start with Day 1**: Open `docs/plans/implementation-day1-core-mvp.md`
3. **Follow task by task**: Each task has code, tests, and verification steps
4. **Commit frequently**: After each passing test
5. **Ask questions**: If anything is unclear

**Estimated timeline**:
- Day 1: 10-13 hours
- Day 2: 10-12 hours
- Day 3: 10-12 hours

**Good luck! 🚀**

---

## Appendices

Detailed task-by-task implementation guides:

- **[Day 1: Core MVP](implementation-day1-core-mvp.md)** - Event bus, database, agents, CLI
- **[Day 2: Web Dashboard](implementation-day2-dashboard.md)** - Web UI, intelligence, PR agent
- **[Day 3: Production](implementation-day3-production.md)** - Real trading, polish, deployment
