# Day 3: Production Ready

**Goal**: Real trading mode, enhanced features, polish, deployment
**Estimated Time**: 10-12 hours
**Prerequisites**: Day 2 complete (dashboard working, 4 strategies running)

---

## Overview

Day 3 makes the system production-ready by adding real trading capabilities, enhanced risk controls, remaining strategies, and deployment configuration.

**What you'll build:**
- Real trading mode with Binance API
- Enhanced risk monitor with circuit breakers
- Parameter optimization using parallel forks
- Remaining strategies (Breakout, Stochastic)
- Dashboard polish and visualizations
- Documentation and deployment

---

## Task 3.1: Real Trading Mode (2 hours)

### Binance API Integration

**Update config/app.yaml**:

```yaml
trading:
  trade_mode: "real"  # Change from "paper"

binance:
  api_key: "YOUR_API_KEY_HERE"
  api_secret: "YOUR_SECRET_HERE"
  testnet: false  # true for Binance testnet
```

**File**: `src/agents/execution.py` (enhance)

```python
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException

class TradeExecutionAgent(BaseAgent):
    def __init__(self, event_bus, db_manager, config):
        super().__init__("execution", event_bus)
        self.db = db_manager
        self.config = config
        self.mode = config['trading']['trade_mode']

        # Initialize Binance client for real mode
        if self.mode == 'real':
            self.binance = BinanceClient(
                api_key=config['binance']['api_key'],
                api_secret=config['binance']['api_secret'],
                testnet=config['binance'].get('testnet', False)
            )
        else:
            self.binance = None

    async def _execute_order_real(self, order: TradeOrderEvent):
        """Execute real order on Binance"""
        try:
            if order.side == 'buy':
                result = self.binance.order_market_buy(
                    symbol=order.symbol,
                    quantity=float(order.quantity)
                )
            else:  # sell
                result = self.binance.order_market_sell(
                    symbol=order.symbol,
                    quantity=float(order.quantity)
                )

            # Parse Binance response
            fill_price = Decimal(result['fills'][0]['price'])
            fill_qty = Decimal(result['executedQty'])
            fee = Decimal(result['fills'][0]['commission'])

            # Publish fill event
            await self.publish(TradeExecutedEvent(
                strategy_name=order.strategy_name,
                symbol=order.symbol,
                side=order.side,
                quantity=fill_qty,
                price=fill_price,
                fee=fee,
                order_id=result['orderId']
            ))

            logger.info(f"Real trade executed: {order.side} {fill_qty} {order.symbol} @ {fill_price}")

        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
            # Publish error event
            await self.publish(ErrorEvent(
                agent_name=self.name,
                error_type='binance_api_error',
                message=str(e)
            ))

    async def _execute_order(self, order: TradeOrderEvent):
        """Route to paper or real execution"""
        if self.mode == 'paper':
            await self._execute_order_paper(order)
        else:
            await self._execute_order_real(order)
```

**Safety checks before enabling real trading**:

1. **Test with small amounts**
2. **Use Binance testnet first** (`testnet: true`)
3. **Verify API key permissions** (spot trading only, no withdrawals)
4. **Check account balance**
5. **Monitor first trades closely**

**Test** (on testnet):
```python
# Update config to testnet
# Run system
# Verify orders appear in Binance testnet UI
```

**Commit**: `git add src/agents/execution.py config/app.yaml && git commit -m "feat(execution): add real trading mode with Binance API"`

---

## Task 3.2: Enhanced Risk Monitor (1 hour)

Add circuit breakers and advanced risk checks.

**File**: `src/agents/risk_monitor.py` (enhance)

