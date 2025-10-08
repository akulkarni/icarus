# Icarus Trading System - Architecture

## System Overview

Icarus is a multi-agent trading system built on event-driven architecture with database forking capabilities for parallel strategy validation.

```
┌─────────────────────────────────────────────────────────────┐
│                        Event Bus                             │
│                  (Async Pub/Sub System)                      │
└─────────────────────────────────────────────────────────────┘
          ▲                    │                    ▲
          │                    │                    │
          │                    ▼                    │
┌─────────┴────────┐  ┌─────────────────┐  ┌──────┴─────────┐
│  Market Data     │  │   Strategy      │  │  Trade Exec    │
│     Agent        │  │   Agents (6)    │  │     Agent      │
└──────────────────┘  └─────────────────┘  └────────────────┘
          │                    │                    │
          │                    ▼                    │
          │           ┌─────────────────┐           │
          └──────────▶│ Meta-Strategy   │───────────┘
                      │     Agent       │
                      └─────────────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │  Risk Monitor   │
                      │     Agent       │
                      └─────────────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │  Fork Manager   │
                      │     Agent       │
                      └─────────────────┘
                               │
                               ▼
                      ┌─────────────────────────┐
                      │   TimescaleDB + Forks   │
                      │    (Tiger Cloud)        │
                      └─────────────────────────┘
                               │
                               ▼
                      ┌─────────────────────────┐
                      │   FastAPI Dashboard     │
                      │   (Web Interface)       │
                      └─────────────────────────┘
```

## Core Components

### Event Bus (`src/core/event_bus.py`)

The event bus is the central nervous system of Icarus, enabling asynchronous communication between all agents.

**Features**:
- AsyncIO-based publish/subscribe messaging
- Type-safe event routing based on event classes
- Queue-based delivery with backpressure handling
- Non-blocking publish (drops events if subscriber queue is full)
- Multiple subscribers per event type
- Event statistics and monitoring

**Key Methods**:
```python
event_bus.subscribe(EventType) -> asyncio.Queue
event_bus.publish(event: Event) -> None
event_bus.get_stats() -> dict
```

**Design Benefits**:
- **Decoupling**: Agents don't need to know about each other
- **Scalability**: Easy to add new agents without modifying existing ones
- **Testability**: Can mock event bus for unit tests
- **Observability**: All system communication is visible

### Agents (`src/agents/`)

All agents inherit from base agent classes in `src/agents/base.py`:

#### Base Agent Classes

1. **BaseAgent**
   - Abstract base class for all agents
   - Lifecycle management (start, stop, health checks)
   - Error handling and logging
   - Configuration management

2. **EventDrivenAgent** (extends BaseAgent)
   - Subscribes to specific event types
   - Processes events asynchronously
   - Manages event queue

3. **PeriodicAgent** (extends BaseAgent)
   - Runs on scheduled intervals
   - Configurable execution frequency
   - Handles timing and scheduling

4. **StatefulAgent** (extends BaseAgent)
   - Maintains internal state
   - State persistence capabilities
   - State recovery on restart

#### Agent Implementations

**1. Market Data Agent** (`market_data.py`)

Streams real-time market data from Binance WebSocket.

- **Type**: EventDrivenAgent
- **Subscribes to**: None (data source)
- **Publishes**: `MarketTickEvent`
- **Responsibilities**:
  - Maintain WebSocket connection to Binance
  - Parse ticker data
  - Publish price updates to event bus
  - Handle reconnection on failure

**2. Strategy Agents** (`agents/strategies/`)

Generate trading signals based on technical analysis.

Available strategies:
- **Momentum** (`momentum.py`): Moving average crossover
- **MACD** (`macd.py`): MACD indicator signals

Additional strategies (to be implemented per agent plans):
- **Bollinger Bands**: Mean reversion on band touches
- **Mean Reversion**: RSI-based reversal signals
- **Breakout**: Volume-based breakout detection
- **Stochastic**: Stochastic oscillator signals

All strategy agents:
- **Type**: EventDrivenAgent
- **Subscribes to**: `MarketTickEvent`
- **Publishes**: `TradingSignalEvent`
- **Responsibilities**:
  - Maintain price history buffer
  - Calculate technical indicators
  - Detect trading signals (buy/sell)
  - Publish signals with confidence scores

**3. Meta-Strategy Agent** (`meta_strategy.py`)

Dynamically allocates capital across strategies based on performance.

