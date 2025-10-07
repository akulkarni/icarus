# Live Trading System Design Specification

**Project**: Autonomous Live Crypto Trading System with Tiger Cloud Showcase
**Purpose**: Demonstrate Tiger Cloud's forkable database capabilities through a multi-agent trading system
**Timeline**: 3-day MVP with phased rollout
**Last Updated**: 2025-10-06

---

## Table of Contents

1. [Design Overview](#design-overview)
2. [System Architecture & Components](#system-architecture--components)
3. [Database Architecture & Fork Workflow](#database-architecture--fork-workflow)
4. [Meta-Strategy Intelligence & Decision Making](#meta-strategy-intelligence--decision-making)
5. [Web Dashboard & Visualization](#web-dashboard--visualization)
6. [Technology Stack & Implementation](#technology-stack--implementation)
7. [Fork Manager Agent Implementation](#fork-manager-agent-implementation)
8. [Agent Communication & Coordination](#agent-communication--coordination)
9. [MVP Scope & Development Phases](#mvp-scope--development-phases)
10. [Database Schema Design](#database-schema-design)
11. [System Configuration & Operations](#system-configuration--operations)
12. [Risk Management & Trading Parameters](#risk-management--trading-parameters)

---

## Design Overview

### Core Concept & Purpose

A live cryptocurrency trading system that serves as a compelling showcase for Tiger Cloud's forkable database capabilities. The system runs multiple backtested strategies (momentum, MACD, Bollinger Bands, breakout, mean reversion, stochastic) against live market data from Binance, supporting both paper trading and real trading modes.

The key differentiator is the intelligent use of database forks throughout the development and operational lifecycle. Rather than treating forks as an occasional feature, they become central to how strategies are developed, tested, validated, and deployed. A meta-strategy component dynamically selects which strategies to activate based on a combination of recent backtest performance, market regime detection, and other signals.

The system prioritizes getting to an MVP quickly - a working end-to-end demonstration that shows real trading decisions being made with forked databases playing a visible role. Initial paper trading capital is set at $10,000 with clear risk limits enforced from day 1. The primary interface will be a web dashboard that visualizes not just trading activity and P&L, but also the fork lifecycle and how forks enable rapid iteration.

**Initial Trading Parameters**:
- Trading pairs: BTC/USDT and ETH/USDT
- Paper trading capital: $10,000
- Market data source: Binance public API (no authentication required)
- Order execution: Paper trading simulation with instant fills at market price

---

## System Architecture & Components

### Agent-Based Architecture

The system is built as a multi-agent system where each component operates as an autonomous agent with its own goals, decision-making logic, and communication patterns:

#### 1. Market Data Agent
Continuously monitors Binance API, streaming real-time price data into TimescaleDB. Makes decisions about what data to fetch (symbols, intervals) and adapts to rate limits or connectivity issues. Publishes market events that other agents subscribe to.

#### 2. Strategy Agents
Each trading strategy (momentum, MACD, Bollinger, etc.) runs as an independent agent. Each agent analyzes market data, maintains its own state, generates trading signals autonomously, and can request database forks to validate its own performance. Strategy agents compete for capital allocation from the Meta-Strategy Agent.

#### 3. Meta-Strategy Agent
Acts as a portfolio manager, observing all strategy agents' performance and market conditions. Makes autonomous decisions about capital allocation, strategy activation/deactivation. Requests forks to evaluate "what-if" scenarios and compare strategy performance across different market regimes.

#### 4. Trade Execution Agent
Receives trade signals from active strategies and autonomously manages order lifecycle (placement, monitoring, fills). Handles both paper trading simulation and real order execution. Makes decisions about order types, timing, and retries.

#### 5. Fork Manager Agent
Proactively creates, monitors, and cleans up database forks. Responds to requests from other agents (strategies wanting to backtest, meta-strategy running evaluations) and autonomously manages fork lifecycle and resource usage.

#### 6. Risk Monitor Agent
Observes all trading activity and can autonomously intervene (halt trading, reduce positions) when risk thresholds are breached. Enforces strict limits from Phase 1 MVP to ensure safe operation.

#### 7. PR Agent
Monitors system activity across all agents, identifying "interesting developments" worth highlighting: exceptional strategy performance, successful fork-based optimizations, regime changes detected by meta-strategy, near-misses caught by risk monitoring, etc. Logs these narratives in a human-readable format (markdown file or structured log) that can be used for demos, blog posts, or documentation.

### Agent Communication
Agents communicate via message passing or event streams, making the system loosely coupled and easy to extend.

---

## Database Architecture & Fork Workflow

### TimescaleDB Structure

The main production database maintains the current state:
- **crypto_prices** hypertable with live market data (OHLCV)
- **trades** table logging all executed trades with timestamps, strategy attribution, prices, and outcomes
- **positions** table tracking current holdings per strategy
- **strategy_performance** table with running metrics (P&L, win rate, Sharpe ratio, drawdown)
- **agent_events** table logging agent decisions, state changes, and inter-agent messages
- Continuous aggregates for 5min, 1hour, 1day views (already configured)

### Fork Usage Patterns

Forks become the primary mechanism for safe experimentation and validation:

#### Pattern 1 - Strategy Validation
Strategy Agents request forks for validation backtests on a hybrid schedule:
- **Fixed schedule**: Every 6 hours for routine validation
- **Event-triggered**: On market regime changes or when strategy performance drops below -5%
- **On-demand**: When Meta-Strategy Agent requests validation before reallocation decisions

The strategy runs a backtest on recent data in the fork, generates performance metrics, and reports results to Meta-Strategy Agent. Fork is destroyed after validation.

#### Pattern 2 - Parameter Optimization
Strategy Agents periodically request forks to test parameter variations (different MA periods, threshold values). Multiple parameter sets are tested in parallel across multiple forks. Best-performing parameters are adopted by the live strategy.

#### Pattern 3 - Meta-Strategy Evaluation
Before reallocating capital, Meta-Strategy Agent forks the database and simulates different allocation scenarios using recent market data. Compares outcomes across forks to make informed decisions. This showcases how forks enable sophisticated "what-if" analysis.

#### Pattern 4 - Incident Analysis
When Risk Monitor Agent detects anomalies or PR Agent identifies interesting events, a fork is created to preserve that moment in time for later analysis without impacting production.

---

## Meta-Strategy Intelligence & Decision Making

### How the Meta-Strategy Agent Decides

The Meta-Strategy Agent operates on a periodic cycle (every 6 hours) and uses multiple inputs to make capital allocation decisions.

**Initial Allocation Strategy**: When the system starts with no historical performance data, Meta-Strategy allocates capital equally across all available strategies. After the first validation cycle completes (1-2 hours), it switches to performance-based allocation using the inputs below:

#### Input 1 - Recent Backtest Performance
Requests forks covering the last 7, 30, and 90 days. Each Strategy Agent runs backtests on these forks in parallel. Meta-strategy receives performance metrics (ROI, Sharpe ratio, max drawdown, win rate) and weighs recent performance more heavily than older data.

#### Input 2 - Market Regime Detection
Analyzes current market conditions from the live database:
- Volatility levels (standard deviation of returns, ATR indicators)
- Trend strength (ADX, moving average slopes)
- Correlation patterns between assets
- Volume patterns and liquidity signals

Classifies the current regime (trending bull, trending bear, high volatility range-bound, low volatility consolidation, etc.).

#### Input 3 - Strategy-Regime Matching
Maintains historical knowledge of which strategies perform best in which regimes. For example, momentum strategies excel in strong trends, mean reversion works in range-bound markets, breakout strategies shine during volatility expansion.

#### Input 4 - Diversification & Risk
Considers how strategy signals correlate - avoids allocating heavily to strategies that would all take the same positions simultaneously.

#### Decision Output
Produces capital allocation percentages for each strategy (including 0% = disabled). Communicates decisions to Trade Execution Agent, which adjusts positions accordingly.

---

## Web Dashboard & Visualization

### Dashboard Views

The web interface provides real-time visibility into the entire system with multiple views:

#### Main Trading View
Central display showing current portfolio value, total P&L, active positions, and recent trades. Real-time price charts for monitored cryptocurrencies. Live feed of trading signals and executions as they happen.

#### Agent Status Panel
Grid or list view of all agents showing their current state, health, and recent activities. Visual indicators (green/yellow/red) for agent status. Click into any agent to see detailed logs and decision history.

#### Strategy Performance Dashboard
Comparative view of all strategy agents showing current allocation percentages, individual P&L, trade counts, and performance metrics. Charts showing strategy performance over time. Highlights which strategies are currently active vs. inactive and why.

#### Fork Activity Visualization
This is a showcase centerpiece - visualizes the fork lifecycle in real-time. Shows active forks, what they're being used for (which agent requested them, for what purpose), and results/insights generated. Timeline view of fork creation/destruction events. Metrics on fork usage patterns demonstrating the value of forkable databases.

#### Market Regime Indicator
Visual representation of detected market conditions (volatility meter, trend strength gauge, regime classification). Shows how Meta-Strategy Agent is interpreting current conditions.

#### PR Feed
Dedicated section displaying interesting developments logged by the PR Agent - formatted as a narrative timeline with highlights like "Momentum strategy detected trend reversal and exited position, avoiding 8% drawdown" or "Meta-strategy created 3 forks to evaluate reallocation, selected diversified approach."

---

## Technology Stack & Implementation

### Backend Technologies

#### Agent Framework
Python-based with an async/await model using `asyncio` for concurrent agent operations. Each agent runs as an async task that can independently make decisions and communicate. Message passing between agents via Python's `asyncio.Queue` for MVP (no external dependencies). Can be upgraded to Redis Pub/Sub in later phases if needed for scalability.

#### Database Layer
- TimescaleDB (Tiger Cloud) as primary data store
- `psycopg2` or `asyncpg` for PostgreSQL connections
- Tiger Cloud CLI/API for fork management operations
- Connection pool size: `(num_agents * 2) + 5` for main database
- Each agent maintains its own connection when querying forks
- Requires Tiger Cloud credentials with fork creation/deletion permissions

#### Market Data & Trading
- `python-binance` or `ccxt` library for Binance API integration
- **Phase 1**: Use Binance public endpoints (no API keys required) for market data streaming
- **Phase 3**: Binance API keys required for real trading mode
- WebSocket connections for real-time price streams
- REST API calls for order execution (simulated in paper mode, real in Phase 3)

#### Data Processing
`pandas` and `numpy` for time-series analysis, technical indicators, and backtest calculations (reusing existing backtest code).

### Frontend Technologies

#### Web Framework
Modern JavaScript framework - React or Next.js for the dashboard. Real-time updates via WebSockets (Socket.io or native WebSockets) pushing agent events, trades, and fork activities to the browser.

#### Visualization
Chart.js or Plotly for price charts and performance graphs. Custom components for agent status visualization and fork lifecycle diagrams.

#### API Layer
FastAPI or Flask backend serving REST endpoints for dashboard data and WebSocket connections for live updates.

### MVP Implementation Priority

Start with core loop: Market Data Agent → Strategy Agents → simple Meta-Strategy → Trade Execution (paper mode) → basic dashboard. Add Fork Manager integration early to showcase database forks. Layer in sophistication (advanced meta-strategy logic, PR Agent, rich visualizations) in subsequent iterations.

---

## Fork Manager Agent Implementation

### Fork Lifecycle Management

The Fork Manager Agent interfaces with Tiger Cloud's fork capabilities to orchestrate the database fork workflow:

#### Fork Creation
When an agent requests a fork (Strategy Agent wants to backtest, Meta-Strategy needs scenario analysis), Fork Manager:
- Calls Tiger Cloud API/CLI to create a fork from the current production database
- Tracks fork metadata: purpose, requesting agent, timestamp, expected duration
- Provides connection details to the requesting agent
- Logs fork creation event to `agent_events` table and notifies PR Agent of interesting fork patterns

#### Fork Tracking
Maintains an in-memory registry and persistent database table tracking all active forks:
- Fork ID, service ID from Tiger Cloud
- Purpose and requesting agent
- Creation timestamp and TTL (time-to-live)
- Resource usage and query patterns
- Results/insights generated

#### Fork Cleanup
Autonomously monitors fork age and usage:
- Destroys forks after their purpose is complete (backtest finished, results reported)
- Enforces maximum fork lifetime (e.g., 24 hours) to prevent resource accumulation
- Can preserve "interesting" forks longer if PR Agent flags significant findings
- Calls Tiger Cloud API to delete forks and logs cleanup events

#### Fork Optimization
Over time, learns fork usage patterns:
- Pre-emptively creates forks if agents have predictable schedules (e.g., Meta-Strategy evaluates every 6 hours)
- Batches multiple backtest requests to share forks when possible
- Suggests optimal fork timing to minimize costs while maximizing agent effectiveness

### Showcase Value

Fork Manager's logs and metrics become compelling demo material: "System created 47 forks today for strategy validation, enabling rapid experimentation without production impact" or "Meta-strategy evaluated 8 allocation scenarios across parallel forks in 3 minutes."

---

## Agent Communication & Coordination

### Message-Passing Architecture

Agents operate independently but coordinate through an event-driven messaging system:

#### Event Bus
Central message broker implemented with Python's `asyncio.Queue` where agents publish events and subscribe to topics of interest. No external dependencies required for MVP.

#### Event Types
- **Market events**: Price updates, volume spikes, volatility changes (from Market Data Agent)
- **Signal events**: Buy/sell signals with confidence scores (from Strategy Agents)
- **Execution events**: Order placements, fills, position changes (from Trade Execution Agent)
- **Allocation events**: Capital reallocation decisions (from Meta-Strategy Agent)
- **Fork events**: Fork creation, completion, results (from Fork Manager Agent)
- **Risk events**: Threshold breaches, interventions (from Risk Monitor Agent)
- **Narrative events**: Interesting developments for logging (to PR Agent)

### Agent Autonomy & Decision Making

Each agent operates on its own event loop:

#### Strategy Agents
Subscribe to market events, analyze data independently, generate signals based on their logic. Periodically (e.g., daily) request forks from Fork Manager to validate performance and potentially adjust parameters. Publish signal events when they want to enter/exit positions.

#### Meta-Strategy Agent
Subscribes to execution events and performance metrics. On its evaluation cycle, requests multiple forks, coordinates parallel backtests across Strategy Agents, aggregates results, applies regime detection logic, and publishes allocation decisions. Other agents don't tell it what to do - it observes and decides autonomously.

#### Trade Execution Agent
Subscribes to signal events and allocation decisions. Autonomously decides whether to execute signals based on current allocations, position limits, and available capital. Manages order state machines independently, retrying failed orders or adjusting order types as needed.

#### Fork Manager Agent
Subscribes to fork request events from any agent. Makes autonomous decisions about resource allocation, fork scheduling, and cleanup timing. Publishes fork availability and results.

#### Risk Monitor Agent
Subscribes to all execution and position events. Autonomously calculates exposure and risk metrics. Can publish emergency halt events if thresholds breach.

#### PR Agent
Subscribes to all event types, applies heuristics to identify "interesting" patterns (unusual strategy performance, successful optimizations, regime changes, risk interventions). Autonomously decides what's noteworthy and logs narratives.

### Coordination Without Central Control

No single "orchestrator" - the system emerges from agent interactions. Meta-Strategy influences capital allocation but doesn't command strategies. Strategies generate signals but Execution Agent decides final actions. Fork Manager responds to requests but schedules autonomously. This loose coupling makes the system resilient and extensible.

---

## MVP Scope & Development Phases

### Phase 1: Core MVP (Day 1)

**Goal**: Get a working end-to-end system demonstrating the core concept with fork integration.

**Includes**:
- Market Data Agent streaming live Binance price data into TimescaleDB (public API, no auth required)
- 2 Strategy Agents (momentum, MACD) running in paper trading mode - reuse existing backtest code
- Simple Meta-Strategy Agent with equal weighting initially, switching to performance-based after first validation cycle
- Trade Execution Agent in paper trading mode with instant fills at market price
- Fork Manager Agent capable of creating/destroying forks via Tiger Cloud CLI
- Basic event bus for agent communication (asyncio queues, no external dependencies)
- Risk Monitor Agent enforcing Phase 1 risk limits (see Risk Management section)
- Command-line output showing agent activity and trades (no web UI yet)
- Database schema with core tables (trades, positions, strategy_performance, agent_events, fork_tracking)
- Trading BTC/USDT and ETH/USDT with $10,000 paper capital

**Key Showcase Element**: Strategy Agents request forks for validation backtests every hour, Fork Manager creates/destroys forks, results feed Meta-Strategy allocation decisions. All visible in logs.

### Phase 2: Enhanced Intelligence + Web Dashboard (Day 2)

**Goal**: Add web interface and sophisticated meta-strategy logic.

**Adds**:
- Basic web dashboard with FastAPI backend + simple HTML/JavaScript frontend
- Real-time updates via WebSockets showing: portfolio value, positions, strategy P&L, **fork activity**
- Advanced Meta-Strategy with market regime detection (volatility, trend analysis)
- Fork-based scenario analysis for allocation decisions
- PR Agent identifying and logging interesting developments
- Add remaining Strategy Agents (1-2 more: Bollinger, mean reversion)
- Agent status visualization on dashboard
- Paper trading with basic slippage simulation (0.05-0.1%) for added realism

### Phase 3: Production Ready + Full Showcase (Day 3)

**Goal**: Polish, add real trading capability, and create comprehensive showcase.

**Adds**:
- Real trading mode toggle with Binance API integration
- Enhanced dashboard with rich visualizations (charts, fork lifecycle diagrams, PR feed)
- All remaining Strategy Agents operational
- Parameter optimization feature using parallel forks
- Enhanced Risk Monitor with better safety controls
- Documentation, demo scripts, and showcase narrative
- Performance tuning and error handling

---

## Database Schema Design

### Core Trading Tables

#### trades
Complete audit trail of all trade executions:

```sql
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'buy' or 'sell'
    quantity DECIMAL NOT NULL,
    price DECIMAL NOT NULL,
    value DECIMAL NOT NULL,  -- quantity * price
    fee DECIMAL,
    trade_mode TEXT NOT NULL,  -- 'paper' or 'real'
    signal_confidence DECIMAL,  -- optional confidence score from strategy
    order_id TEXT  -- Binance order ID if real trade
);
SELECT create_hypertable('trades', 'time');
```

#### positions
Current holdings per strategy:

```sql
CREATE TABLE positions (
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity DECIMAL NOT NULL,
    avg_entry_price DECIMAL NOT NULL,
    current_value DECIMAL,
    unrealized_pnl DECIMAL,
    last_updated TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (strategy_name, symbol)
);
```

#### strategy_performance
Time-series performance metrics:

```sql
CREATE TABLE strategy_performance (
    time TIMESTAMPTZ NOT NULL,
    strategy_name TEXT NOT NULL,
    portfolio_value DECIMAL NOT NULL,
    cash_balance DECIMAL NOT NULL,
    total_pnl DECIMAL NOT NULL,
    allocation_pct DECIMAL,  -- current capital allocation from meta-strategy
    win_rate DECIMAL,
    trade_count INT,
    is_active BOOLEAN
);
SELECT create_hypertable('strategy_performance', 'time');
```

### Agent Coordination Tables

#### agent_events
Event log for all agent activities and decisions:

```sql
CREATE TABLE agent_events (
    time TIMESTAMPTZ NOT NULL,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'signal', 'allocation', 'fork_request', 'risk_alert', etc.
    event_data JSONB,  -- flexible storage for event details
    related_fork_id TEXT,
    severity TEXT  -- 'info', 'warning', 'critical'
);
SELECT create_hypertable('agent_events', 'time');
CREATE INDEX ON agent_events (agent_name, time DESC);
CREATE INDEX ON agent_events (event_type, time DESC);
```

#### fork_tracking
Active and historical fork metadata:

```sql
CREATE TABLE fork_tracking (
    fork_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,  -- Tiger Cloud service ID
    parent_service_id TEXT,
    requesting_agent TEXT NOT NULL,
    purpose TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    destroyed_at TIMESTAMPTZ,
    ttl_seconds INT,
    status TEXT,  -- 'active', 'completed', 'destroyed'
    results JSONB,  -- backtest results, insights, etc.
    cost_estimate DECIMAL
);
```

### Market Regime Tracking

#### market_regimes
Detected market conditions over time:

```sql
CREATE TABLE market_regimes (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    regime_type TEXT NOT NULL,  -- 'trending_bull', 'ranging', 'high_volatility', etc.
    volatility DECIMAL,
    trend_strength DECIMAL,
    metadata JSONB
);
SELECT create_hypertable('market_regimes', 'time');
```

### PR Narratives

#### pr_events
Interesting developments logged by PR Agent:

```sql
CREATE TABLE pr_events (
    time TIMESTAMPTZ NOT NULL,
    narrative TEXT NOT NULL,  -- human-readable description
    event_category TEXT,  -- 'performance', 'optimization', 'risk', 'regime_change'
    related_agents TEXT[],
    metrics JSONB,  -- supporting data/metrics
    importance_score INT  -- 1-10 scale
);
SELECT create_hypertable('pr_events', 'time');
```

---

## System Configuration & Operations

### Configuration Management

#### System Config File (YAML or JSON)
- Tiger Cloud connection details (main database and fork management credentials)
- Binance API credentials and trading mode (paper vs. real)
- Agent parameters: update frequencies, risk limits, allocation constraints
- Strategy parameters: technical indicator periods, thresholds for each strategy
- Fork policies: max concurrent forks, TTL defaults, cost limits
- Symbols to trade and monitor

#### Environment-Based Settings
Separate configs for development (aggressive forking, fast cycles for testing) vs. production (conservative limits, longer evaluation periods).

### Startup & Initialization

System startup sequence:
1. Connect to Tiger Cloud main database, verify schema
2. Initialize event bus
3. Start Market Data Agent - begin streaming prices
4. Start all Strategy Agents - load parameters, subscribe to market events
5. Start Fork Manager Agent - scan for orphaned forks, clean up if needed
6. Start Meta-Strategy Agent - perform initial allocation based on recent data
7. Start Trade Execution Agent - reconcile positions with database state
8. Start Risk Monitor Agent - establish baseline metrics
9. Start PR Agent - begin monitoring for narratives
10. Launch web dashboard server

### Operational Monitoring

#### Health Checks
Each agent exposes health status (healthy/degraded/down). Dashboard shows agent grid with status indicators.

#### Logging
Structured JSON logs from all agents with correlation IDs for tracing events across agents. Logs written to files and optionally to TimescaleDB for time-series analysis.

#### Metrics
Track key operational metrics - event bus throughput, database query latency, fork creation/destruction rates, agent decision latency, trade execution success rates.

### Safety & Recovery

#### Graceful Shutdown
Agents close positions or persist state before shutdown. Fork Manager destroys temporary forks or marks them for cleanup.

#### Error Handling
Agents catch exceptions and publish error events. Critical failures (database connection loss, Binance API down) trigger system-wide alerts. Risk Monitor can halt trading autonomously.

#### State Recovery
On restart, agents rebuild state from database (positions, recent performance, active forks).

### Demo & Showcase Mode

#### Accelerated Time
Configuration option to run Meta-Strategy evaluations more frequently (every 5 minutes instead of hourly) for live demos.

#### Narrative Generation
PR Agent configured to generate more frequent updates highlighting fork usage and interesting decisions.

#### Dashboard Highlighting
Visual emphasis on fork activity panel during demos to draw attention to Tiger Cloud's differentiating feature.

---

---

## Risk Management & Trading Parameters

### Phase 1 Risk Limits (MVP)

The Risk Monitor Agent enforces the following limits from Day 1 to ensure safe paper trading operation:

#### Position Limits
- **Max position size**: 20% of allocated capital per trade
- **Max total exposure**: 80% of portfolio (minimum 20% cash reserve)
- **Max positions per strategy**: 2 simultaneous positions

#### Loss Limits
- **Max daily loss**: 5% of total portfolio value
  - Action: Halt all trading for remainder of day
  - Reset at midnight UTC
- **Per-strategy drawdown limit**: 10% from peak
  - Action: Automatically deactivate strategy, set allocation to 0%
  - Strategy can be reactivated after successful fork-based validation

#### Portfolio Parameters
- **Initial capital**: $10,000 (paper trading)
- **Trading pairs**: BTC/USDT, ETH/USDT
- **Transaction fees**: 0.1% per trade (Binance standard)
- **Initial allocation**: Equal weighting across active strategies
  - Example: 2 strategies = 50% each
  - Switches to performance-based after first validation cycle (1-2 hours)

### Paper Trading Mechanics

#### Order Execution Simulation
- **Phase 1**: Instant fills at current market price
  - No slippage modeling for MVP simplicity
  - Execution price = latest market price from Market Data Agent
- **Phase 2**: Add basic slippage simulation
  - 0.05-0.1% slippage on fills
  - Models realistic execution conditions

#### Capital Allocation
- Meta-Strategy controls allocation percentages
- Trade Execution Agent respects current allocations when processing signals
- Example: Strategy with 30% allocation and $10,000 portfolio = $3,000 buying power

### Prerequisites & Setup Requirements

Before implementation begins, ensure the following are available:

#### Tiger Cloud Access
- [ ] Tiger Cloud service credentials (host, port, database, username, password)
- [ ] Fork creation/deletion permissions enabled on service
- [ ] CLI/API access configured for fork operations
- [ ] Connection string for main production database

#### Binance API (Phase-Dependent)
- [ ] **Phase 1-2**: No API keys required (public endpoints only for market data)
- [ ] **Phase 3**: Binance API key and secret for real trading mode
- [ ] **Phase 3**: API keys have spot trading permissions enabled

#### Development Environment
- [ ] Python 3.9+ installed
- [ ] Required libraries: `asyncio`, `asyncpg`/`psycopg2`, `pandas`, `numpy`, `python-binance`/`ccxt`, `fastapi` (Phase 2+)
- [ ] Database schema deployed to Tiger Cloud instance

---

## Next Steps

See `implementation-plan.md` for detailed implementation tasks and Day 1-3 breakdown.
