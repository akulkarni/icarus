# Icarus Trading System - User Guide

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL/TimescaleDB (or Tiger Cloud service)
- Binance account (for real trading only)

### Installation

1. **Clone repository**:
```bash
git clone <repo-url>
cd agent-6
```

2. **Install dependencies**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure database**:
```bash
cp .env.example .env
# Edit .env with your Tiger Cloud credentials
```

Tiger Cloud credentials can be found at:
- https://console.tigerdata.cloud/
- Click your service → "Connection Info"
- Copy: host, port, database, user, password, service_id

4. **Deploy schema**:
```bash
./sql/deploy_schema.sh
```

Or manually:
```bash
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -f sql/schema.sql
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
  pool_min_size: 5
  pool_max_size: 20
  timeout: 30
```

### Trading Mode
```yaml
trading:
  mode: paper  # paper or live
  initial_capital: 10000
  position_size_pct: 20
  position_exit_pct: 50
  symbols:
    - BTCUSDT
    - ETHUSDT
```

**Important**: Always start with `paper` mode for testing!

### Strategies
Enable/disable strategies:
```yaml
strategies:
  momentum:
    enabled: true
    symbol: BTCUSDT
    ma_short: 20
    ma_long: 50
    warmup_period: 50

  macd:
    enabled: true
    symbol: BTCUSDT
    fast_period: 12
    slow_period: 26
    signal_period: 9
    warmup_period: 50
```

Available strategies:
- **momentum**: Moving average crossover
- **macd**: MACD indicator signals
- **bollinger**: Bollinger Bands mean reversion
- **mean_reversion**: RSI-based mean reversion
- **breakout**: Volume-based breakout detection
- **stochastic**: Stochastic oscillator signals

### Risk Management
```yaml
risk:
  max_position_size_pct: 20  # % of allocated capital
  max_daily_loss_pct: 5      # % of total portfolio
  max_exposure_pct: 80       # % of portfolio in positions
  max_strategy_drawdown_pct: 10
```

### Meta-Strategy
```yaml
meta_strategy:
  evaluation_interval_minutes: 5
  initial_allocation: equal  # equal or custom
```

### Fork Configuration
```yaml
fork_usage:
  validation_interval_minutes: 5
  optimization_interval_minutes: 15
  scenario_analysis_enabled: true
  default_fork_ttl_seconds: 600
  validation_fork_ttl_seconds: 300
  cleanup_check_interval_seconds: 60
```

## Running the System

### Paper Trading (Safe)
Default mode, no real money:
```bash
python src/main.py
```

You should see output like:
```
2025-10-08 10:00:00 [INFO] Starting Icarus Trading System
2025-10-08 10:00:00 [INFO] Starting agent: market_data
2025-10-08 10:00:00 [INFO] Starting agent: momentum
2025-10-08 10:00:00 [INFO] Starting agent: macd
2025-10-08 10:00:00 [INFO] Starting agent: meta_strategy
2025-10-08 10:00:00 [INFO] Starting agent: execution
2025-10-08 10:00:00 [INFO] Starting agent: risk_monitor
2025-10-08 10:00:00 [INFO] Starting agent: fork_manager
2025-10-08 10:00:00 [INFO] Starting web server on http://0.0.0.0:8000
2025-10-08 10:00:00 [INFO] Dashboard available at http://localhost:8000/dashboard
```

### Real Trading (⚠️ Caution)

**WARNING**: Real trading involves real money. Only proceed if you understand the risks!

1. **Validate safety first**:
```bash
python scripts/validate_trading_safety.py
```

2. **Set Binance credentials**:
```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
```

3. **Edit config for testnet first**:
```yaml
trading:
  mode: live
binance:
  testnet: true  # Start with testnet!
  api_key: ${BINANCE_API_KEY}
  api_secret: ${BINANCE_API_SECRET}
```

4. **Test on testnet**:
```bash
python src/main.py
```

5. **After successful testing, switch to live**:
```yaml
binance:
  testnet: false  # ⚠️ Real trading!
```

6. **Run with live trading**:
```bash
python src/main.py
```

