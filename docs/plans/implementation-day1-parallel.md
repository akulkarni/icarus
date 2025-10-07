# Day 1: Parallel Implementation Strategy

**Goal**: Complete Day 1 MVP with 3 agents working in parallel
**Duration**: ~5 hours (vs 13 hours sequential)
**Method**: 3 separate git worktrees, coordinated integration points

---

## Overview

Day 1 tasks can be split into 3 independent workstreams that converge at integration points:

- **Agent 1 (Foundation)**: Core infrastructure - Event bus, database, models
- **Agent 2 (Data & Trading)**: Market data, strategies, execution
- **Agent 3 (Intelligence)**: Meta-strategy, fork manager, risk monitor

### Dependency Flow

```
Time →

Agent 1: [Setup → Models → Event Bus → Database] ────────────→ [Integration]
                                                    ↓
Agent 2: [Wait for models] → [Market Data → Strategies → Execution] → [Integration]
                                                    ↓
Agent 3: [Wait for models] → [Meta-Strategy → Fork Mgr → Risk] ────→ [Integration]
```

---

## Worktree Setup

Create 3 separate worktrees so agents don't conflict:

```bash
cd /Users/ajay/code/icarus

# Create worktrees
git worktree add project-planner-agent1 -b day1-agent1
git worktree add project-planner-agent2 -b day1-agent2
git worktree add project-planner-agent3 -b day1-agent3

# Agents work in their respective directories:
# Agent 1: /Users/ajay/code/icarus/project-planner-agent1
# Agent 2: /Users/ajay/code/icarus/project-planner-agent2
# Agent 3: /Users/ajay/code/icarus/project-planner-agent3
```

---

## Agent 1: Foundation (Lead)

**Working Directory**: `project-planner-agent1`
**Duration**: ~4 hours
**Role**: Build core infrastructure that other agents depend on

### Phase 1A: Setup & Models (1.5 hours)

**Tasks**:
- **1.1**: Environment setup (all 3 agents can do this simultaneously)
  - Create directory structure
  - Install dependencies
  - Configure database credentials
  - Git: `feat(setup): initialize project structure and dependencies`

- **1.2**: Database schema deployment
  - Create `sql/schema.sql` (800+ lines)
  - Deploy to Tiger Cloud
  - Verify tables created
  - Git: `feat(db): add database schema with hypertables`

- **1.3**: Event models (`src/models/events.py`)
  - All 20+ event types
  - Full tests
  - Git: `feat(models): add event type definitions`

- **1.4**: Trading models (`src/models/trading.py`)
  - Position, Trade, Portfolio classes
  - Full tests
  - Git: `feat(models): add trading data models`

**Commit and push** after 1.4 completes - this unblocks Agent 2 & 3!

### Phase 1B: Core Infrastructure (2.5 hours)

**Tasks**:
- **1.5**: Event bus (`src/core/event_bus.py`)
  - AsyncIO Queue-based pub/sub
  - Full tests
  - Git: `feat(core): implement event bus`

- **1.6**: Database manager (`src/core/database.py`)
  - Connection pooling
  - Fork connection management
  - Full tests
  - Git: `feat(core): add database connection manager`

- **1.7**: Base agent class (`src/agents/base.py`)
  - Abstract base class
  - Lifecycle management
  - Full tests
  - Git: `feat(agents): add base agent class`

**Commit and push** - core infrastructure complete!

### Deliverables

```
src/
├── models/
│   ├── events.py        ✓
│   └── trading.py       ✓
├── core/
│   ├── event_bus.py     ✓
│   ├── database.py      ✓
│   └── config.py        ✓
└── agents/
    └── base.py          ✓

tests/
├── test_models/         ✓
└── test_core/           ✓

sql/schema.sql           ✓
config/                  ✓
```

---

## Agent 2: Data & Trading

**Working Directory**: `project-planner-agent2`
**Duration**: ~4 hours
**Role**: Market data ingestion and trading execution