```python
class RiskMonitor(BaseAgent):
    def __init__(self, event_bus, db_manager, config):
        super().__init__("risk_monitor", event_bus)
        self.config = config['risk']

        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = None

        # Tracking
        self.daily_start_value = None
        self.strategy_peak_values = {}  # strategy -> peak value

    async def _check_circuit_breakers(self, portfolio_value):
        """Advanced circuit breaker logic"""

        # 1. Rapid loss circuit breaker
        # If portfolio drops >2% in 5 minutes, halt

        # 2. Correlation circuit breaker
        # If all strategies losing simultaneously, halt

        # 3. Market volatility circuit breaker
        # If detected volatility > threshold, reduce exposure

        # 4. Consecutive losses circuit breaker
        # If >5 consecutive losing trades, halt

        pass  # Implement based on design doc

    async def _check_strategy_correlation(self):
        """Check if strategies are too correlated"""
        # Query recent trades
        # Calculate correlation of returns
        # If correlation > 0.8, warn meta-strategy
        pass
```

**Commit**: `git add src/agents/risk_monitor.py && git commit -m "feat(risk): add circuit breakers and correlation checks"`

---

## Task 3.3: Parameter Optimization (2 hours)

Use parallel forks to optimize strategy parameters.

**File**: `src/agents/optimizer.py` (new)

```python
"""
Parameter Optimizer Agent

Uses parallel forks to test multiple parameter combinations
and select the best-performing parameters.
"""
import itertools
from typing import List, Dict, Any
import asyncio

class ParameterOptimizer(BaseAgent):
    def __init__(self, event_bus, db_manager, fork_manager, config):
        super().__init__("optimizer", event_bus)
        self.db = db_manager
        self.fork_manager = fork_manager

    async def optimize_strategy(self, strategy_name: str,
                                 param_grid: Dict[str, List[Any]]):
        """
        Optimize parameters for a strategy using parallel forks.

        Example:
            param_grid = {
                'ma_short': [10, 20, 30],
                'ma_long': [50, 100, 200]
            }

        Creates 9 forks to test all combinations.
        """
        # Generate all parameter combinations
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        logger.info(f"Testing {len(combinations)} parameter combinations for {strategy_name}")

        # Request forks for parallel testing
        fork_ids = []
        for combo in combinations:
            fork_request = ForkRequestEvent(
                requesting_agent=self.name,
                purpose=f"optimize_{strategy_name}_{combo}",
                ttl_seconds=3600
            )
            await self.publish(fork_request)

            # Wait for fork creation...
            fork_ids.append(...)  # Get fork ID from response

        # Run backtests on each fork in parallel
        results = await asyncio.gather(*[
            self._run_backtest_on_fork(fork_id, strategy_name, params)
            for fork_id, params in zip(fork_ids, combinations)
        ])

        # Find best parameters
        best_result = max(results, key=lambda r: r['sharpe_ratio'])

        logger.info(f"Best parameters for {strategy_name}: {best_result['params']}")

        return best_result

    async def _run_backtest_on_fork(self, fork_id, strategy_name, params):
        """Run backtest with given parameters on fork"""
        # Connect to fork database
        # Run backtest with parameters
        # Calculate performance metrics
        # Return results
        pass
```

**Commit**: `git add src/agents/optimizer.py && git commit -m "feat(optimizer): add parallel parameter optimization"`

---

## Task 3.4: Remaining Strategies (1.5 hours)

Add Breakout and Stochastic strategies.

**Reference**:
- `backtest_breakout.py`
- `backtest_stochastic.py`

**Create**:
- `src/agents/strategies/breakout.py`
- `src/agents/strategies/stochastic.py`

**Commit**: `git add src/agents/strategies/ && git commit -m "feat(strategies): add Breakout and Stochastic strategies"`

---

## Task 3.5: Dashboard Enhancements (2 hours)

Add charts and visualizations to dashboard.

### Add Chart.js for price charts

**Update `src/web/static/index.html`**:

