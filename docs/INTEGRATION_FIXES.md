# Integration Fixes - Single Agent Assignment

## Overview
9 integration issues to fix, all in existing files. These are interface mismatches between components developed in parallel.

**Estimated Time**: 30 minutes
**Branch**: `bugfix-integration`

---

## Fix 1: Strategy Constructor Signatures (CRITICAL)

**Files**:
- `src/agents/strategies/momentum.py`
- `src/agents/strategies/macd.py`

**Problem**: Strategies don't accept config parameters that main.py tries to pass.

**Fix**: Update both strategy constructors to accept config parameters:

### src/agents/strategies/momentum.py

```python
# Change line 17 from:
def __init__(self, event_bus, symbol: str = 'BTCUSDT'):

# To:
def __init__(self, event_bus, symbol: str = 'BTCUSDT',
             ma_short: int = 20, ma_long: int = 50, warmup_period: int = 50):
    params = {
        'ma_short': ma_short,      # Use parameter instead of hardcoded 20
        'ma_long': ma_long,        # Use parameter instead of hardcoded 50
        'warmup_period': warmup_period,  # Use parameter instead of hardcoded 50
        'max_history': 200
    }
    super().__init__('momentum', event_bus, symbol, params)
    self.previous_signal = None
```

### src/agents/strategies/macd.py

```python
# Change line 17 from:
def __init__(self, event_bus, symbol: str = 'BTCUSDT'):

# To:
def __init__(self, event_bus, symbol: str = 'BTCUSDT',
             fast_period: int = 12, slow_period: int = 26,
             signal_period: int = 9, warmup_period: int = 50):
    params = {
        'fast_period': fast_period,      # Use parameter instead of hardcoded 12
        'slow_period': slow_period,      # Use parameter instead of hardcoded 26
        'signal_period': signal_period,  # Use parameter instead of hardcoded 9
        'warmup_period': warmup_period,  # Use parameter instead of hardcoded 50
        'max_history': 200
    }
    super().__init__('macd', event_bus, symbol, params)
    self.previous_signal = None
```

**Verification**:
```python
# Test import
from src.agents.strategies.momentum import MomentumStrategy
from src.core.event_bus import EventBus
eb = EventBus()
strategy = MomentumStrategy(eb, 'BTCUSDT', ma_short=20, ma_long=50, warmup_period=50)
print(f"✅ MomentumStrategy accepts config params: {strategy.params}")
```

---

## Fix 2: RiskMonitorAgent Constructor Call (CRITICAL)

**File**: `src/main.py`

**Problem**: main.py passes individual parameters, but RiskMonitorAgent expects config dict.

**Fix**: Change lines 140-151

```python
# Change from:
risk_monitor_agent = RiskMonitorAgent(
    self.event_bus,
    initial_capital=initial_capital,
    max_position_size_pct=risk_config['max_position_size_pct'],
    max_daily_loss_pct=risk_config['max_daily_loss_pct'],
    max_exposure_pct=risk_config['max_exposure_pct'],
    max_strategy_drawdown_pct=risk_config['max_strategy_drawdown_pct']
)

# To:
risk_monitor_agent = RiskMonitorAgent(
    self.event_bus,
    config=risk_config,  # Pass entire config dict
    initial_portfolio_value=initial_capital  # Use correct parameter name
)
```

**Verification**:
```python
# Check RiskMonitorAgent signature
from src.agents.risk_monitor import RiskMonitorAgent
import inspect
sig = inspect.signature(RiskMonitorAgent.__init__)
print(f"✅ RiskMonitorAgent signature: {sig}")
# Should show: (self, event_bus, config: Dict, initial_portfolio_value: Decimal = Decimal('10000'))
```

---

## Fix 3: MetaStrategyAgent Strategy Names (CRITICAL)

**File**: `src/main.py`

**Problem**: MetaStrategyAgent receives agent objects but expects list of strategy names.

**Fix**: Change lines 79-127 to build list of strategy names:

```python
# After line 78 (inside _create_agents method):
# 1. Market Data Agent
symbols = config['trading']['symbols']
market_data_agent = MarketDataAgent(self.event_bus, symbols)
self.agents.append(market_data_agent)
logger.info(f"  - MarketDataAgent created for symbols: {symbols}")

# 2. Strategy Agents
strategy_names = []  # ✅ Add this line to collect strategy names

# Momentum Strategy
if config['strategies']['momentum']['enabled']:
    momentum_strategy = MomentumStrategy(
        self.event_bus,
        symbol=config['strategies']['momentum']['symbol'],
        ma_short=config['strategies']['momentum']['ma_short'],
        ma_long=config['strategies']['momentum']['ma_long'],
        warmup_period=config['strategies']['momentum']['warmup_period']
    )
    self.agents.append(momentum_strategy)
    strategy_names.append('momentum')  # ✅ Add name to list
    logger.info("  - MomentumStrategy created")

# MACD Strategy
if config['strategies']['macd']['enabled']:
    macd_strategy = MACDStrategy(
        self.event_bus,
        symbol=config['strategies']['macd']['symbol'],
        fast_period=config['strategies']['macd']['fast_period'],
        slow_period=config['strategies']['macd']['slow_period'],
        signal_period=config['strategies']['macd']['signal_period'],
        warmup_period=config['strategies']['macd']['warmup_period']
    )
    self.agents.append(macd_strategy)
    strategy_names.append('macd')  # ✅ Add name to list
    logger.info("  - MACDStrategy created")

# 3. Execution Agent
initial_capital = Decimal(str(config['trading']['initial_capital']))
execution_agent = ExecutionAgent(
    self.event_bus,
    initial_capital=initial_capital,
    config=config
)
self.agents.append(execution_agent)
logger.info(f"  - ExecutionAgent created (capital: ${initial_capital})")

# 4. Meta-Strategy Agent
meta_strategy_agent = MetaStrategyAgent(
    self.event_bus,
    strategies=strategy_names,  # ✅ Changed: pass string list, not agent objects
    evaluation_interval_hours=config['meta_strategy']['evaluation_interval_hours']
)
self.agents.append(meta_strategy_agent)
logger.info("  - MetaStrategyAgent created")

# ... rest stays the same
```

**Verification**:
```python
# Check that strategy_names is list of strings
print(f"Strategy names: {strategy_names}")
# Should print: ['momentum', 'macd']
assert all(isinstance(name, str) for name in strategy_names), "All should be strings"
```

---

## Fix 4: Performance Tracking Database Manager (HIGH PRIORITY)

**File**: `src/agents/execution.py`

**Problem**: Uses `get_db_manager()` without await.

**Fix**: Change line 293

```python
# Change from:
db = get_db_manager()

# To:
db = get_db_manager_sync()
```

**Verification**:
```bash
# Search for get_db_manager() usage without await
grep -n "get_db_manager()" src/agents/execution.py
# Should show no results (all should be get_db_manager_sync())
```

---

## Fix 5: Integrate Logging Setup (HIGH PRIORITY)

**File**: `src/main.py`

**Problem**: Logging setup module exists but isn't used.

**Fix**: Replace lines 210-217 with proper logging setup:

```python
# Change from:
async def main():
    """Main entry point"""
    # Basic logging setup (will be enhanced by logging_setup.py later)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)8s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    system = IcarusSystem()

# To:
async def main():
    """Main entry point"""
    # Load configuration first
    from src.core.config import load_config
    from src.core.logging_setup import setup_logging

    config = load_config()
    setup_logging(config)

    system = IcarusSystem()
```

**Also update** IcarusSystem.initialize() to not reload config (line 44-47):

```python
# Change from:
async def initialize(self):
    """Initialize system components"""
    logger.info("=" * 80)
    logger.info("ICARUS TRADING SYSTEM - INITIALIZING")
    logger.info("=" * 80)

    # Load configuration
    logger.info("Loading configuration...")
    self.config = load_config()
    logger.info("Configuration loaded")

# To:
async def initialize(self):
    """Initialize system components"""
    logger.info("=" * 80)
    logger.info("ICARUS TRADING SYSTEM - INITIALIZING")
    logger.info("=" * 80)

    # Load configuration (if not already loaded)
    if self.config is None:
        logger.info("Loading configuration...")
        self.config = load_config()
        logger.info("Configuration loaded")
```