### Phase 2A: Wait for Foundation (poll every 15 min)

Check if Agent 1 has pushed:
```bash
git fetch origin
git log origin/day1-agent1 --oneline | grep "feat(models): add trading data models"
```

Once available:
```bash
# Merge Agent 1's work
git merge origin/day1-agent1
```

### Phase 2B: Market Data Agent (1.5 hours)

**Task 1.8**: Market Data Agent

**File**: `src/agents/market_data.py`

```python
"""
Market Data Agent

Streams real-time price data from Binance WebSocket.
Publishes MarketTickEvent for each price update.
"""
import asyncio
import logging
from decimal import Decimal
from binance import AsyncClient, BinanceSocketManager
from src.agents.base import BaseAgent
from src.models.events import MarketTickEvent, OHLCVEvent
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class MarketDataAgent(BaseAgent):
    """
    Streams live market data from Binance.

    Publishes:
    - MarketTickEvent: Real-time price updates
    - OHLCVEvent: Aggregated OHLCV candles
    """

    def __init__(self, event_bus, symbols: list[str]):
        super().__init__("market_data", event_bus)
        self.symbols = symbols  # e.g., ['BTCUSDT', 'ETHUSDT']
        self.client = None
        self.bm = None

    async def start(self):
        """Start streaming market data"""
        logger.info(f"Starting market data for {self.symbols}")

        # Initialize Binance client (no API key needed for market data)
        self.client = await AsyncClient.create()
        self.bm = BinanceSocketManager(self.client)

        # Create tasks for each symbol
        tasks = [self._stream_symbol(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks)

    async def _stream_symbol(self, symbol: str):
        """Stream ticker data for a symbol"""
        # Use ticker stream for real-time price updates
        ts = self.bm.symbol_ticker_socket(symbol)

        async with ts as tscm:
            while True:
                msg = await tscm.recv()

                if msg:
                    # Parse Binance ticker message
                    event = MarketTickEvent(
                        symbol=symbol,
                        price=Decimal(msg['c']),  # Last price
                        volume=Decimal(msg['v'])  # 24h volume
                    )

                    # Publish to event bus
                    await self.publish(event)

                    # Also persist to database
                    await self._persist_tick(event)

    async def _persist_tick(self, event: MarketTickEvent):
        """Save tick to database"""
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            await conn.execute("""
                INSERT INTO market_data (time, symbol, price, volume)
                VALUES (NOW(), $1, $2, $3)
            """, event.symbol, event.price, event.volume)
        except Exception as e:
            logger.error(f"Failed to persist tick: {e}")
        finally:
            await db.release_connection(conn)

    async def stop(self):
        """Cleanup"""
        if self.client:
            await self.client.close_connection()
        logger.info("Market data agent stopped")
```

**Test**: `tests/test_agents/test_market_data.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.market_data import MarketDataAgent
from src.core.event_bus import EventBus
from src.models.events import MarketTickEvent

@pytest.mark.asyncio
async def test_market_data_publishes_events():
    """Test that market data agent publishes tick events"""
    event_bus = EventBus()
    agent = MarketDataAgent(event_bus, ['BTCUSDT'])

    # Subscribe to events
    queue = event_bus.subscribe(MarketTickEvent)

    # Mock Binance stream
    with patch('src.agents.market_data.AsyncClient.create') as mock_client:
        # Simulate receiving ticker data
        # ... test implementation
        pass

@pytest.mark.asyncio
async def test_market_data_persists_to_db():
    """Test that ticks are saved to database"""
    # ... test implementation
    pass
```

**Git**: `feat(agents): add Market Data Agent with Binance streaming`

### Phase 2C: Strategy Agents (2 hours)

**Task 1.9**: Strategy base class and concrete strategies

**File**: `src/agents/strategy.py`

