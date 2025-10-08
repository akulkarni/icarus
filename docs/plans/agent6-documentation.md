# Agent 6: Comprehensive Documentation Suite

**Branch**: `agent6-documentation`
**Estimated Time**: 2-3 hours
**Dependencies**: None (can start immediately, but best done last)

---

## Overview

Create complete documentation suite for the Icarus trading system covering architecture, deployment, troubleshooting, and user guides.

**What you're building**:
- User guide for running the system
- Architecture documentation
- API documentation
- Troubleshooting guide
- Deployment guide
- Contributing guide

---

## Step 1: User Guide (30 min)

### 1.1 Create branch
```bash
git checkout -b agent6-documentation
```

### 1.2 Comprehensive User Guide
**File**: `docs/USER_GUIDE.md`

```markdown
# Icarus Trading System - User Guide

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL/TimescaleDB (or Tiger Cloud service)
- Binance account (for real trading)

### Installation

1. **Clone repository**:
```bash
git clone <repo-url>
cd project-planner
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure database**:
```bash
cp .env.example .env
# Edit .env with your Tiger Cloud credentials
```

4. **Deploy schema**:
```bash
./sql/deploy_schema.sh
```

5. **Run system**:
```bash
python src/main.py
```

6. **Open dashboard**:
```
http://localhost:8000/dashboard
```

## Configuration

### Database (`config/app.yaml`)
```yaml
database:
  host: ${TIGER_HOST}
  port: ${TIGER_PORT:5432}
  database: ${TIGER_DATABASE:tsdb}
  user: ${TIGER_USER:tsdbadmin}
  password: ${TIGER_PASSWORD}
```

### Trading Mode
```yaml
trading:
  mode: paper  # paper or real
  initial_capital: 10000
  position_size_pct: 20
  position_exit_pct: 50
```

### Strategies
Enable/disable strategies:
```yaml
strategies:
  momentum:
    enabled: true
    symbol: BTCUSDT
    ma_short: 20
    ma_long: 50

  macd:
    enabled: true
    symbol: BTCUSDT
    fast_period: 12
    slow_period: 26
    signal_period: 9
```

### Risk Management
```yaml
risk:
  max_position_size_pct: 20
  max_daily_loss_pct: 5
  max_exposure_pct: 80
  max_strategy_drawdown_pct: 10
```

## Running the System

### Paper Trading (Safe)
Default mode, no real money:
```bash
python src/main.py
```

### Real Trading (⚠️ Caution)
1. Validate safety first:
```bash
python scripts/validate_trading_safety.py
```

2. Set credentials:
```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
```

3. Edit config:
```yaml
trading:
  mode: real
binance:
  testnet: true  # Start with testnet!
```

4. Run:
```bash
python src/main.py
```

## Monitoring

### Dashboard
- URL: http://localhost:8000/dashboard
- Real-time portfolio updates
- Active positions
- Recent trades
- Fork activity
- PR narratives

### Logs
- Location: `logs/icarus.log`
- Format: JSON
- Level: INFO (configurable)

### Database
Query directly:
```sql
-- Recent trades
SELECT * FROM trades ORDER BY time DESC LIMIT 10;

-- Portfolio performance
SELECT * FROM strategy_performance ORDER BY time DESC LIMIT 10;

-- Active positions
SELECT * FROM positions WHERE quantity > 0;
```

## Common Operations

### Check System Health
```bash
python scripts/health_check.py
```

### View P&L
```bash
python scripts/show_pnl.py
```

### Run Migrations
```bash
python scripts/run_migration.py <migration_file>
```

### Stop System
```bash
# Graceful shutdown
Ctrl+C

# Force stop
pkill -f "python src/main.py"
```

## Agents Overview

1. **Market Data Agent**: Streams real-time prices from Binance
2. **Strategy Agents** (6): Generate trading signals
   - Momentum (MA crossover)
   - MACD
   - Bollinger Bands
   - Mean Reversion (RSI)
   - Breakout
   - Stochastic