**And update** main() to pass config to system (after line 232):

```python
# Change from:
    system = IcarusSystem()

    # Setup signal handlers
    # ... (signal handlers)

    try:
        # Initialize system
        await system.initialize()

# To:
    system = IcarusSystem()
    system.config = config  # ✅ Pass config loaded in main()

    # Setup signal handlers
    # ... (signal handlers)

    try:
        # Initialize system
        await system.initialize()
```

**Verification**:
```bash
# Check that logging setup is imported
grep -n "from src.core.logging_setup import setup_logging" src/main.py
# Should show the import line

# Run and check logs directory created
python -m src.main &
sleep 2
ls -la logs/
# Should show icarus.log file
```

---

## Fix 6: Agent Run vs Start (MEDIUM PRIORITY)

**File**: `src/main.py`

**Problem**: Calling `agent.start()` instead of `agent.run()`.

**Fix**: Change line 163

```python
# Change from:
tasks.append(asyncio.create_task(agent.start()))

# To:
tasks.append(asyncio.create_task(agent.run()))
```

**Why**: `run()` provides lifecycle management (startup event, heartbeat, cleanup), while `start()` is the abstract method that subclasses implement.

**Verification**:
```bash
# Check that we're calling .run()
grep -n "agent.run()" src/main.py
# Should show line 163 with agent.run()
```

---

## Fix 7: QUICKSTART Directory Name (MEDIUM PRIORITY)

**File**: `docs/QUICKSTART.md`

**Problem**: References wrong directory name.

**Fix**: Change line 11

```python
# Change from:
cd worker-agent-3

# To:
cd project-planner
```

**Verification**:
```bash
# Check file references correct directory
grep -n "cd project-planner" docs/QUICKSTART.md
# Should show line 11
```

---

## Fix 8: README Agent Count (LOW PRIORITY)

**File**: `README.md`

**Problem**: Says "7 autonomous agents" but only lists 6.

**Fix**: Change line 34 and update list:

```markdown
# Change from:
The Icarus Trading System consists of 7 autonomous agents:

1. **Market Data Agent** - Streams real-time market data
2. **Strategy Agents** - Generate trading signals (Momentum, MACD)
3. **Execution Agent** - Executes trades and manages positions
4. **Meta-Strategy Agent** - Dynamically allocates capital across strategies
5. **Risk Monitor Agent** - Enforces risk limits and emergency halts
6. **Fork Manager Agent** - Creates database forks for backtesting

# To:
The Icarus Trading System consists of 6 autonomous agents:

1. **Market Data Agent** - Streams real-time market data from Binance
2. **Momentum Strategy Agent** - Moving average crossover signals
3. **MACD Strategy Agent** - MACD indicator signals
4. **Execution Agent** - Executes trades and manages positions
5. **Meta-Strategy Agent** - Dynamically allocates capital across strategies
6. **Risk Monitor Agent** - Enforces risk limits and emergency halts
7. **Fork Manager Agent** - Creates database forks for backtesting

*Note: PR Agent (narrative generation) will be added in Day 2.*
```

**Verification**:
```bash
# Count agents listed in README
grep -c "**.*Agent**" README.md
# Should show 7
```

---

## Fix 9: Health Check Timezone (LOW PRIORITY)

**File**: `scripts/health_check.py`

**Problem**: Assumes last_heartbeat has timezone info.

**Fix**: Change line 106

```python
# Change from:
elapsed = (datetime.now(agent['last_heartbeat'].tzinfo) - agent['last_heartbeat']).total_seconds()

# To:
from datetime import timezone
# ... at top of file

# Then at line 106:
now = datetime.now(timezone.utc)
elapsed = (now - agent['last_heartbeat']).total_seconds()
```

**Full context** (add import at top):

