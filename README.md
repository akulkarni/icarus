# Icarus Trading System

A multi-agent autonomous trading system built with Python, TimescaleDB, and Tiger Cloud.

## Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your Tiger Cloud credentials**
   - Get credentials from https://console.tigerdata.cloud/
   - Click your service → "Connection Info"
   - Copy host, port, database, user, password, and service_id

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database:**
   ```bash
   python scripts/init_db.py
   ```

5. **Run the system:**
   ```bash
   python -m src.main
   ```

## System Architecture

The Icarus Trading System consists of 7 autonomous agents:

1. **Market Data Agent** - Streams real-time market data
2. **Strategy Agents** - Generate trading signals (Momentum, MACD)
3. **Execution Agent** - Executes trades and manages positions
4. **Meta-Strategy Agent** - Dynamically allocates capital across strategies
5. **Risk Monitor Agent** - Enforces risk limits and emergency halts
6. **Fork Manager Agent** - Creates database forks for backtesting

## Configuration

Edit `config/app.yaml` to customize:
- Trading symbols
- Initial capital
- Risk limits
- Strategy parameters
- Logging settings

## Documentation

- [Implementation Plan](docs/plans/implementation-plan.md)
- [Architecture Overview](docs/plans/live-trading-system-design.md)
- [Blog Post](docs/blog-post.md)

## Development

### Running Tests
```bash
pytest tests/
```

### Health Check
```bash
python scripts/health_check.py
```

## License

[Add your license here]
