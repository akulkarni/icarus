# Web Dashboard Module

FastAPI-based web dashboard for the Icarus trading system.

## Components

### API (`api.py`)
- REST endpoints for system state
- WebSocket endpoint for real-time events
- CORS middleware for browser access

### Server (`server.py`)
- Web server wrapper
- Background thread runner
- Integration with main application

### Static Assets (`static/`)
- Dashboard HTML/CSS/JS
- Real-time event display
- Portfolio monitoring

## Endpoints

### REST API

- `GET /` - Health check
- `GET /api/health` - Detailed health status
- `GET /api/portfolio` - Portfolio summary with positions and strategies
- `GET /api/trades/recent?limit=N` - Recent trades
- `GET /api/forks/active` - Active database forks
- `GET /dashboard` - Dashboard UI

### WebSocket

- `WS /ws` - Real-time event stream

## Usage

```python
from src.web.server import start_web_server

# Start server
server = start_web_server(host="0.0.0.0", port=8000)

# Access dashboard at http://localhost:8000/dashboard
```

## Testing

```bash
# Run all web tests
pytest tests/test_web/ -v

# Run with coverage
pytest tests/test_web/ --cov=src.web
```

## Development

```bash
# Start development server
python -m uvicorn src.web.api:app --reload --port 8000

# Access at http://localhost:8000/dashboard
```