```python
"""
Base Strategy Agent

All trading strategies inherit from this class.
Provides common functionality for signal generation.
"""
import logging
from abc import abstractmethod
from decimal import Decimal
import pandas as pd
from src.agents.base import BaseAgent
from src.models.events import MarketTickEvent, TradingSignalEvent

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    Base class for all trading strategies.

    Subclasses implement analyze() method to generate signals.
    """

    def __init__(self, name: str, event_bus, symbol: str, params: dict):
        super().__init__(name, event_bus)
        self.symbol = symbol
        self.params = params
        self.price_history = []  # Store recent prices
        self.max_history = params.get('max_history', 200)

    async def start(self):
        """Start strategy event loop"""
        # Subscribe to market data
        queue = self.event_bus.subscribe(MarketTickEvent)

        async for event in self._consume_events(queue):
            if event.symbol == self.symbol:
                await self._handle_tick(event)

    async def _handle_tick(self, tick: MarketTickEvent):
        """Process price update"""
        # Add to history
        self.price_history.append({
            'time': tick.timestamp,
            'price': float(tick.price),
            'volume': float(tick.volume)
        })

        # Keep only recent history
        if len(self.price_history) > self.max_history:
            self.price_history.pop(0)

        # Need minimum history before analyzing
        if len(self.price_history) < self.params.get('warmup_period', 50):
            return

        # Run strategy analysis
        signal = await self.analyze()

        if signal:
            await self.publish(signal)

    @abstractmethod
    async def analyze(self) -> TradingSignalEvent | None:
        """
        Analyze price data and generate signal.

        Returns:
            TradingSignalEvent if signal generated, None otherwise
        """
        pass

    def get_prices_df(self) -> pd.DataFrame:
        """Get price history as DataFrame"""
        return pd.DataFrame(self.price_history)
```

**File**: `src/agents/strategies/momentum.py`

Reuse logic from `backtest_momentum.py`:

```python
"""
Momentum Strategy

Uses 20-period and 50-period moving averages.
- Buy when 20MA crosses above 50MA
- Sell when 20MA crosses below 50MA
"""
import pandas as pd
from decimal import Decimal
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


class MomentumStrategy(StrategyAgent):
    """Moving average crossover strategy"""

    def __init__(self, event_bus, symbol: str = 'BTCUSDT'):
        params = {
            'ma_short': 20,
            'ma_long': 50,
            'warmup_period': 50,
            'max_history': 200
        }
        super().__init__('momentum', event_bus, symbol, params)
        self.previous_signal = None

    async def analyze(self) -> TradingSignalEvent | None:
        """Generate signal based on MA crossover"""
        df = self.get_prices_df()

        # Calculate moving averages
        df['ma20'] = df['price'].rolling(window=20).mean()
        df['ma50'] = df['price'].rolling(window=50).mean()

        # Get current values
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Detect crossover
        current_signal = 'buy' if current['ma20'] > current['ma50'] else 'sell'
        previous_signal = 'buy' if previous['ma20'] > previous['ma50'] else 'sell'

        # Signal on crossover
        if current_signal != previous_signal:
            return TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side=current_signal,
                confidence=0.7,
                reason=f"MA crossover: 20MA {'above' if current_signal == 'buy' else 'below'} 50MA"
            )

        return None
```

**File**: `src/agents/strategies/macd.py`

Reuse logic from `backtest_macd.py` (similar structure).

**Tests**: Create tests for both strategies.

**Git**: `feat(strategies): add Momentum and MACD strategies`

### Phase 2D: Trade Execution Agent (1 hour)

**Task 1.10**: Trade Execution Agent

**File**: `src/agents/execution.py`