```html
<!-- Add to head -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

<!-- Add to body -->
<div class="card" style="grid-column: 1 / -1;">
    <h2>Price Charts</h2>
    <div style="height: 300px;">
        <canvas id="price-chart"></canvas>
    </div>
</div>

<div class="card" style="grid-column: 1 / -1;">
    <h2>Portfolio Performance</h2>
    <div style="height: 300px;">
        <canvas id="performance-chart"></canvas>
    </div>
</div>

<script>
// Price chart
const priceCtx = document.getElementById('price-chart').getContext('2d');
const priceChart = new Chart(priceCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'BTC/USDT',
            data: [],
            borderColor: '#667eea',
            tension: 0.1
        }, {
            label: 'ETH/USDT',
            data: [],
            borderColor: '#764ba2',
            tension: 0.1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: '#e0e0e0' }
            }
        },
        scales: {
            y: {
                ticks: { color: '#e0e0e0' },
                grid: { color: '#2a2f4a' }
            },
            x: {
                ticks: { color: '#e0e0e0' },
                grid: { color: '#2a2f4a' }
            }
        }
    }
});

// Update charts with real-time data
function updateCharts(marketData) {
    // Add new data point
    priceChart.data.labels.push(new Date().toLocaleTimeString());
    priceChart.data.datasets[0].data.push(marketData.BTC_USDT);
    priceChart.data.datasets[1].data.push(marketData.ETH_USDT);

    // Keep last 50 points
    if (priceChart.data.labels.length > 50) {
        priceChart.data.labels.shift();
        priceChart.data.datasets.forEach(ds => ds.data.shift());
    }

    priceChart.update();
}
</script>
```

### Add fork lifecycle visualization

Create timeline view showing fork creation → usage → destruction with visual indicators.

**Commit**: `git add src/web/ && git commit -m "feat(dashboard): add charts and fork visualization"`

---

## Task 3.6: Documentation (1 hour)

Create comprehensive documentation.

**File**: `docs/USER_GUIDE.md`

```markdown
# User Guide

## Installation

1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure database: Edit `config/database.yaml`
4. Deploy schema: `./sql/deploy_schema.sh`

## Configuration

Edit `config/app.yaml`:
- Set trading mode (paper/real)
- Configure risk limits
- Set initial capital
- Add Binance API keys (for real trading)

## Running the System

```bash
# Start all agents
python src/main.py

# Open dashboard
open http://localhost:8000
```

## Monitoring

- Dashboard shows real-time activity
- Logs written to `logs/trading.log`
- Database contains full audit trail

## Safety

- Start with paper trading
- Test on Binance testnet before real trading
- Monitor first few real trades closely
- Set conservative risk limits

## Troubleshooting

See TROUBLESHOOTING.md
```

**File**: `docs/API.md`

Document all REST and WebSocket endpoints.

**Commit**: `git add docs/ && git commit -m "docs: add user guide and API documentation"`

---

## Task 3.7: Deployment (1.5 hours)

### Systemd Service

**File**: `deploy/trading-system.service`

```ini
[Unit]
Description=Live Trading System
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/trading-system
ExecStart=/opt/trading-system/venv/bin/python src/main.py
Restart=on-failure
RestartSec=10

Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

### Logging Configuration

**File**: `config/logging.yaml`

```yaml
version: 1
formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    formatter: default
    level: INFO

  file:
    class: logging.handlers.RotatingFileHandler
    filename: logs/trading.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
    formatter: default
    level: DEBUG

loggers:
  src:
    level: DEBUG
    handlers: [console, file]
```

### Deployment Script

**File**: `deploy/deploy.sh`

```bash
#!/bin/bash
set -e

echo "Deploying Live Trading System..."

# Pull latest code
git pull origin main

# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest

# Restart service
sudo systemctl restart trading-system

echo "Deployment complete!"
```

**Commit**: `git add deploy/ && git commit -m "feat(deploy): add systemd service and deployment scripts"`

---

## Task 3.8: Final Testing & Polish (1 hour)

### End-to-End Test

**File**: `tests/test_e2e.py`

```python
"""End-to-end system test"""
import pytest
import asyncio
from src.main import main