**Best practices for live trading**:
- Start with small position sizes (1-5%)
- Monitor closely for first few hours
- Set conservative risk limits
- Keep daily loss limits low (2-3%)
- Have stop-loss mechanisms
- Test all strategies in paper mode first

## Monitoring

### Dashboard
The web dashboard provides real-time monitoring:

**URL**: http://localhost:8000/dashboard

**Features**:
- Portfolio summary (cash, positions, total value)
- Active positions with P&L
- Recent trades
- Fork activity tracking
- PR narratives (system events)
- Real-time WebSocket updates

### Logs
Application logs provide detailed information:

- **Location**: `logs/icarus.log`
- **Format**: JSON (structured logging)
- **Level**: INFO (configurable to DEBUG)

**View logs**:
```bash
tail -f logs/icarus.log
```

**Filter by agent**:
```bash
grep "market_data" logs/icarus.log
```

**View as JSON**:
```bash
tail -f logs/icarus.log | jq .
```

### Database Queries

Query the database directly for detailed analysis:

```sql
-- Recent trades
SELECT * FROM trades
ORDER BY time DESC
LIMIT 10;

-- Portfolio performance
SELECT * FROM strategy_performance
ORDER BY time DESC
LIMIT 10;

-- Active positions
SELECT * FROM positions
WHERE quantity > 0;

-- Strategy allocations
SELECT * FROM current_allocations
ORDER BY strategy_name;

-- Recent trading signals
SELECT * FROM trading_signals
ORDER BY time DESC
LIMIT 20;

-- Fork activity
SELECT * FROM fork_tracking
WHERE status = 'active';

-- PR narratives
SELECT * FROM pr_events
ORDER BY time DESC
LIMIT 20;
```

## Common Operations

### Check System Health
```bash
python scripts/health_check.py
```

Shows:
- Database connectivity
- Agent status
- Recent activity
- Configuration validation

### View P&L
```bash
python scripts/show_pnl.py
```

Displays:
- Total P&L
- P&L by strategy
- Win rate
- Trade statistics

### Run Migrations
```bash
python scripts/run_migration.py sql/migrations/001_fix_win_rate_precision.sql
```

### Stop System
```bash
# Graceful shutdown (recommended)
Ctrl+C

# Force stop (if graceful fails)
pkill -f "python src/main.py"
```

The system will:
1. Stop accepting new signals
2. Wait for pending trades to complete
3. Close database connections
4. Shut down all agents gracefully

### Restart After Changes
```bash
# Stop system
Ctrl+C

# Pull latest changes
git pull

# Run migrations if needed
python scripts/run_migration.py <migration_file>

# Restart
python src/main.py
```

## Agents Overview

The system consists of multiple specialized agents:

1. **Market Data Agent** (`market_data.py`)
   - Streams real-time prices from Binance WebSocket
   - Publishes `MarketTickEvent` to event bus
   - Handles reconnection on failure
   - Tracks multiple symbols

2. **Strategy Agents** (`agents/strategies/`)
   - **Momentum**: MA crossover strategy
   - **MACD**: MACD indicator signals
   - **Bollinger**: Bollinger Bands mean reversion
   - **Mean Reversion**: RSI-based reversal signals
   - **Breakout**: Volume breakout detection
   - **Stochastic**: Stochastic oscillator signals

   Each strategy:
   - Subscribes to market data
   - Calculates technical indicators
   - Generates trading signals
   - Publishes `TradingSignalEvent`

3. **Meta-Strategy Agent** (`meta_strategy.py`)
   - Evaluates strategy performance
   - Allocates capital dynamically
   - Creates forks for validation
   - Rebalances periodically
   - Publishes `AllocationEvent`

4. **Trade Execution Agent** (`execution.py`)
   - Receives trade orders from meta-strategy
   - Executes in paper or live mode
   - Handles order placement with Binance API
   - Simulates slippage in paper mode
   - Publishes `TradeExecutedEvent`

5. **Risk Monitor Agent** (`risk_monitor.py`)
   - Enforces position limits
   - Tracks daily loss limits
   - Monitors portfolio exposure
   - Emergency halt capability
   - Publishes `RiskAlertEvent`