```python
"""
Trade Execution Agent

Executes trades in paper trading mode.
Manages positions and persists to database.
"""
import logging
from decimal import Decimal
from datetime import datetime
from src.agents.base import BaseAgent
from src.models.events import TradingSignalEvent, TradeExecutedEvent, AllocationEvent
from src.models.trading import Position, Trade
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class TradeExecutionAgent(BaseAgent):
    """
    Executes trades based on signals.

    Paper trading mode: simulates fills instantly at market price.
    """

    def __init__(self, event_bus, initial_capital: Decimal = Decimal('10000')):
        super().__init__("execution", event_bus)
        self.initial_capital = initial_capital
        self.strategy_portfolios = {}  # strategy_name -> {cash, positions}
        self.current_allocations = {}  # strategy_name -> allocation_pct
        self.current_prices = {}  # symbol -> last price

    async def start(self):
        """Start execution agent"""
        # Subscribe to signals and allocation events
        signal_queue = self.event_bus.subscribe(TradingSignalEvent)
        allocation_queue = self.event_bus.subscribe(AllocationEvent)
        market_queue = self.event_bus.subscribe(MarketTickEvent)

        # Run event loops concurrently
        await asyncio.gather(
            self._process_signals(signal_queue),
            self._process_allocations(allocation_queue),
            self._track_prices(market_queue)
        )

    async def _process_signals(self, queue):
        """Process trading signals"""
        async for signal in self._consume_events(queue):
            await self._execute_signal(signal)

    async def _execute_signal(self, signal: TradingSignalEvent):
        """Execute a trading signal"""
        # Check if strategy has allocation
        allocation = self.current_allocations.get(signal.strategy_name, 0)
        if allocation == 0:
            logger.debug(f"Strategy {signal.strategy_name} has 0% allocation, skipping signal")
            return

        # Get strategy portfolio
        if signal.strategy_name not in self.strategy_portfolios:
            # Initialize portfolio
            allocated_capital = self.initial_capital * (Decimal(str(allocation)) / 100)
            self.strategy_portfolios[signal.strategy_name] = {
                'cash': allocated_capital,
                'positions': {}
            }

        portfolio = self.strategy_portfolios[signal.strategy_name]

        # Execute based on signal
        if signal.side == 'buy':
            await self._execute_buy(signal, portfolio)
        else:  # sell
            await self._execute_sell(signal, portfolio)

    async def _execute_buy(self, signal, portfolio):
        """Execute buy order (paper trading)"""
        # Use 20% of available cash (position sizing)
        cash_to_use = portfolio['cash'] * Decimal('0.2')

        if cash_to_use < 10:  # Minimum order size
            logger.warning(f"Insufficient cash for {signal.symbol}")
            return

        # Get current price
        price = self.current_prices.get(signal.symbol)
        if not price:
            logger.warning(f"No price data for {signal.symbol}")
            return

        # Calculate quantity and fee
        quantity = cash_to_use / price
        fee = quantity * price * Decimal('0.001')  # 0.1% fee

        # Update portfolio
        portfolio['cash'] -= (quantity * price + fee)

        if signal.symbol not in portfolio['positions']:
            portfolio['positions'][signal.symbol] = Decimal('0')
        portfolio['positions'][signal.symbol] += quantity

        # Persist trade
        await self._persist_trade(Trade(
            id=None,
            time=datetime.now(),
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side='buy',
            quantity=quantity,
            price=price,
            fee=fee,
            trade_mode='paper'
        ))

        # Publish fill event
        await self.publish(TradeExecutedEvent(
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side='buy',
            quantity=quantity,
            price=price,
            fee=fee,
            order_id=None
        ))

        logger.info(f"Executed BUY: {quantity} {signal.symbol} @ {price}")

    async def _execute_sell(self, signal, portfolio):
        """Execute sell order (paper trading)"""
        # Similar to buy but selling position
        # ... implementation
        pass

    async def _persist_trade(self, trade: Trade):
        """Save trade to database"""
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            await conn.execute("""
                INSERT INTO trades (time, strategy_name, symbol, side, quantity, price, value, fee, trade_mode)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, trade.time, trade.strategy_name, trade.symbol, trade.side,
               trade.quantity, trade.price, trade.value, trade.fee, trade.trade_mode)
        finally:
            await db.release_connection(conn)
```

**Tests**: Test paper trading simulation.

**Git**: `feat(agents): add Trade Execution Agent with paper trading`

### Deliverables