- **Type**: PeriodicAgent + EventDrivenAgent
- **Subscribes to**: `TradingSignalEvent`
- **Publishes**: `AllocationEvent`, `ForkRequestEvent`
- **Responsibilities**:
  - Track strategy performance metrics
  - Calculate dynamic allocations (e.g., based on Sharpe ratio, win rate)
  - Create database forks for validation
  - Rebalance capital periodically
  - Generate trade orders based on signals and allocations

**4. Trade Execution Agent** (`execution.py`)

Executes trades in paper or live mode.

- **Type**: EventDrivenAgent
- **Subscribes to**: `AllocationEvent`, `TradeOrderEvent`
- **Publishes**: `TradeExecutedEvent`
- **Responsibilities**:
  - Execute trades via Binance API (live mode)
  - Simulate trades with slippage (paper mode)
  - Track order status
  - Update portfolio positions
  - Record trade history in database

**5. Risk Monitor Agent** (`risk_monitor.py`)

Enforces risk management rules and position limits.

- **Type**: EventDrivenAgent + PeriodicAgent
- **Subscribes to**: `TradeOrderEvent`, `TradeExecutedEvent`
- **Publishes**: `RiskAlertEvent`
- **Responsibilities**:
  - Monitor position sizes
  - Track daily P&L and loss limits
  - Calculate portfolio exposure
  - Enforce max drawdown per strategy
  - Emergency trading halt if limits breached

**6. Fork Manager Agent** (`fork_manager.py`)

Manages Tiger Cloud database forks for parallel validation.

- **Type**: EventDrivenAgent
- **Subscribes to**: `ForkRequestEvent`, `ForkCompletedEvent`
- **Publishes**: `ForkCreatedEvent`, `ForkDestroyedEvent`
- **Responsibilities**:
  - Create Tiger Cloud forks on demand
  - Track fork lifecycle and TTL
  - Provide fork connection info to requesters
  - Automatically destroy expired forks
  - Enforce maximum concurrent fork limits

**7. PR Agent** (`pr_agent.py`) - Coming Soon

Generates human-readable narratives of system activity.

- **Type**: EventDrivenAgent
- **Subscribes to**: All events
- **Publishes**: `PRNarrativeEvent`
- **Responsibilities**:
  - Monitor all system events
  - Generate descriptive narratives
  - Score event importance
  - Store narratives in `pr_events` table
  - Provide activity feed for dashboard

### Database Layer (`src/core/database.py`)

Manages database connections and queries.

**Features**:
- AsyncPG connection pool
- Async context managers for safe connection handling
- Connection lifecycle management
- Automatic reconnection on failure
- Query execution helpers

**Key Functions**:
```python
async with get_db_connection() as conn:
    await conn.execute("INSERT INTO ...")
    result = await conn.fetch("SELECT * FROM ...")
```

### Models (`src/models/`)

**Event Models** (`events.py`)
- All event types as immutable dataclasses
- Type-safe event definitions
- Event hierarchy and inheritance
- Helper functions for event type detection

**Trading Models** (`trading.py`)
- Position, Trade, Order models
- Strategy performance metrics
- Portfolio state representation
- Risk metrics

### Web Dashboard (`src/web/`)

FastAPI-based web interface for monitoring.

**Components**:
- **API Routes** (`api.py`): REST endpoints
- **WebSocket** (`websocket.py`): Real-time updates
- **Static Files** (`static/`): HTML, CSS, JavaScript
- **Server** (`server.py`): FastAPI application

**Endpoints**:
- `GET /`: Health check
- `GET /dashboard`: Dashboard HTML
- `GET /api/portfolio`: Portfolio summary
- `GET /api/trades/recent`: Recent trades
- `GET /api/forks/active`: Active forks
- `GET /api/pr/narratives`: PR narratives
- `WS /ws`: Real-time event stream

## Data Flow

### Trading Signal Flow

1. **Market Data Ingestion**
   - Binance WebSocket → Market Data Agent
   - Agent publishes `MarketTickEvent`
   - Event contains: symbol, price, timestamp, volume

2. **Signal Generation**
   - Strategy Agents receive `MarketTickEvent`
   - Each strategy:
     - Updates price history buffer
     - Recalculates indicators
     - Checks for signal conditions
   - If signal detected, publish `TradingSignalEvent`

3. **Signal Evaluation**
   - Meta-Strategy Agent receives `TradingSignalEvent`
   - Evaluates signal against:
     - Current strategy allocation
     - Available capital
     - Strategy performance history
   - Publishes `AllocationEvent` if trade should be made