3. **Meta-Strategy Agent**: Allocates capital across strategies
4. **Trade Execution Agent**: Executes orders (paper or real)
5. **Risk Monitor Agent**: Enforces risk limits
6. **Fork Manager Agent**: Manages database forks
7. **PR Agent**: Generates narratives

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Safety

See [REAL_TRADING_SAFETY.md](REAL_TRADING_SAFETY.md)
```

### ✅ CHECKPOINT 1: Commit
```bash
git add docs/USER_GUIDE.md
git commit -m "docs: add comprehensive user guide"
```

---

## Step 2: Architecture Documentation (30 min)

### 2.1 Architecture Overview
**File**: `docs/ARCHITECTURE.md`

```markdown
# Icarus Trading System - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Event Bus                             │
│                  (Async Pub/Sub System)                      │
└─────────────────────────────────────────────────────────────┘
          ▲                    │                    ▲
          │                    │                    │
          │                    ▼                    │
┌─────────┴────────┐  ┌─────────────────┐  ┌──────┴─────────┐
│  Market Data     │  │   6 Strategy    │  │  Trade Exec    │
│     Agent        │  │     Agents      │  │     Agent      │
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
```

## Components

### Event Bus (`src/core/event_bus.py`)
- Async pub/sub messaging
- Type-safe event routing
- Queue-based delivery
- Decouples agents

### Agents (`src/agents/`)

#### Base Agent (`base.py`)
Abstract base class:
- Lifecycle management
- Event subscription
- Health monitoring
- Error handling

Types:
- `BaseAgent`: Basic agent
- `EventDrivenAgent`: Subscribes to events
- `PeriodicAgent`: Runs on schedule
- `StatefulAgent`: Maintains state

#### Market Data Agent (`market_data.py`)
- Connects to Binance WebSocket
- Streams real-time price data
- Publishes `MarketTickEvent`
- Handles reconnection

#### Strategy Agents (`agents/strategies/`)
All inherit from `StrategyAgent`:
1. **Momentum** - MA crossover
2. **MACD** - MACD indicator
3. **Bollinger Bands** - Price bands
4. **Mean Reversion** - RSI
5. **Breakout** - Volume breakout
6. **Stochastic** - Stochastic oscillator

Each:
- Subscribes to market data
- Calculates indicators
- Generates `TradingSignalEvent`

#### Meta-Strategy Agent (`meta_strategy.py`)
- Evaluates strategy performance
- Allocates capital dynamically
- Creates forks for validation
- Publishes `AllocationEvent`

#### Trade Execution Agent (`execution.py`)
- Receives trade orders
- Paper trading (simulated)
- Real trading (Binance API)
- Publishes `TradeExecutedEvent`

#### Risk Monitor Agent (`risk_monitor.py`)
- Enforces position limits
- Daily loss tracking
- Exposure monitoring
- Emergency halt capability

#### Fork Manager Agent (`fork_manager.py`)
- Creates Tiger Cloud forks
- Manages fork lifecycle
- Tracks fork usage
- Destroys expired forks

#### PR Agent (`pr_agent.py`)
- Monitors all events
- Generates narratives
- Importance scoring
- Dashboard display

### Database (`src/core/database.py`)
- AsyncPG connection pool
- Async context managers
- Connection lifecycle
- Error handling

### Models (`src/models/`)
- `events.py`: All event types
- `trading.py`: Trading models
- Immutable dataclasses
- Type safety

### Web Dashboard (`src/web/`)
- FastAPI backend
- REST endpoints
- WebSocket streaming
- Static HTML/CSS/JS
- Real-time updates

## Data Flow

### Trading Signal Flow

1. **Market Data**: Binance → Market Data Agent
2. **Signal Generation**: Market Data Agent → Strategy Agent
3. **Signal Evaluation**: Strategy Agent → Meta-Strategy Agent
4. **Order Creation**: Meta-Strategy Agent → Risk Monitor
5. **Risk Check**: Risk Monitor → Trade Execution Agent
6. **Trade Execution**: Trade Execution Agent → Binance (or paper)
7. **Confirmation**: Trade Execution Agent → Database
8. **Narrative**: PR Agent observes, generates narrative

### Fork Workflow

1. Meta-Strategy requests fork
2. Fork Manager creates Tiger Cloud fork
3. Fork Manager publishes `ForkCreatedEvent`
4. Requesting agent uses fork for validation
5. Agent publishes `ForkCompletedEvent`
6. Fork Manager destroys fork

## Database Schema

### Core Tables
- `crypto_prices`: OHLCV market data (hypertable)
- `trades`: Trade execution history (hypertable)
- `positions`: Current open positions
- `strategy_performance`: Performance metrics (hypertable)

### Fork Management
- `fork_tracking`: Active forks
- `fork_results`: Fork outcomes

### PR/Monitoring
- `pr_events`: Generated narratives (hypertable)
- `system_health`: Health metrics (hypertable)

## Configuration

- `config/app.yaml`: Main configuration
- `config/database.yaml`: Database config (optional)
- `.env`: Environment variables (secrets)

## Design Patterns

### Event-Driven Architecture
- Loose coupling
- Async processing
- Scalable

### Agent Pattern
- Self-contained
- Single responsibility
- Observable

### Pub/Sub Messaging
- Decoupled communication
- Type-safe events
- Async delivery

### Database Forking
- Parallel validation
- No main DB impact
- Automatic cleanup

## Technology Stack

- **Language**: Python 3.10+
- **Async**: asyncio
- **Database**: PostgreSQL + TimescaleDB
- **Cloud**: Tiger Cloud (Timescale)
- **Web**: FastAPI
- **Exchange**: Binance API
- **Testing**: pytest, pytest-asyncio
```