```
src/agents/
├── market_data.py       ✓
├── strategy.py          ✓
├── strategies/
│   ├── momentum.py      ✓
│   └── macd.py          ✓
└── execution.py         ✓

tests/test_agents/       ✓
```

---

## Agent 3: Intelligence

**Working Directory**: `project-planner-agent3`
**Duration**: ~4 hours
**Role**: Meta-strategy, fork management, risk monitoring

### Phase 3A: Wait for Foundation

Same as Agent 2 - wait for Agent 1 to push models, then merge:

```bash
git fetch origin
git merge origin/day1-agent1
```

### Phase 3B: Meta-Strategy Agent (1.5 hours)

**Task 1.11**: Meta-Strategy Agent

**File**: `src/agents/meta_strategy.py`

```python
"""
Meta-Strategy Agent

Manages capital allocation across strategies.
Phase 1: Equal weighting initially, then performance-based.
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.models.events import AllocationEvent, TradeExecutedEvent
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class MetaStrategyAgent(BaseAgent):
    """
    Portfolio manager that allocates capital to strategies.
    """

    def __init__(self, event_bus, strategies: list[str], evaluation_interval_hours: int = 6):
        super().__init__("meta_strategy", event_bus)
        self.strategies = strategies
        self.evaluation_interval = evaluation_interval_hours
        self.current_allocations = {}
        self.first_allocation = True

    async def start(self):
        """Start meta-strategy"""
        # Initial allocation
        await self._allocate_capital()

        # Periodic reallocation
        while True:
            await asyncio.sleep(self.evaluation_interval * 3600)
            await self._evaluate_and_reallocate()

    async def _allocate_capital(self):
        """Allocate capital to strategies"""
        if self.first_allocation:
            # Equal weighting initially
            allocation_pct = 100.0 / len(self.strategies)
            self.current_allocations = {
                strategy: allocation_pct for strategy in self.strategies
            }
            reason = "Initial equal weighting allocation"
            self.first_allocation = False
        else:
            # Performance-based allocation
            self.current_allocations = await self._calculate_performance_allocations()
            reason = "Performance-based reallocation"

        # Publish allocation event
        await self.publish(AllocationEvent(
            allocations=self.current_allocations,
            reason=reason
        ))

        logger.info(f"Capital allocated: {self.current_allocations}")

    async def _calculate_performance_allocations(self) -> dict:
        """Calculate allocations based on recent performance"""
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            # Get recent performance for each strategy
            performances = await conn.fetch("""
                SELECT strategy_name, total_pnl
                FROM strategy_performance
                WHERE time >= NOW() - INTERVAL '7 days'
                ORDER BY time DESC
            """)

            # Simple allocation: More to better performers
            # ... implementation
            return {}  # Return allocation dict

        finally:
            await db.release_connection(conn)
```

**Tests**: Test allocation logic.

**Git**: `feat(agents): add Meta-Strategy Agent with allocation logic`

### Phase 3C: Fork Manager Agent (1.5 hours)

**Task 1.12**: Fork Manager Agent

**File**: `src/agents/fork_manager.py`