4. **Risk Validation**
   - Risk Monitor receives `AllocationEvent`
   - Validates against:
     - Position size limits
     - Daily loss limits
     - Portfolio exposure
     - Strategy drawdown
   - Publishes `RiskAlertEvent` if limits breached

5. **Trade Execution**
   - Execution Agent receives `AllocationEvent`
   - If paper mode: Simulates trade with slippage
   - If live mode: Places order via Binance API
   - Publishes `TradeExecutedEvent`

6. **Record Keeping**
   - All agents record to database:
     - Market data → `market_data` table
     - Signals → `trading_signals` table
     - Trades → `trades` table
     - Positions → `positions` table
     - Performance → `strategy_performance` table

7. **Narrative Generation**
   - PR Agent observes all events
   - Generates human-readable narrative
   - Stores in `pr_events` table
   - Displayed on dashboard

### Fork Workflow

Database forking enables parallel validation without affecting the main database.

1. **Fork Request**
   - Meta-Strategy Agent needs to validate allocation scenario
   - Publishes `ForkRequestEvent` with:
     - Purpose (validation, optimization, scenario analysis)
     - TTL (time-to-live)
     - Requesting agent ID

2. **Fork Creation**
   - Fork Manager receives `ForkRequestEvent`
   - Creates Tiger Cloud fork via API
   - Records fork in `fork_tracking` table
   - Publishes `ForkCreatedEvent` with connection info

3. **Fork Usage**
   - Requesting agent receives `ForkCreatedEvent`
   - Connects to fork database
   - Runs validation queries (e.g., backtest allocation scenario)
   - Performs analysis without affecting main DB

4. **Fork Completion**
   - Agent finishes validation
   - Publishes `ForkCompletedEvent` with results
   - Results stored in `fork_results` table

5. **Fork Cleanup**
   - Fork Manager monitors fork TTLs
   - When expired, destroys fork via Tiger Cloud API
   - Updates `fork_tracking` status to 'destroyed'
   - Publishes `ForkDestroyedEvent`

## Database Schema

### Time-Series Tables (Hypertables)

**crypto_prices** (formerly market_data)
```sql
CREATE TABLE crypto_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    PRIMARY KEY (time, symbol)
);
SELECT create_hypertable('crypto_prices', 'time');
```

**trades**
```sql
CREATE TABLE trades (
    time TIMESTAMPTZ NOT NULL,
    trade_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'buy' or 'sell'
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION,
    trade_mode TEXT NOT NULL,  -- 'paper' or 'live'
    PRIMARY KEY (time, trade_id)
);
SELECT create_hypertable('trades', 'time');
```

**strategy_performance**
```sql
CREATE TABLE strategy_performance (
    time TIMESTAMPTZ NOT NULL,
    strategy_name TEXT NOT NULL,
    portfolio_value DOUBLE PRECISION NOT NULL,
    cash_balance DOUBLE PRECISION NOT NULL,
    total_pnl DOUBLE PRECISION,
    total_trades INTEGER,
    win_rate DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    allocation_pct DOUBLE PRECISION,
    is_active BOOLEAN,
    PRIMARY KEY (time, strategy_name)
);
SELECT create_hypertable('strategy_performance', 'time');
```

### Regular Tables

**positions**
```sql
CREATE TABLE positions (
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    avg_entry_price DOUBLE PRECISION NOT NULL,
    current_value DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    last_updated TIMESTAMPTZ,
    PRIMARY KEY (strategy_name, symbol)
);
```

**current_allocations**
```sql
CREATE TABLE current_allocations (
    strategy_name TEXT PRIMARY KEY,
    allocation_pct DOUBLE PRECISION NOT NULL,
    allocated_capital DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL
);
```

**fork_tracking**
```sql
CREATE TABLE fork_tracking (
    fork_id TEXT PRIMARY KEY,
    requesting_agent TEXT NOT NULL,
    purpose TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    status TEXT NOT NULL,  -- 'active', 'expired', 'destroyed'
    connection_info JSONB
);
```

**pr_events**
```sql
CREATE TABLE pr_events (
    time TIMESTAMPTZ NOT NULL,
    event_id TEXT NOT NULL,
    narrative TEXT NOT NULL,
    event_category TEXT,
    importance_score INTEGER,
    PRIMARY KEY (time, event_id)
);
SELECT create_hypertable('pr_events', 'time');
```

## Configuration Management

Configuration is managed through YAML files and environment variables.

