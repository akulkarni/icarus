# Web Dashboard Quick Start

## Installation

Dependencies are already in `requirements.txt`:
- fastapi
- uvicorn
- python-multipart

## Starting the Dashboard

### With Main Application

The dashboard starts automatically when you run the main application:

```bash
python src/main.py
```

Then open: http://localhost:8000/dashboard

### Standalone (for development)

```bash
python -m uvicorn src.web.api:app --reload --port 8000
```

## Features

### Real-Time Updates
- WebSocket connection shows live events
- Market ticks, signals, trades, allocations
- Fork creation and completion
- Automatic reconnection on disconnect

### Portfolio View
- Current portfolio value per strategy
- P&L tracking
- Allocation percentages
- Active/inactive status

### Positions
- Open positions by strategy
- Entry prices
- Unrealized P&L
- Current values

### Trades History
- Recent trade executions
- Buy/sell indicators
- Timestamps and prices
- Fees and modes (paper/live)

### Database Forks
- Active forks display
- Purpose and requesting agent
- TTL tracking

## Troubleshooting

### Dashboard won't load
1. Check web server started: Look for "Starting web dashboard" in logs
2. Verify port 8000 is not in use: `lsof -i :8000`
3. Check firewall settings

### WebSocket not connecting
1. Ensure EventBus is initialized
2. Check browser console for errors
3. Verify CORS settings in api.py

### No data showing
1. Verify database connection in config/app.yaml
2. Check that agents are publishing events
3. Ensure schema is deployed (see sql/deploy_schema.sh)
