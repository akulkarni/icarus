# 🚀 Icarus Trading System

A sophisticated multi-agent cryptocurrency trading system featuring dynamic portfolio management, real-time strategy execution, and database forking for parallel validation.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TimescaleDB](https://img.shields.io/badge/database-TimescaleDB-orange.svg)](https://www.timescale.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## ✨ Features

### Multi-Strategy Trading
- **6 Technical Strategies**: Momentum, MACD, Bollinger Bands, Mean Reversion, Breakout, Stochastic
- **Dynamic Allocation**: Meta-strategy automatically allocates capital based on performance
- **Automated Rebalancing**: Continuous portfolio optimization

### Database Forking
- **Parallel Validation**: Test strategies on database forks without affecting main database
- **Tiger Cloud Integration**: Seamless fork creation and management
- **Automatic Cleanup**: TTL-based fork lifecycle management

### Real-Time Dashboard
- **Live Updates**: WebSocket-powered real-time portfolio monitoring
- **Position Tracking**: Active positions with P&L
- **Trade History**: Complete trade execution history
- **Fork Activity**: Monitor fork creation and usage
- **PR Narratives**: Human-readable activity feed

### Paper & Live Trading
- **Safe Testing**: Comprehensive paper trading mode with slippage simulation
- **Binance Integration**: Direct API integration for live trading
- **Risk Controls**: Multiple layers of risk management
- **Trading Modes**: Easy switching between paper and live

### Agent-Based Architecture
- **Event-Driven**: Asynchronous pub/sub messaging via event bus
- **Loosely Coupled**: Independent agents communicating through events
- **Scalable**: Easy to add new strategies and agents
- **Observable**: Complete visibility into system behavior

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Tiger Cloud account ([Sign up](https://console.tigerdata.cloud/))
- Binance account (optional, for live trading)

### Installation

1. **Clone repository**:
```bash
git clone <repo-url>
cd agent-6
```

2. **Create virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your Tiger Cloud credentials
```

Get Tiger Cloud credentials:
- Visit https://console.tigerdata.cloud/
- Click your service → "Connection Info"
- Copy: host, port, database, user, password, service_id

5. **Deploy database schema**:
```bash
./sql/deploy_schema.sh
```

6. **Run the system**:
```bash
python src/main.py
```

7. **Access dashboard** (when implemented):
```
http://localhost:8000/dashboard
```

## 📖 Documentation

### User Documentation
- **[User Guide](docs/USER_GUIDE.md)** - Complete usage instructions
- **[Quick Start](docs/QUICKSTART.md)** - Get running in 10 minutes
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Technical Documentation
- **[Architecture](docs/ARCHITECTURE.md)** - System design and components
- **[API Documentation](docs/API.md)** - REST and WebSocket API reference
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions

### Development
- **[Contributing Guide](docs/CONTRIBUTING.md)** - How to contribute
- **[Implementation Plans](docs/plans/)** - Agent implementation roadmaps

### Safety
- **[Real Trading Safety](docs/REAL_TRADING_SAFETY.md)** - Safety checklist for live trading

## 🏗️ Architecture

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
                      └─────────────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │  Fork Manager   │
                      └─────────────────┘
                               │
                               ▼
                      ┌─────────────────────────┐
                      │   TimescaleDB + Forks   │
                      │    (Tiger Cloud)        │
                      └─────────────────────────┘
```

## 🤖 Agents

### Core Agents

1. **Market Data Agent** (`src/agents/market_data.py`)
   - Streams real-time prices from Binance WebSocket
   - Handles reconnection and error recovery
   - Publishes `MarketTickEvent` to event bus

2. **Strategy Agents** (`src/agents/strategies/`)
   - **Momentum**: Moving average crossover
   - **MACD**: MACD indicator signals
   - **Bollinger Bands**: Mean reversion (planned)
   - **Mean Reversion**: RSI-based signals (planned)
   - **Breakout**: Volume breakout detection (planned)
   - **Stochastic**: Stochastic oscillator (planned)

3. **Meta-Strategy Agent** (`src/agents/meta_strategy.py`)
   - Evaluates strategy performance
   - Dynamically allocates capital
   - Creates database forks for validation
   - Rebalances portfolio periodically

4. **Trade Execution Agent** (`src/agents/execution.py`)
   - Executes trades in paper or live mode
   - Handles order placement and tracking
   - Simulates slippage in paper mode
   - Integrates with Binance API for live trading

5. **Risk Monitor Agent** (`src/agents/risk_monitor.py`)
   - Enforces position size limits
   - Tracks daily loss limits
   - Monitors portfolio exposure
   - Emergency trading halt

6. **Fork Manager Agent** (`src/agents/fork_manager.py`)
   - Creates Tiger Cloud database forks
   - Manages fork lifecycle
   - Automatic cleanup based on TTL
   - Tracks fork usage and statistics

7. **PR Agent** (`src/agents/pr_agent.py`) - *Coming Soon*
   - Generates human-readable narratives
   - Monitors all system events
   - Importance scoring
   - Activity feed for dashboard

## 📁 Project Structure

```
agent-6/
├── config/                 # Configuration files
│   └── app.yaml           # Main configuration
├── docs/                  # Documentation
│   ├── USER_GUIDE.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DEPLOYMENT.md
│   ├── TROUBLESHOOTING.md
│   └── plans/            # Implementation plans
├── scripts/              # Utility scripts
│   ├── init_db.py       # Database initialization
│   ├── health_check.py  # System health check
│   ├── show_pnl.py      # P&L display
│   └── run_migration.py # Migration runner
├── sql/                  # Database schema & migrations
│   ├── schema.sql
│   ├── deploy_schema.sh
│   └── migrations/
├── src/
│   ├── agents/          # All trading agents
│   │   ├── base.py      # Base agent classes
│   │   ├── market_data.py
│   │   ├── execution.py
│   │   ├── meta_strategy.py
│   │   ├── risk_monitor.py
│   │   ├── fork_manager.py
│   │   └── strategies/  # Strategy implementations
│   │       ├── momentum.py
│   │       └── macd.py
│   ├── core/            # Core infrastructure
│   │   ├── event_bus.py # Pub/sub event system
│   │   ├── database.py  # Database layer
│   │   └── config.py    # Configuration management
│   ├── models/          # Data models
│   │   ├── events.py    # Event definitions
│   │   └── trading.py   # Trading models
│   └── main.py          # Entry point
├── tests/               # Test suite
├── .env.example         # Environment template
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚙️ Configuration

Edit `config/app.yaml` to customize:

```yaml
trading:
  mode: paper              # paper or live
  initial_capital: 10000
  position_size_pct: 20
  symbols:
    - BTCUSDT
    - ETHUSDT

risk:
  max_position_size_pct: 20
  max_daily_loss_pct: 5
  max_exposure_pct: 80

strategies:
  momentum:
    enabled: true
    symbol: BTCUSDT
    ma_short: 20
    ma_long: 50
```

See [User Guide](docs/USER_GUIDE.md) for complete configuration options.

## 🧪 Development

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_agents/test_meta_strategy.py
```

### Code Quality
```bash
# Linting
flake8 src/

# Formatting
black src/

# Type checking
mypy src/
```

### Health Check
```bash
python scripts/health_check.py
```

### View P&L
```bash
python scripts/show_pnl.py
```

## 🛠️ Technology Stack

- **Language**: Python 3.11+
- **Async Runtime**: asyncio
- **Database**: PostgreSQL 15+ with TimescaleDB
- **Cloud Platform**: Tiger Cloud (managed TimescaleDB)
- **Web Framework**: FastAPI (planned)
- **Exchange API**: Binance (python-binance)
- **Testing**: pytest, pytest-asyncio
- **Key Libraries**: asyncpg, pydantic, pyyaml

## 🔒 Safety & Risk Management

### Built-in Safety Features
- Paper trading mode by default
- Multiple risk limit layers
- Position size limits
- Daily loss limits
- Portfolio exposure limits
- Emergency halt capability
- Comprehensive logging

### Before Live Trading
1. ✅ Test thoroughly in paper mode (minimum 24 hours)
2. ✅ Validate all risk limits work correctly
3. ✅ Start with Binance testnet
4. ✅ Use very small position sizes (1-2%)
5. ✅ Monitor actively during first sessions
6. ✅ Review [Real Trading Safety Guide](docs/REAL_TRADING_SAFETY.md)

**⚠️ WARNING**: Trading involves risk. Only trade with money you can afford to lose.

## 📊 Monitoring

### Logs
```bash
# Application logs
tail -f logs/icarus.log

# JSON formatted
tail -f logs/icarus.log | jq .
```

### Database Queries
```sql
-- Recent trades
SELECT * FROM trades ORDER BY time DESC LIMIT 10;

-- Portfolio state
SELECT * FROM strategy_performance ORDER BY time DESC;

-- Active positions
SELECT * FROM positions WHERE quantity > 0;

-- Fork activity
SELECT * FROM fork_tracking WHERE status = 'active';
```

### Dashboard
Access the real-time dashboard at `http://localhost:8000/dashboard` (when implemented).

## 🚀 Deployment

For production deployment:
1. See [Deployment Guide](docs/DEPLOYMENT.md)
2. Use systemd for service management
3. Setup Nginx reverse proxy (optional)
4. Configure monitoring and alerting
5. Setup automated backups
6. Follow security best practices

## 🤝 Contributing

We welcome contributions! See [Contributing Guide](docs/CONTRIBUTING.md) for:
- Development setup
- Code standards
- Testing requirements
- Pull request process
- Adding new strategies

## 📝 License

[Add your license here - MIT recommended]

## 🙏 Acknowledgments

- **Timescale**: For TimescaleDB and Tiger Cloud
- **Binance**: For comprehensive trading API
- **Python Community**: For excellent async libraries

## 📞 Support

- **Documentation**: Check `docs/` directory
- **Issues**: Report bugs on GitHub Issues
- **Health Check**: Run `python scripts/health_check.py`
- **Troubleshooting**: See [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

## 🗺️ Roadmap

### Current Status (v1.0)
- ✅ Core agent architecture
- ✅ Market data streaming
- ✅ Strategy framework (Momentum, MACD)
- ✅ Meta-strategy with dynamic allocation
- ✅ Database forking integration
- ✅ Paper trading
- ✅ Risk management

### Upcoming (v1.1)
- 🔄 FastAPI web dashboard
- 🔄 4 additional strategies
- 🔄 PR agent for narratives
- 🔄 Live trading with Binance
- 🔄 Enhanced visualization

### Future (v2.0)
- Machine learning signal generation
- Multi-exchange support
- Advanced risk models (VaR, CVaR)
- Backtesting framework
- Portfolio optimization
- Mobile app

---

**Built with ❤️ using Python, TimescaleDB, and Tiger Cloud**

*Start your trading journey with Icarus - where autonomous agents meet financial markets.*
