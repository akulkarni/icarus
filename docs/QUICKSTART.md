# Quick Start Guide

## Prerequisites
- Python 3.11+
- Tiger Cloud account with PostgreSQL database
- 10 minutes of time

## Step 1: Clone and Setup
```bash
git clone <repo>
cd worker-agent-3
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your Tiger Cloud credentials:
- Get these from https://console.tigerdata.cloud/
- Click your service → "Connection Info"
- Copy host, port, database, user, password, service_id

## Step 3: Initialize Database
```bash
python scripts/init_db.py
```

## Step 4: Run the System
```bash
python -m src.main
```

You should see:
```
2025-10-07 10:00:00 [INFO] Starting agent: market_data
2025-10-07 10:00:00 [INFO] Starting agent: momentum
...
```

## Step 5: Monitor Activity
Open another terminal:
```bash
# Watch trades
psql $DATABASE_URL -c "SELECT * FROM trades ORDER BY time DESC LIMIT 10"

# Watch signals
psql $DATABASE_URL -c "SELECT * FROM trading_signals ORDER BY time DESC LIMIT 10"

# Check allocations
psql $DATABASE_URL -c "SELECT * FROM current_allocations"
```

## Stopping
Press `Ctrl+C` in the main terminal. All agents will shut down gracefully.

## Troubleshooting

**Problem**: `FileNotFoundError: Config file not found`
**Solution**: Make sure you're in the project root directory with `config/app.yaml`

**Problem**: `connection refused` to database
**Solution**: Check your `.env` has correct `TIGER_HOST` and `TIGER_PASSWORD`

**Problem**: `table "market_data" does not exist`
**Solution**: Run `python scripts/init_db.py` first

## Next Steps
- Read the [Architecture Overview](../docs/plans/live-trading-system-design.md)
- Explore the [Implementation Plan](../docs/plans/implementation-plan.md)
- Check the [Blog Post](../docs/blog-post.md) to understand the vision