### ✅ CHECKPOINT 2: Commit & Review
```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add architecture documentation"
git push -u origin agent6-documentation
```

**🛑 REQUEST REVIEW**: "Agent 6 - Checkpoint 2. User guide and architecture docs complete."

---

## Step 3: Troubleshooting Guide (20 min)

**File**: `docs/TROUBLESHOOTING.md`

```markdown
# Troubleshooting Guide

## Installation Issues

### "ModuleNotFoundError: No module named 'X'"
**Cause**: Missing dependency
**Solution**:
```bash
pip install -r requirements.txt
```

### "Permission denied" on scripts
**Cause**: Script not executable
**Solution**:
```bash
chmod +x scripts/*.py
chmod +x sql/*.sh
```

## Database Issues

### "Connection refused" to database
**Causes**:
1. Tiger Cloud credentials wrong
2. Network/firewall issue
3. Service not running

**Solutions**:
```bash
# Verify credentials
cat .env

# Test connection
python scripts/health_check.py

# Check network
ping <TIGER_HOST>
```

### "Table does not exist"
**Cause**: Schema not deployed
**Solution**:
```bash
./sql/deploy_schema.sh
```

### "Hypertable already exists"
**Cause**: Trying to recreate hypertable
**Solution**: Use `IF NOT EXISTS` or drop first:
```sql
DROP TABLE IF EXISTS table_name CASCADE;
```

## Agent Issues

### Agent crashes on startup
**Symptoms**: Agent starts then stops immediately
**Solutions**:
1. Check logs: `tail -f logs/icarus.log`
2. Verify config: `python -c "import yaml; print(yaml.safe_load(open('config/app.yaml')))"`
3. Test imports: `python -c "from src.agents.market_data import MarketDataAgent"`

### No market data received
**Causes**:
1. Binance WebSocket connection failed
2. Symbol not configured
3. Network issue

**Solutions**:
```bash
# Check config
grep -A5 "market_data:" config/app.yaml

# Test Binance connection manually
python -c "from binance.client import Client; c = Client(); print(c.get_server_time())"

# Check logs for errors
grep "market_data" logs/icarus.log
```

### Strategy not generating signals
**Causes**:
1. Not enough data (warmup period)
2. Strategy disabled
3. No crossover/condition met

**Solutions**:
```bash
# Check if enabled
grep -A3 "strategy_name:" config/app.yaml

# Check warmup period
# Wait for strategy.warmup_period data points

# Check database for prices
psql -c "SELECT COUNT(*) FROM crypto_prices WHERE symbol='BTCUSDT' AND time > NOW() - INTERVAL '1 hour';"
```

## Trading Issues

### Orders not executing
**Causes**:
1. Risk limits exceeded
2. Insufficient balance (real mode)
3. Strategy not allocated capital

**Solutions**:
```bash
# Check risk alerts
psql -c "SELECT * FROM risk_alerts ORDER BY time DESC LIMIT 5;"

# Check allocations
psql -c "SELECT * FROM strategy_performance ORDER BY time DESC LIMIT 5;"

# Check logs
grep "execution" logs/icarus.log | tail -20
```

### Binance API errors
**Error**: "Invalid API key"
**Solution**: Verify credentials in `.env`

**Error**: "Insufficient balance"
**Solution**: Check Binance account balance

**Error**: "Timestamp outside allowed"
**Solution**: Sync system clock:
```bash
sudo ntpdate -s time.nist.gov
```

## Dashboard Issues

### Dashboard won't load
**Causes**:
1. Web server not started
2. Port 8000 in use
3. CORS issue

**Solutions**:
```bash
# Check if running
lsof -i :8000

# Check logs
grep "FastAPI" logs/icarus.log

# Try different port
# Edit src/web/server.py, change port
```

### WebSocket not connecting
**Symptoms**: Connection status shows "Disconnected"
**Solutions**:
1. Check browser console for errors
2. Verify WebSocket endpoint: `ws://localhost:8000/ws`
3. Check CORS settings in `src/web/api.py`

### No data showing on dashboard
**Causes**:
1. No data in database
2. API endpoints failing
3. Database connection issue

**Solutions**:
```bash
# Test API endpoints
curl http://localhost:8000/api/portfolio
curl http://localhost:8000/api/trades/recent

# Check database
psql -c "SELECT COUNT(*) FROM trades;"
```

## Performance Issues

### High CPU usage
**Causes**:
1. Too many strategies
2. Calculation-heavy indicators
3. Memory leaks

**Solutions**:
- Disable unused strategies
- Reduce history size in strategy params
- Monitor with: `top -p $(pgrep -f "python src/main.py")`

### High memory usage
**Causes**:
1. Price history growing unbounded
2. Too many event subscriptions
3. Connection pool leaks

**Solutions**:
- Check `max_history` in strategy configs
- Restart system periodically
- Monitor: `ps aux | grep python`

## Fork Issues

### Forks not being created
**Causes**:
1. Tiger Cloud quota exceeded
2. Fork Manager agent not running
3. API credentials wrong

**Solutions**:
```bash
# Check quota
# Log into Tiger Cloud console

# Check agent
grep "fork_manager" logs/icarus.log

# Test fork creation manually
python -c "from src.agents.fork_manager import ForkManager; ..."
```

### Forks not being destroyed
**Cause**: TTL not expiring or cleanup failed
**Solution**:
```bash
# Check fork_tracking table
psql -c "SELECT * FROM fork_tracking WHERE status='active';"

# Manual cleanup
psql -c "UPDATE fork_tracking SET status='expired' WHERE fork_id='...';"
```

## Getting Help

1. **Check logs**: `logs/icarus.log`
2. **Check database**: Query relevant tables
3. **Check config**: Verify `config/app.yaml`
4. **Run health check**: `python scripts/health_check.py`
5. **Search issues**: GitHub issues
6. **Ask community**: Discord/Slack (if available)

## Debug Mode

Enable debug logging:
```yaml
# config/app.yaml
logging:
  level: DEBUG
```

Restart system to see detailed logs.
```

### ✅ CHECKPOINT 3: Commit
```bash
git add docs/TROUBLESHOOTING.md
git commit -m "docs: add comprehensive troubleshooting guide"
```

---

## Step 4: API & Deployment Docs (30 min)

### 4.1 API Documentation
**File**: `docs/API.md`

```markdown
# API Documentation

## REST API

Base URL: `http://localhost:8000`

### Health & Status

#### GET /
Health check
```json
{
  "status": "running",
  "service": "icarus-trading-system",
  "timestamp": "2024-01-15T10:30:00"
}
```

#### GET /api/health
Detailed health status
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

### Portfolio

#### GET /api/portfolio
Get portfolio summary

**Response**:
```json
{
  "positions": [
    {
      "strategy_name": "momentum",
      "symbol": "BTCUSDT",
      "quantity": 0.5,
      "avg_entry_price": 50000.00,
      "current_value": 25000.00,
      "unrealized_pnl": 500.00,
      "last_updated": "2024-01-15T10:30:00"
    }
  ],
  "strategies": [
    {
      "strategy_name": "momentum",
      "portfolio_value": 10500.00,
      "cash_balance": 5000.00,
      "total_pnl": 500.00,
      "allocation_pct": 40.0,
      "is_active": true
    }
  ],
  "timestamp": "2024-01-15T10:30:00"
}
```

### Trades

#### GET /api/trades/recent?limit=N
Get recent trades

**Parameters**:
- `limit` (optional): Number of trades (default: 50)

**Response**:
```json
{
  "trades": [
    {
      "time": "2024-01-15T10:25:00",
      "strategy_name": "momentum",
      "symbol": "BTCUSDT",
      "side": "buy",
      "quantity": 0.5,
      "price": 50000.00,
      "value": 25000.00,
      "fee": 25.00,
      "trade_mode": "paper"
    }
  ]
}
```

### Forks

#### GET /api/forks/active
Get active database forks

**Response**:
```json
{
  "forks": [
    {
      "fork_id": "fork_abc123",
      "requesting_agent": "meta_strategy",
      "purpose": "validation",
      "created_at": "2024-01-15T10:20:00",
      "ttl_seconds": 3600,
      "status": "active"
    }
  ]
}
```

### PR Narratives

#### GET /api/pr/narratives?limit=N
Get PR narratives

**Parameters**:
- `limit` (optional): Number of narratives (default: 20)

**Response**:
```json
{
  "narratives": [
    {
      "time": "2024-01-15T10:30:00",
      "narrative": "💰 momentum strategy bought 0.5000 BTCUSDT at $50000.00",
      "event_category": "trade",
      "importance_score": 7
    }
  ]
}
```

## WebSocket API

### WS /ws
Real-time event stream

**Connection**: `ws://localhost:8000/ws`

**Message Format**:
```json
{
  "type": "trade",
  "data": {
    "strategy_name": "momentum",
    "symbol": "BTCUSDT",
    "side": "buy",
    "quantity": "0.5",
    "price": "50000.00"
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

**Event Types**:
- `market`: Market price ticks
- `signal`: Trading signals
- `trade`: Trade executions
- `allocation`: Capital allocations
- `fork_created`: Fork created
- `fork_completed`: Fork completed

## Dashboard

#### GET /dashboard
Serve dashboard HTML
```
http://localhost:8000/dashboard
```

## Error Responses

All endpoints return errors in format:
```json
{
  "error": "Error message",
  "detail": "Detailed error information"
}
```

**Status Codes**:
- 200: Success
- 400: Bad request
- 404: Not found
- 500: Server error
```

### 4.2 Deployment Guide
**File**: `docs/DEPLOYMENT.md`

```markdown
# Deployment Guide

## Production Deployment

### Requirements
- Ubuntu 20.04+ or similar
- Python 3.10+
- Systemd
- Tiger Cloud account
- (Optional) Nginx for reverse proxy

### Installation

1. **Create deploy user**:
```bash
sudo useradd -m -s /bin/bash icarus
sudo su - icarus
```

2. **Clone and setup**:
```bash
git clone <repo-url> /opt/icarus
cd /opt/icarus
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure**:
```bash
cp .env.example .env
# Edit .env with production credentials
nano .env

# Edit config for production
nano config/app.yaml
```

4. **Deploy schema**:
```bash
./sql/deploy_schema.sh
```

5. **Test run**:
```bash
python src/main.py
# Verify no errors, then Ctrl+C
```

### Systemd Service

**File**: `/etc/systemd/system/icarus.service`

```ini
[Unit]
Description=Icarus Trading System
After=network.target

[Service]
Type=simple
User=icarus
WorkingDirectory=/opt/icarus
Environment="PATH=/opt/icarus/venv/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/icarus/.env
ExecStart=/opt/icarus/venv/bin/python src/main.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/icarus/output.log
StandardError=append:/var/log/icarus/error.log

[Install]
WantedBy=multi-user.target
```

**Setup**:
```bash
sudo mkdir -p /var/log/icarus
sudo chown icarus:icarus /var/log/icarus
sudo systemctl daemon-reload
sudo systemctl enable icarus
sudo systemctl start icarus
sudo systemctl status icarus
```

### Nginx Reverse Proxy (Optional)

**File**: `/etc/nginx/sites-available/icarus`

```nginx
server {
    listen 80;
    server_name icarus.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable**:
```bash
sudo ln -s /etc/nginx/sites-available/icarus /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Monitoring

**Logs**:
```bash
# System logs
sudo journalctl -u icarus -f

# Application logs
tail -f /opt/icarus/logs/icarus.log

# Web logs
tail -f /var/log/icarus/output.log
```

**Health Check**:
```bash
curl http://localhost:8000/api/health
```

### Backup

**Database**:
```bash
# Automated backup (cron)
pg_dump -h $TIGER_HOST -U $TIGER_USER $TIGER_DATABASE > backup_$(date +%Y%m%d).sql
```

**Configuration**:
```bash
tar -czf config_backup.tar.gz config/ .env
```

### Updates

**File**: `deploy/update.sh`

```bash
#!/bin/bash
set -e

echo "Pulling latest code..."
git pull origin main

echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "Running migrations..."
./scripts/run_migration.py

echo "Running tests..."
pytest

echo "Restarting service..."
sudo systemctl restart icarus

echo "Deployment complete!"
```

### Security

1. **Firewall**:
```bash
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable
```

2. **API Keys**:
- Store in `.env` only
- Restrict Binance API permissions
- Rotate regularly

3. **Database**:
- Use strong passwords
- Enable SSL connections
- Restrict IP access

### Troubleshooting

See main [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
```

### ✅ CHECKPOINT 4: Commit & Review
```bash
git add docs/API.md docs/DEPLOYMENT.md
git commit -m "docs: add API and deployment documentation"
git push
```

**🛑 REQUEST REVIEW**: "Agent 6 - Checkpoint 4. API and deployment docs complete."

---

## Step 5: Final Polish & README (20 min)

### 5.1 Update main README
**File**: `README.md` (comprehensive update)

```markdown
# 🚀 Icarus Trading System

Multi-agent cryptocurrency trading system with dynamic portfolio management and database forking for parallel strategy validation.

## Features

✅ **Multi-Strategy Trading**
- 6 strategies: Momentum, MACD, Bollinger Bands, Mean Reversion, Breakout, Stochastic
- Dynamic capital allocation
- Automated rebalancing

✅ **Database Forking**
- Parallel strategy validation using Tiger Cloud forks
- No impact on main database
- Automatic cleanup

✅ **Real-Time Dashboard**
- Live portfolio updates
- Active positions and trades
- Fork activity monitoring
- PR narratives

✅ **Paper & Real Trading**
- Safe paper trading mode
- Binance API integration
- Slippage simulation
- Comprehensive risk controls

✅ **Agent-Based Architecture**
- Event-driven design
- Loosely coupled agents
- Async/await throughout

## Quick Start

```bash
# Install
git clone <repo-url>
cd project-planner
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with Tiger Cloud credentials

# Deploy schema
./sql/deploy_schema.sh

# Run
python src/main.py

# Open dashboard
open http://localhost:8000/dashboard
```

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Complete usage guide
- **[Architecture](docs/ARCHITECTURE.md)** - System design
- **[API Docs](docs/API.md)** - REST and WebSocket API
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues
- **[Deployment](docs/DEPLOYMENT.md)** - Production setup
- **[Real Trading Safety](docs/REAL_TRADING_SAFETY.md)** - Safety checklist

## Project Structure

```
project-planner/
├── config/              # Configuration files
│   └── app.yaml        # Main config
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── sql/                # Database schema & migrations
├── src/
│   ├── agents/         # All trading agents
│   │   ├── strategies/ # Strategy implementations
│   │   ├── execution.py
│   │   ├── meta_strategy.py
│   │   ├── risk_monitor.py
│   │   ├── fork_manager.py
│   │   └── pr_agent.py
│   ├── core/           # Core infrastructure
│   │   ├── event_bus.py
│   │   ├── database.py
│   │   └── config.py
│   ├── models/         # Data models
│   ├── web/            # FastAPI dashboard
│   └── main.py         # Entry point
└── tests/              # Test suite
```

## Agents

1. **Market Data** - Streams prices from Binance
2. **6 Strategies** - Generate trading signals
3. **Meta-Strategy** - Allocates capital dynamically
4. **Execution** - Executes trades (paper/real)
5. **Risk Monitor** - Enforces limits
6. **Fork Manager** - Manages database forks
7. **PR Agent** - Generates narratives

## Tech Stack

- **Python 3.10+** with asyncio
- **TimescaleDB** (PostgreSQL + time-series)
- **Tiger Cloud** for database forking
- **Binance API** for trading
- **FastAPI** for web dashboard
- **pytest** for testing

## Development

```bash
# Run tests
pytest -v

# Coverage
pytest --cov=src

# Linting
flake8 src/
black src/

# Type checking
mypy src/
```

## Safety ⚠️

**This system can trade with real money.**

- Always start with paper trading
- Test on Binance testnet first
- Use conservative risk limits
- Monitor actively during first trades
- See [REAL_TRADING_SAFETY.md](docs/REAL_TRADING_SAFETY.md)

## License

[Your License]

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## Support

- Issues: GitHub Issues
- Docs: `docs/` directory
- Health check: `python scripts/health_check.py`
```

### 5.2 Contributing Guide
**File**: `CONTRIBUTING.md`

```markdown
# Contributing to Icarus

## Development Setup

1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Install dependencies: `pip install -r requirements.txt`
4. Make changes
5. Run tests: `pytest`
6. Commit: `git commit -m "feat: add my feature"`
7. Push: `git push origin feature/my-feature`
8. Create Pull Request

## Code Standards

### Style
- Follow PEP 8
- Use Black for formatting: `black src/`
- Use type hints
- Max line length: 100

### Testing
- Write tests for all new features
- Maintain >80% coverage
- Use pytest fixtures
- Mock external dependencies

### Commits
Follow Conventional Commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Refactoring
- `chore:` Maintenance

### Documentation
- Update relevant docs
- Add docstrings to all functions
- Include examples

## Project Principles

- **DRY**: Don't Repeat Yourself
- **YAGNI**: You Aren't Gonna Need It
- **TDD**: Test-Driven Development
- **Event-Driven**: Use event bus
- **Async**: Use async/await

## Adding a New Strategy

1. Create `src/agents/strategies/my_strategy.py`
2. Inherit from `StrategyAgent`
3. Implement `analyze()` method
4. Add tests in `tests/test_agents/test_strategies/`
5. Update `src/agents/strategies/__init__.py`
6. Add config to `config/app.yaml`
7. Document in `docs/strategies/`

## Pull Request Process

1. Ensure all tests pass
2. Update documentation
3. Add entry to CHANGELOG
4. Request review
5. Address feedback
6. Squash commits before merge

## Questions?

Open an issue or discussion on GitHub.
```

### ✅ FINAL: Commit & Review
```bash
git add README.md CONTRIBUTING.md
git commit -m "docs: update README and add contributing guide"
git push
```

**🛑 FINAL REVIEW**: "Agent 6 - Complete. All documentation finished."

---

## Testing Checklist

- [ ] All documentation files created
- [ ] No broken links
- [ ] Code examples work
- [ ] Markdown renders correctly
- [ ] Covers all features
- [ ] Troubleshooting comprehensive
- [ ] Deployment steps tested

## Success Criteria

✅ User guide complete
✅ Architecture documented
✅ API documentation complete
✅ Troubleshooting guide comprehensive
✅ Deployment guide tested
✅ README updated
✅ Contributing guide added
✅ All docs reviewed