```python
# At top of file (line 8), change:
from datetime import datetime, timedelta

# To:
from datetime import datetime, timedelta, timezone
```

**Verification**:
```python
# Test timezone handling
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
print(f"✅ UTC time: {now}")
```

---

## Execution Instructions

### Setup
```bash
cd /path/to/project-planner
git checkout -b bugfix-integration
```

### Apply Fixes
Work through fixes 1-9 in order. Each fix includes:
- Exact file location
- Exact line numbers or search patterns
- Complete "change from/to" code
- Verification command

### Testing After Each Fix
Run verification command provided for each fix.

### Final Integration Test
```bash
# 1. Check imports
python -c "from src.main import IcarusSystem; print('✅ Imports work')"

# 2. Check strategy constructors
python -c "
from src.agents.strategies.momentum import MomentumStrategy
from src.core.event_bus import EventBus
eb = EventBus()
s = MomentumStrategy(eb, 'BTCUSDT', ma_short=20, ma_long=50, warmup_period=50)
print('✅ MomentumStrategy constructor works')
"

# 3. Check RiskMonitorAgent
python -c "
from src.agents.risk_monitor import RiskMonitorAgent
from src.core.event_bus import EventBus
from decimal import Decimal
eb = EventBus()
config = {'max_position_size_pct': 20, 'max_daily_loss_pct': 5, 'max_exposure_pct': 80, 'max_strategy_drawdown_pct': 10}
r = RiskMonitorAgent(eb, config=config, initial_portfolio_value=Decimal('10000'))
print('✅ RiskMonitorAgent constructor works')
"

# 4. Test full system startup (dry run)
python -c "
import asyncio
from src.main import IcarusSystem
async def test():
    system = IcarusSystem()
    print('✅ IcarusSystem instantiates')
asyncio.run(test())
"
```

### Commit and Push
```bash
git add -A
git commit -m "Fix integration issues from parallel development

- Fix strategy constructor signatures to accept config params
- Fix RiskMonitorAgent constructor call in main.py
- Fix MetaStrategyAgent to receive strategy names not objects
- Fix database manager usage in performance tracking
- Integrate logging setup into main.py
- Change agent.start() to agent.run() for proper lifecycle
- Fix directory name in QUICKSTART.md
- Correct agent count in README.md
- Fix timezone handling in health_check.py

All 9 integration issues resolved. System ready to run."

git push origin bugfix-integration
```

### Merge to Main
```bash
git checkout main
git merge bugfix-integration --no-edit
git push origin main
```

---

## Verification Checklist

After all fixes applied:

- [ ] All imports work: `python -c "from src.main import IcarusSystem"`
- [ ] Strategy constructors accept config params
- [ ] RiskMonitorAgent constructor signature matches
- [ ] MetaStrategyAgent receives string list
- [ ] No `get_db_manager()` without await in execution.py
- [ ] Logging setup integrated in main.py
- [ ] All agent.run() calls in main.py
- [ ] QUICKSTART.md references correct directory
- [ ] README lists 7 agents correctly
- [ ] Health check has timezone import

### Full System Test
```bash
# 1. Initialize database
python scripts/init_db.py

# 2. Start system
python -m src.main

# Expected output:
# ================================================================================
# ICARUS TRADING SYSTEM - INITIALIZING
# ================================================================================
# ...
# Starting agent: market_data
# Starting agent: momentum
# Starting agent: macd
# Starting agent: execution
# Starting agent: meta_strategy
# Starting agent: fork_manager
# Starting agent: risk_monitor
# (no errors)

# 3. In another terminal, health check
python scripts/health_check.py

# Expected:
# ✅ Connected to database
# ✅ All tables exist
# ✅ All 6 agents running
# ✅ Market ticks streaming
```

---

## Success Criteria

✅ All 9 fixes applied
✅ No import errors
✅ All verification commands pass
✅ System starts without errors
✅ All 6 agents show "running" status
✅ Health check passes
✅ Market data streaming
✅ No exceptions in logs

**Estimated completion time: 30 minutes**