**Configuration Files**:
- `config/app.yaml`: Main application configuration
- `.env`: Environment-specific secrets (database credentials, API keys)

**Configuration Loading** (`src/core/config.py`):
- Loads YAML with environment variable substitution
- Validates required fields
- Provides type-safe config access
- Supports defaults

**Example**:
```python
from src.core.config import get_config

config = get_config()
trading_mode = config['trading']['mode']
db_host = config['database']['host']
```

## Design Patterns

### Event-Driven Architecture

**Benefits**:
- Loose coupling between components
- Asynchronous processing
- Easy to scale and extend
- Clear communication paths

**Implementation**:
- Central event bus
- Type-safe event classes
- Queue-based delivery
- Non-blocking publish

### Agent Pattern

**Benefits**:
- Self-contained components
- Single responsibility
- Lifecycle management
- Observable behavior

**Implementation**:
- Base agent classes with common functionality
- Start/stop lifecycle methods
- Health check interface
- Configuration injection

### Database Forking

**Benefits**:
- Parallel validation without main DB impact
- Safe experimentation
- Automatic cleanup
- Resource management

**Implementation**:
- Tiger Cloud fork API
- TTL-based lifecycle
- Fork tracking and monitoring
- Connection info distribution

### Pub/Sub Messaging

**Benefits**:
- Decoupled communication
- Multiple subscribers per event
- Flexible routing
- Async delivery

**Implementation**:
- Type-based subscriptions
- Queue per subscriber
- Backpressure handling
- Event statistics

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Async Runtime**: asyncio
- **Database**: PostgreSQL 15+ with TimescaleDB extension
- **Cloud Platform**: Tiger Cloud (managed TimescaleDB)
- **Web Framework**: FastAPI
- **WebSocket**: FastAPI WebSockets
- **Exchange API**: Binance API (python-binance)

### Key Libraries
- **asyncpg**: Async PostgreSQL driver
- **pydantic**: Data validation
- **pyyaml**: Configuration parsing
- **python-binance**: Binance exchange client
- **uvicorn**: ASGI server
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support

### Infrastructure
- **Database**: TimescaleDB hypertables for time-series data
- **Forks**: Tiger Cloud fork API for parallel validation
- **Deployment**: Docker (optional), systemd service
- **Monitoring**: JSON logs, dashboard, database queries

## Scalability Considerations

### Horizontal Scaling
- Event bus supports multiple instances via Redis (future)
- Stateless agents can be replicated
- Database read replicas for query load
- Load balancer for web dashboard

### Vertical Scaling
- AsyncIO enables high concurrency on single machine
- Connection pooling optimizes database connections
- Event queue sizes configurable for memory management
- Strategy agents can process multiple symbols

### Performance Optimization
- TimescaleDB compression for historical data
- Continuous aggregates for performance metrics
- Index optimization for frequent queries
- Connection pool tuning

## Security Considerations

### API Keys
- Stored in `.env` file (never committed)
- Environment variable injection
- Binance API key with restricted permissions
- IP whitelist on exchange

### Database
- SSL/TLS connections
- Tiger Cloud managed security
- Row-level security (future)
- Audit logging

### Trading Safety
- Paper trading mode by default
- Risk limits enforced
- Emergency halt capability
- Trade validation before execution

## Testing Strategy

### Unit Tests
- Agent behavior in isolation
- Event bus functionality
- Strategy calculations
- Risk checks

### Integration Tests
- Agent communication via event bus
- Database operations
- Fork lifecycle
- End-to-end signal flow

### Mock Objects
- Mock event bus for isolated testing
- Mock Binance API for trade execution tests
- Mock database connections
- Mock fork manager

### Test Coverage
- Target: >80% code coverage
- Critical paths: 100% coverage
- Strategy logic: Comprehensive test cases
- Risk validation: Edge cases

## Future Enhancements

### Planned Features
1. **Machine Learning Integration**: ML-based signal generation
2. **Multi-Exchange Support**: Beyond Binance
3. **Advanced Risk Models**: VaR, CVaR calculations
4. **Backtesting Framework**: Historical strategy validation
5. **Portfolio Optimization**: Modern portfolio theory
6. **Distributed Event Bus**: Redis-based for multi-instance
7. **Advanced Dashboard**: React-based SPA with charts
8. **Notification System**: Alerts via email, SMS, Slack

### Architectural Evolution
- Microservices architecture for large-scale deployment
- Kubernetes orchestration
- Service mesh for inter-agent communication
- Distributed tracing and observability
- Advanced monitoring and alerting