```python
"""
Fork Manager Agent

Manages database fork lifecycle.
Creates, tracks, and destroys forks on request.
"""
import logging
import subprocess
import json
from datetime import datetime
from src.agents.base import BaseAgent
from src.models.events import ForkRequestEvent, ForkCreatedEvent, ForkCompletedEvent
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class ForkManagerAgent(BaseAgent):
    """
    Manages Tiger Cloud database forks.

    Uses Tiger Cloud CLI (`tsdb` command) to create/destroy forks.
    """

    def __init__(self, event_bus, parent_service_id: str, max_concurrent_forks: int = 10):
        super().__init__("fork_manager", event_bus)
        self.parent_service_id = parent_service_id
        self.max_concurrent_forks = max_concurrent_forks
        self.active_forks = {}  # fork_id -> metadata

    async def start(self):
        """Start fork manager"""
        # Subscribe to fork requests
        request_queue = self.event_bus.subscribe(ForkRequestEvent)
        completed_queue = self.event_bus.subscribe(ForkCompletedEvent)

        await asyncio.gather(
            self._process_fork_requests(request_queue),
            self._process_fork_completions(completed_queue),
            self._cleanup_expired_forks()
        )

    async def _process_fork_requests(self, queue):
        """Process fork creation requests"""
        async for request in self._consume_events(queue):
            await self._create_fork(request)

    async def _create_fork(self, request: ForkRequestEvent):
        """Create database fork using Tiger Cloud CLI"""
        # Check concurrent limit
        if len(self.active_forks) >= self.max_concurrent_forks:
            logger.warning("Max concurrent forks reached, queuing request")
            return

        try:
            # Call Tiger Cloud CLI to create fork
            # tsdb service fork <parent-service-id>
            result = subprocess.run(
                ['tsdb', 'service', 'fork', self.parent_service_id],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse CLI output to get fork service ID
            output = json.loads(result.stdout)
            fork_service_id = output['service_id']

            # Get connection parameters
            fork_connection = await self._get_fork_connection_params(fork_service_id)

            # Track fork
            self.active_forks[fork_service_id] = {
                'requesting_agent': request.requesting_agent,
                'purpose': request.purpose,
                'created_at': datetime.now(),
                'ttl_seconds': request.ttl_seconds
            }

            # Persist to database
            await self._persist_fork_metadata(fork_service_id, request)

            # Publish fork created event
            await self.publish(ForkCreatedEvent(
                fork_id=fork_service_id,
                service_id=fork_service_id,
                connection_params=fork_connection,
                requesting_agent=request.requesting_agent
            ))

            logger.info(f"Fork created: {fork_service_id} for {request.requesting_agent}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create fork: {e}")

    async def _destroy_fork(self, fork_id: str):
        """Destroy database fork"""
        try:
            subprocess.run(
                ['tsdb', 'service', 'delete', fork_id],
                check=True
            )

            # Remove from tracking
            del self.active_forks[fork_id]

            # Update database
            db = get_db_manager()
            conn = await db.get_connection()
            try:
                await conn.execute("""
                    UPDATE fork_tracking
                    SET status = 'destroyed', destroyed_at = NOW()
                    WHERE fork_id = $1
                """, fork_id)
            finally:
                await db.release_connection(conn)

            logger.info(f"Fork destroyed: {fork_id}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to destroy fork: {e}")

    async def _cleanup_expired_forks(self):
        """Periodically cleanup expired forks"""
        while True:
            await asyncio.sleep(1800)  # Every 30 minutes

            now = datetime.now()
            expired = []

            for fork_id, metadata in self.active_forks.items():
                age = (now - metadata['created_at']).total_seconds()
                if age > metadata['ttl_seconds']:
                    expired.append(fork_id)

            for fork_id in expired:
                await self._destroy_fork(fork_id)
```

**Tests**: Mock Tiger Cloud CLI calls.

**Git**: `feat(agents): add Fork Manager with Tiger Cloud integration`

### Phase 3D: Risk Monitor Agent (1 hour)

**Task 1.13**: Risk Monitor Agent

**File**: `src/agents/risk_monitor.py`