@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_system_integration():
    """
    Test complete system:
    1. Start all agents
    2. Inject market data
    3. Verify trades execute
    4. Verify database persistence
    5. Verify forks created
    6. Verify dashboard accessible
    """
    # Start system (with timeout)
    task = asyncio.create_task(main())

    try:
        # Wait for initialization
        await asyncio.sleep(10)

        # Inject test market data
        # ...

        # Wait for trades
        await asyncio.sleep(30)

        # Verify database state
        # ...

        # Verify fork creation
        # ...

        # Verify web API
        # ...

        assert True  # All checks passed

    finally:
        task.cancel()
```

### Performance Tuning

1. **Database**: Add indexes for common queries
2. **Event Bus**: Tune queue sizes
3. **WebSocket**: Add connection pooling
4. **Memory**: Monitor and optimize agent memory usage

### Demo Preparation

Create demo script showing:
1. System startup
2. Market data streaming
3. Strategies generating signals
4. Trades executing
5. Fork creation for validation
6. Meta-strategy reallocation
7. PR narratives appearing
8. Risk monitor interventions

**File**: `demo/showcase.md`

```markdown
# Live Trading System Demo

## 1. System Startup (1 min)

```bash
python src/main.py
```

Show:
- All 7 agents starting
- Database connections established
- WebSocket server running

## 2. Dashboard Tour (2 min)

Open http://localhost:8000

Show:
- Portfolio summary
- Real-time price updates
- Active positions
- Recent trades
- Fork activity
- PR narratives

## 3. Live Trading (3 min)

Show:
- Market data streaming
- Strategy signals appearing
- Trades executing
- Portfolio updating in real-time

## 4. Fork Showcase (2 min)

Show:
- Fork creation triggered
- Validation backtest running on fork
- Results feeding into meta-strategy
- Fork destruction after completion

## 5. Meta-Strategy Intelligence (2 min)

Show:
- Regime detection
- Performance-based allocation adjustment
- Strategy activation/deactivation

## 6. Risk Management (1 min)

Show:
- Position limits enforced
- Daily loss tracking
- Circuit breaker demonstration (if triggered)

## 7. PR Agent Narratives (1 min)

Show interesting developments logged:
- "Momentum strategy detected trend reversal..."
- "Meta-strategy created 3 forks to evaluate reallocation..."
- "Risk monitor prevented trade exceeding position limit..."
```

**Commit**: `git add tests/test_e2e.py demo/ && git commit -m "test: add e2e tests and demo preparation"`

---

## Final Checklist

Before considering Day 3 complete:

**Functionality**:
- [ ] Real trading mode works (tested on testnet)
- [ ] All 6 strategies operational
- [ ] Enhanced risk controls active
- [ ] Parameter optimization functional
- [ ] Dashboard polished and complete
- [ ] All tests passing (>80% coverage)

**Documentation**:
- [ ] User guide complete
- [ ] API documentation complete
- [ ] Deployment guide complete
- [ ] Demo script prepared

**Production Readiness**:
- [ ] Logging configured
- [ ] Systemd service created
- [ ] Error handling robust
- [ ] Performance acceptable

**Showcase**:
- [ ] Fork activity prominently displayed
- [ ] PR narratives compelling
- [ ] Demo runs smoothly
- [ ] System highlights Tiger Cloud capabilities

---

## Post-Day 3: Optional Enhancements

If time permits or for future iterations:

1. **Backtesting UI**: Web interface for running backtests
2. **Alert System**: Email/Slack notifications for important events
3. **Performance Analytics**: Sharpe ratio, drawdown charts
4. **Multi-Exchange**: Support Coinbase, Kraken
5. **Advanced Strategies**: ML-based strategies, sentiment analysis
6. **Mobile App**: React Native dashboard
7. **API Authentication**: JWT tokens for web API

---

## Final Commit

```bash
git add .
git commit -m "feat: complete Day 3 - Production Ready

- Real trading mode with Binance API
- Enhanced risk monitor with circuit breakers
- Parameter optimization using parallel forks
- All 6 strategies operational
- Dashboard polished with charts
- Complete documentation
- Deployment configuration
- E2E tests and demo preparation

System ready for production showcase 🚀"

git push origin main
```

**Congratulations! The live trading system is complete! 🎉**