6. **Fork Manager Agent** (`fork_manager.py`)
   - Creates Tiger Cloud database forks
   - Manages fork lifecycle (create, track, destroy)
   - Enforces TTL (time-to-live)
   - Automatic cleanup of expired forks
   - Publishes `ForkCreatedEvent` and `ForkCompletedEvent`

7. **PR Agent** (`pr_agent.py`) - Coming Soon
   - Monitors all system events
   - Generates human-readable narratives
   - Scores event importance
   - Stores in `pr_events` table
   - Displays on dashboard

## Understanding the Event Flow

1. **Market Data** → Market Data Agent receives price from Binance
2. **Signal Generation** → Strategy Agents analyze data and generate signals
3. **Signal Evaluation** → Meta-Strategy Agent evaluates signals and creates allocations
4. **Risk Check** → Risk Monitor validates proposed trades
5. **Execution** → Execution Agent places orders (paper or live)
6. **Confirmation** → Trade results stored in database
7. **Narrative** → PR Agent generates human-readable summary

## Troubleshooting

Common issues and solutions:

### "Connection refused" to database
- Check `.env` file has correct `TIGER_HOST` and `TIGER_PASSWORD`
- Test connection: `psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE`
- Verify Tiger Cloud service is running

### "Table does not exist"
- Run schema deployment: `./sql/deploy_schema.sh`
- Or check if migrations need to run: `python scripts/run_migration.py`

### No market data received
- Check Binance WebSocket connection in logs
- Verify symbol configured: `grep "symbols:" config/app.yaml`
- Test Binance connectivity: `curl https://api.binance.com/api/v3/ping`

### Strategies not generating signals
- Wait for warmup period (need enough historical data)
- Check strategy is enabled in `config/app.yaml`
- Verify data in database: `SELECT COUNT(*) FROM market_data WHERE symbol='BTCUSDT'`

### Orders not executing
- Check risk limits in logs: `grep "risk" logs/icarus.log`
- Verify strategy has allocated capital: `SELECT * FROM current_allocations`
- Check for risk alerts: `SELECT * FROM risk_alerts ORDER BY time DESC`

### Dashboard not loading
- Verify web server started: `grep "FastAPI" logs/icarus.log`
- Check port 8000 is available: `lsof -i :8000`
- Try accessing: `curl http://localhost:8000/api/health`

For more detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Safety Guidelines

### Paper Trading
- Always start with paper trading
- Test all strategies thoroughly
- Validate risk limits work correctly
- Run for at least 24 hours before considering live trading

### Live Trading
- Start with very small position sizes (1-2%)
- Use testnet first
- Monitor actively for first few sessions
- Set conservative risk limits
- Have emergency stop procedures
- Never leave unattended initially

### Risk Management
- Never risk more than you can afford to lose
- Diversify across strategies
- Set maximum daily loss limits
- Use stop-losses
- Monitor drawdowns
- Review performance regularly

## Performance Optimization

### Database
- Use TimescaleDB compression for historical data
- Set appropriate retention policies
- Create indexes for frequently queried columns
- Monitor connection pool usage

### Agents
- Adjust warmup periods based on strategy needs
- Tune evaluation intervals for meta-strategy
- Configure appropriate fork TTLs
- Monitor memory usage with large price histories

### Network
- Place server close to exchange (low latency)
- Use stable internet connection
- Monitor WebSocket connection health
- Handle reconnections gracefully

## Next Steps

- Read the [Architecture Documentation](ARCHITECTURE.md) to understand the system design
- Explore the [API Documentation](API.md) for REST and WebSocket APIs
- Review the [Deployment Guide](DEPLOYMENT.md) for production setup
- Check the [Contributing Guide](CONTRIBUTING.md) to extend the system
- See [REAL_TRADING_SAFETY.md](REAL_TRADING_SAFETY.md) before going live

## Support

- **Issues**: Report bugs on GitHub Issues
- **Documentation**: Check `docs/` directory
- **Health Check**: Run `python scripts/health_check.py`
- **Logs**: Always check `logs/icarus.log` first