```python
"""
Risk Monitor Agent

Enforces risk limits and can halt trading if thresholds breached.
"""
import logging
from decimal import Decimal
from datetime import datetime
from src.agents.base import BaseAgent
from src.models.events import TradeExecutedEvent, RiskAlertEvent, EmergencyHaltEvent
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class RiskMonitorAgent(BaseAgent):
    """
    Monitors risk and enforces limits.

    Phase 1 limits:
    - Max position size: 20% of allocated capital
    - Max daily loss: 5% of total portfolio
    - Max exposure: 80% of portfolio
    - Per-strategy drawdown: 10%
    """

    def __init__(self, event_bus, config: dict):
        super().__init__("risk_monitor", event_bus)
        self.config = config
        self.daily_start_value = None
        self.halt_active = False

    async def start(self):
        """Start risk monitor"""
        # Subscribe to trade events
        trade_queue = self.event_bus.subscribe(TradeExecutedEvent)

        await asyncio.gather(
            self._monitor_trades(trade_queue),
            self._periodic_checks()
        )

    async def _monitor_trades(self, queue):
        """Monitor each trade execution"""
        async for trade in self._consume_events(queue):
            await self._check_trade_risk(trade)

    async def _check_trade_risk(self, trade: TradeExecutedEvent):
        """Check if trade violates risk limits"""
        # Check position size
        # Check exposure
        # Check daily loss
        pass

    async def _periodic_checks(self):
        """Run periodic risk checks"""
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds

            await self._check_daily_loss()
            await self._check_strategy_drawdowns()

    async def _check_daily_loss(self):
        """Check if daily loss limit breached"""
        # Get current portfolio value
        # Compare to start of day value
        # If loss > 5%, publish halt event
        pass
```

**Tests**: Test risk limit enforcement.

**Git**: `feat(agents): add Risk Monitor with Phase 1 limits`

### Deliverables

```
src/agents/
├── meta_strategy.py     ✓
├── fork_manager.py      ✓
└── risk_monitor.py      ✓

tests/test_agents/       ✓
```

---

## Integration Point (All Agents)

**Time**: After ~4 hours (when all agents complete their work)

### Merge Strategy

```bash
# Agent 1 (Foundation) already on main branch or pushed to day1-agent1

# Agent 2 merges Agent 1, then pushes
cd project-planner-agent2
git fetch origin
git merge origin/day1-agent1
# Resolve any conflicts
git push origin day1-agent2

# Agent 3 merges Agent 1, then pushes
cd project-planner-agent3
git fetch origin
git merge origin/day1-agent1
# Resolve any conflicts
git push origin day1-agent3

# Final integration (any agent can do this)
cd project-planner
git checkout -b day1-integration
git merge origin/day1-agent1
git merge origin/day1-agent2
git merge origin/day1-agent3
# Resolve any conflicts
# Run tests
pytest tests/ -v
```

### Task 1.14: Main Entry Point (30 min - any agent)

**File**: `src/main.py`

```python
"""
Main entry point - orchestrates all agents
"""
import asyncio
import logging
import yaml
from src.core.event_bus import get_event_bus
from src.core.database import get_db_manager
from src.agents.market_data import MarketDataAgent
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.macd import MACDStrategy
from src.agents.execution import TradeExecutionAgent
from src.agents.meta_strategy import MetaStrategyAgent
from src.agents.fork_manager import ForkManagerAgent
from src.agents.risk_monitor import RiskMonitorAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start all agents"""
    # Load config
    with open('config/app.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize infrastructure
    event_bus = get_event_bus()
    db_manager = get_db_manager()
    await db_manager.initialize()

    # Create agents
    agents = []

    # Market Data
    market_data = MarketDataAgent(event_bus, symbols=['BTCUSDT', 'ETHUSDT'])
    agents.append(market_data)

    # Strategies
    momentum = MomentumStrategy(event_bus, 'BTCUSDT')
    macd = MACDStrategy(event_bus, 'BTCUSDT')
    agents.extend([momentum, macd])

    # Execution
    execution = TradeExecutionAgent(event_bus, initial_capital=Decimal('10000'))
    agents.append(execution)

    # Meta-Strategy
    meta_strategy = MetaStrategyAgent(event_bus, ['momentum', 'macd'])
    agents.append(meta_strategy)

    # Fork Manager
    fork_manager = ForkManagerAgent(event_bus, config['tiger']['service_id'])
    agents.append(fork_manager)

    # Risk Monitor
    risk_monitor = RiskMonitorAgent(event_bus, config['risk'])
    agents.append(risk_monitor)

    # Start all agents
    logger.info("Starting all agents...")
    tasks = [agent.start() for agent in agents]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await db_manager.close()
        await event_bus.close()


if __name__ == '__main__':
    asyncio.run(main())
```

**Git**: `feat(main): add entry point and agent orchestration`

### Task 1.15: Integration Testing (30 min - any agent)

**File**: `tests/test_integration.py`

```python
"""Integration tests for full system"""
import pytest
import asyncio
from src.main import main

@pytest.mark.asyncio
async def test_system_startup():
    """Test all agents start without errors"""
    # Start system with timeout
    task = asyncio.create_task(main())

    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=10)
    except asyncio.TimeoutError:
        # Expected - system runs indefinitely
        task.cancel()

    # If we got here, agents started successfully
    assert True
```

**Git**: `test(integration): add integration tests`

---

## Conflict Resolution

### Common Conflicts

1. **`src/models/events.py`**: Unlikely - Agent 1 owns this
2. **`src/agents/base.py`**: Unlikely - Agent 1 owns this
3. **`.gitignore`**: Possible - all agents may modify
4. **`requirements.txt`**: Possible - agents may add dependencies
5. **`config/app.yaml`**: Possible - agents may add sections

### Resolution Strategy

**For `.gitignore` and `requirements.txt`**:
- Merge all additions (union)
- Remove duplicates

**For `config/app.yaml`**:
- Each agent owns a section
- Merge all sections together

**Example conflict resolution**:
```bash
# Accept both changes
git checkout --ours file
git checkout --theirs file
# Manually combine in editor
```

---

## Timeline

### Parallel Execution (Best Case)

```
Hour 0: All agents start setup (Task 1.1)
Hour 0.5: Agent 1 does 1.2, 1.3, 1.4
Hour 1.5: Agent 1 pushes → Agents 2 & 3 can merge and start their work
Hour 1.5-4: All agents work in parallel
Hour 4: Integration begins
Hour 4.5: Integration complete, system running
Hour 5: All tests passing

Total: 5 hours
```

### Sequential Execution (Comparison)

```
Hour 0-4: Agent 1 tasks
Hour 4-8: Agent 2 tasks
Hour 8-12: Agent 3 tasks
Hour 12-13: Integration

Total: 13 hours
```

**Time Saved**: 8 hours (62% reduction)

---

## Communication Protocol

### Status Updates

Each agent posts status to shared doc/channel every 30 minutes:

```
Agent 1: [DONE] Task 1.4 - Trading models complete, pushing now
Agent 2: [WAITING] Ready to merge Agent 1's work
Agent 3: [WAITING] Ready to merge Agent 1's work

Agent 2: [IN PROGRESS] Task 1.8 - Market Data Agent (50% done)
Agent 3: [IN PROGRESS] Task 1.11 - Meta-Strategy (30% done)

Agent 2: [DONE] All tasks complete, pushed to day1-agent2
Agent 3: [DONE] All tasks complete, pushed to day1-agent3

Agent 1: [IN PROGRESS] Integration - merging all branches
```

### Blocker Resolution

If blocked:
1. Post in shared channel immediately
2. Other agents help debug
3. If >15 min, reassign task

---

## Success Criteria

- [ ] All 3 agents complete their tasks
- [ ] All branches pushed
- [ ] Integration complete with no major conflicts
- [ ] All tests passing (pytest)
- [ ] System starts and runs for 1 minute without errors
- [ ] Market data streaming
- [ ] Strategies generating signals
- [ ] Trades executing
- [ ] All agents logging activity

**Time Target**: Complete in 5 hours (vs 13 hours sequential)

---

## Summary

This parallel strategy reduces Day 1 implementation time by **62%** through:

1. **Clear separation of concerns**: Foundation, Data/Trading, Intelligence
2. **Minimal dependencies**: Only models needed as foundation
3. **Independent testing**: Each agent can test their components
4. **Structured integration**: Clear merge strategy
5. **Communication protocol**: Status updates prevent conflicts

The 3-agent parallel approach is **feasible and highly recommended** for this codebase structure.
