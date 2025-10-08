# Agent 1: FastAPI Backend + Dashboard UI

**Branch**: `agent1-web-dashboard`
**Estimated Time**: 2-3 hours
**Dependencies**: None (can start immediately)

---

## Overview

You will build a FastAPI web backend with REST endpoints and WebSocket support, plus a real-time dashboard UI. This provides a web interface for monitoring the trading system.

**What you're building**:
- FastAPI application with CORS support
- REST endpoints for portfolio, trades, forks data
- WebSocket endpoint for real-time event streaming
- HTML/CSS/JavaScript dashboard with real-time updates
- Static file serving

**Key Principles**:
- **DRY**: Reuse database connection patterns from existing code
- **YAGNI**: Build only what's specified, no extra features
- **TDD**: Write tests before implementation
- **Frequent commits**: Commit after every 2-3 major steps

---

## Prerequisites - Understanding the Codebase

### 1. Event System
Read these files to understand how events work:
- `src/models/events.py` - All event types
- `src/core/event_bus.py` - Event bus implementation

**Key concepts**:
- Events are immutable dataclasses
- EventBus uses asyncio.Queue for pub/sub
- All events inherit from base `Event` class

### 2. Database Access
Read these files:
- `src/core/database.py` - Database manager
- `config/app.yaml` - Database configuration

**Key patterns**:
```python
# Get database connection
db = get_db_manager()
conn = await db.get_connection()
try:
    result = await conn.fetch("SELECT ...")
finally:
    await db.release_connection(conn)
```

### 3. Existing Agents
Read one example:
- `src/agents/market_data.py` - See how agents are structured

---

## Step 1: Setup & Dependencies (15 min)

### 1.1 Create branch
```bash
git checkout -b agent1-web-dashboard
```

### 1.2 Update requirements.txt
Add FastAPI dependencies:
```txt
# Add to end of requirements.txt
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
```

### 1.3 Install dependencies
```bash
pip install -r requirements.txt
```

### 1.4 Create directory structure
```bash
mkdir -p src/web
mkdir -p src/web/static
touch src/web/__init__.py
touch src/web/api.py
```

### 1.5 Test imports
Create a simple test to verify FastAPI is installed:

**File**: `tests/test_web/__init__.py`
```python
# Empty file
```

**File**: `tests/test_web/test_api_basic.py`
```python
"""Basic API import tests"""
import pytest


def test_fastapi_imports():
    """Verify FastAPI can be imported"""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import FastAPI: {e}")
```

Run test:
```bash
pytest tests/test_web/test_api_basic.py -v
```

### ✅ CHECKPOINT 1: Commit
```bash
git add requirements.txt src/web/ tests/test_web/
git commit -m "feat(web): add FastAPI dependencies and directory structure"
```

---

## Step 2: FastAPI Backend - Core Setup (30 min)

### 2.1 Write test for FastAPI app creation
**File**: `tests/test_web/test_api_basic.py` (add to existing file)

```python
from fastapi.testclient import TestClient


def test_app_creation():
    """Test FastAPI app can be created"""
    from src.web.api import app
    assert app is not None
    assert app.title == "Icarus Trading System Dashboard"


def test_root_endpoint():
    """Test root endpoint returns status"""
    from src.web.api import app
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
```

Run test (it will fail):
```bash
pytest tests/test_web/test_api_basic.py::test_app_creation -v
```

### 2.2 Implement FastAPI app
**File**: `src/web/api.py`

```python
"""
FastAPI Application for Trading System Dashboard

Provides:
- REST endpoints for system state
- WebSocket for real-time updates
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Icarus Trading System Dashboard")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections tracking
active_connections: List[WebSocket] = []


@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    logger.info("FastAPI app starting up")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("FastAPI app shutting down")


# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "status": "running",
        "service": "icarus-trading-system",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }
```

Run tests:
```bash
pytest tests/test_web/test_api_basic.py -v
```

### 2.3 Add database endpoints with tests

**File**: `tests/test_web/test_api_endpoints.py` (new file)

```python
"""Test API endpoints with mocked database"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_manager():
    """Mock database manager"""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_manager = MagicMock()
    mock_manager.get_connection = AsyncMock(return_value=mock_conn)
    mock_manager.release_connection = AsyncMock()

    return mock_manager


def test_portfolio_endpoint(mock_db_manager):
    """Test portfolio endpoint returns data"""
    # Mock database response
    mock_db_manager.get_connection.return_value.fetch = AsyncMock(
        return_value=[
            {
                'strategy_name': 'momentum',
                'portfolio_value': 10500.0,
                'cash_balance': 1000.0,
                'total_pnl': 500.0,
                'allocation_pct': 50.0,
                'is_active': True
            }
        ]
    )

    from src.web.api import app
    with patch('src.web.api.get_db_manager', return_value=mock_db_manager):
        client = TestClient(app)
        response = client.get("/api/portfolio")

        assert response.status_code == 200
        data = response.json()
        assert 'strategies' in data
        assert 'positions' in data
        assert 'timestamp' in data
```

**File**: `src/web/api.py` (add after health endpoint)

```python
from src.core.database import get_db_manager


@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio summary"""
    db = get_db_manager()
    conn = await db.get_connection()

    try:
        # Get all open positions
        positions = await conn.fetch("""
            SELECT strategy_name, symbol, quantity, avg_entry_price,
                   current_value, unrealized_pnl, last_updated
            FROM positions
            WHERE quantity > 0
            ORDER BY strategy_name, symbol
        """)

        # Get strategy performance (latest for each strategy)
        performance = await conn.fetch("""
            SELECT DISTINCT ON (strategy_name)
                   strategy_name, portfolio_value, cash_balance,
                   total_pnl, allocation_pct, is_active
            FROM strategy_performance
            ORDER BY strategy_name, time DESC
        """)

        return {
            "positions": [dict(p) for p in positions],
            "strategies": [dict(s) for s in performance],
            "timestamp": datetime.now().isoformat()
        }

    finally:
        await db.release_connection(conn)


@app.get("/api/trades/recent")
async def get_recent_trades(limit: int = 50):
    """Get recent trades"""
    db = get_db_manager()
    conn = await db.get_connection()

    try:
        trades = await conn.fetch("""
            SELECT time, strategy_name, symbol, side, quantity,
                   price, value, fee, trade_mode
            FROM trades
            ORDER BY time DESC
            LIMIT $1
        """, limit)

        return {"trades": [dict(t) for t in trades]}

    finally:
        await db.release_connection(conn)


@app.get("/api/forks/active")
async def get_active_forks():
    """Get active database forks"""
    db = get_db_manager()
    conn = await db.get_connection()

    try:
        forks = await conn.fetch("""
            SELECT fork_id, requesting_agent, purpose, created_at,
                   ttl_seconds, status
            FROM fork_tracking
            WHERE status = 'active'
            ORDER BY created_at DESC
        """)

        return {"forks": [dict(f) for f in forks]}

    finally:
        await db.release_connection(conn)
```

Run tests:
```bash
pytest tests/test_web/ -v
```

### ✅ CHECKPOINT 2: Commit & Request Review
```bash
git add src/web/api.py tests/test_web/
git commit -m "feat(web): add REST endpoints for portfolio, trades, and forks"
git push -u origin agent1-web-dashboard
```

**🛑 STOP AND REQUEST REVIEW**: Post in chat: "Agent 1 - Checkpoint 2 complete. REST endpoints implemented with tests. Ready for review."

---

## Step 3: WebSocket Implementation (30 min)

### 3.1 Write WebSocket tests
**File**: `tests/test_web/test_websocket.py` (new file)

```python
"""Test WebSocket functionality"""
import pytest
import asyncio
from fastapi.testclient import TestClient


def test_websocket_connection():
    """Test WebSocket connection can be established"""
    from src.web.api import app
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        # Connection should be accepted
        assert websocket is not None


def test_websocket_disconnect():
    """Test WebSocket handles disconnect gracefully"""
    from src.web.api import app
    client = TestClient(app)

    # Connect and disconnect
    with client.websocket_connect("/ws") as websocket:
        pass  # Auto-disconnects after context

    # Should not raise exception
    assert True
```

### 3.2 Implement WebSocket endpoint
**File**: `src/web/api.py` (add after REST endpoints)

```python
from src.core.event_bus import get_event_bus
from src.models.events import (
    MarketTickEvent,
    TradingSignalEvent,
    TradeExecutedEvent,
    AllocationEvent,
    ForkCreatedEvent,
    ForkCompletedEvent
)


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket connection for real-time updates.

    Subscribes to key event types and forwards to connected clients.
    """
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket connected. Total: {len(active_connections)}")

    try:
        # Subscribe to relevant events
        event_bus = get_event_bus()
        market_queue = event_bus.subscribe(MarketTickEvent)
        signal_queue = event_bus.subscribe(TradingSignalEvent)
        trade_queue = event_bus.subscribe(TradeExecutedEvent)
        allocation_queue = event_bus.subscribe(AllocationEvent)
        fork_created_queue = event_bus.subscribe(ForkCreatedEvent)
        fork_completed_queue = event_bus.subscribe(ForkCompletedEvent)

        # Forward events to WebSocket
        async def forward_events():
            while True:
                # Check all queues (non-blocking)
                queues = {
                    'market': market_queue,
                    'signal': signal_queue,
                    'trade': trade_queue,
                    'allocation': allocation_queue,
                    'fork_created': fork_created_queue,
                    'fork_completed': fork_completed_queue
                }

                for event_type, queue in queues.items():
                    if not queue.empty():
                        event = await queue.get()
                        await websocket.send_json({
                            'type': event_type,
                            'data': event.to_dict(),
                            'timestamp': datetime.now().isoformat()
                        })

                await asyncio.sleep(0.1)  # 100ms poll

        await forward_events()

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(active_connections)}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
```

Run tests:
```bash
pytest tests/test_web/test_websocket.py -v
```

### ✅ CHECKPOINT 3: Commit
```bash
git add src/web/api.py tests/test_web/test_websocket.py
git commit -m "feat(web): add WebSocket endpoint for real-time events"
```

---

## Step 4: Dashboard HTML/CSS/JS (45 min)

### 4.1 Create dashboard HTML
**File**: `src/web/static/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Icarus Trading System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }

        h1 {
            color: white;
            font-size: 2em;
        }

        .connection-status {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.9em;
            margin-top: 10px;
        }

        .connected {
            background: #10b981;
        }

        .disconnected {
            background: #ef4444;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: #1a1f3a;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }

        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #2a2f4a;
        }

        th {
            color: #a0aec0;
            font-weight: 600;
        }

        .positive {
            color: #10b981;
        }

        .negative {
            color: #ef4444;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .badge-buy {
            background: #10b981;
            color: white;
        }

        .badge-sell {
            background: #ef4444;
            color: white;
        }

        #recent-events {
            max-height: 300px;
            overflow-y: auto;
        }

        .event-item {
            padding: 10px;
            margin-bottom: 10px;
            background: #0f1729;
            border-left: 3px solid #667eea;
            border-radius: 5px;
        }

        .event-time {
            color: #6b7280;
            font-size: 0.85em;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Icarus Trading System Dashboard</h1>
        <div class="connection-status disconnected" id="connection-status">
            Disconnected
        </div>
    </div>

    <div class="grid">
        <!-- Portfolio Summary -->
        <div class="card">
            <h2>Portfolio Summary</h2>
            <table id="portfolio-table">
                <thead>
                    <tr>
                        <th>Strategy</th>
                        <th>Value</th>
                        <th>P&L</th>
                        <th>Alloc%</th>
                    </tr>
                </thead>
                <tbody id="portfolio-body">
                    <tr><td colspan="4">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Active Positions -->
        <div class="card">
            <h2>Active Positions</h2>
            <table id="positions-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Qty</th>
                        <th>Entry</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody id="positions-body">
                    <tr><td colspan="4">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Recent Trades -->
        <div class="card">
            <h2>Recent Trades</h2>
            <table id="trades-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Qty</th>
                        <th>Price</th>
                    </tr>
                </thead>
                <tbody id="trades-body">
                    <tr><td colspan="5">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Active Forks -->
        <div class="card">
            <h2>Active Database Forks</h2>
            <div id="forks-list">Loading...</div>
        </div>

        <!-- Real-time Events -->
        <div class="card" style="grid-column: 1 / -1;">
            <h2>Real-Time Events</h2>
            <div id="recent-events"></div>
        </div>
    </div>

    <script>
        let ws = null;
        const events = [];

        // Connect WebSocket
        function connectWebSocket() {
            ws = new WebSocket('ws://localhost:8000/ws');

            ws.onopen = () => {
                document.getElementById('connection-status').className = 'connection-status connected';
                document.getElementById('connection-status').textContent = 'Connected';
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'connection-status disconnected';
                document.getElementById('connection-status').textContent = 'Disconnected';
                setTimeout(connectWebSocket, 5000);  // Reconnect after 5s
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleEvent(data);
            };
        }

        // Handle real-time events
        function handleEvent(event) {
            events.unshift(event);
            if (events.length > 50) events.pop();

            const eventsDiv = document.getElementById('recent-events');
            eventsDiv.innerHTML = events.map(e => `
                <div class="event-item">
                    <div class="event-time">${new Date(e.timestamp).toLocaleTimeString()}</div>
                    <div><strong>${e.type}</strong>: ${JSON.stringify(e.data).substring(0, 100)}</div>
                </div>
            `).join('');

            // Refresh data on important events
            if (['trade', 'allocation'].includes(event.type)) {
                loadPortfolio();
                loadTrades();
            }
        }

        // Load portfolio data
        async function loadPortfolio() {
            try {
                const response = await fetch('/api/portfolio');
                const data = await response.json();

                const tbody = document.getElementById('portfolio-body');
                if (data.strategies.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4">No strategies active</td></tr>';
                } else {
                    tbody.innerHTML = data.strategies.map(s => `
                        <tr>
                            <td>${s.strategy_name}</td>
                            <td>$${s.portfolio_value.toFixed(2)}</td>
                            <td class="${s.total_pnl >= 0 ? 'positive' : 'negative'}">
                                ${s.total_pnl >= 0 ? '+' : ''}$${s.total_pnl.toFixed(2)}
                            </td>
                            <td>${s.allocation_pct.toFixed(1)}%</td>
                        </tr>
                    `).join('');
                }

                const positionsBody = document.getElementById('positions-body');
                if (data.positions.length === 0) {
                    positionsBody.innerHTML = '<tr><td colspan="4">No open positions</td></tr>';
                } else {
                    positionsBody.innerHTML = data.positions.map(p => `
                        <tr>
                            <td>${p.symbol}</td>
                            <td>${p.quantity}</td>
                            <td>$${p.avg_entry_price.toFixed(2)}</td>
                            <td class="${p.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                                ${p.unrealized_pnl >= 0 ? '+' : ''}$${p.unrealized_pnl.toFixed(2)}
                            </td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                console.error('Error loading portfolio:', error);
            }
        }

        // Load recent trades
        async function loadTrades() {
            try {
                const response = await fetch('/api/trades/recent?limit=10');
                const data = await response.json();

                const tbody = document.getElementById('trades-body');
                if (data.trades.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5">No trades yet</td></tr>';
                } else {
                    tbody.innerHTML = data.trades.map(t => `
                        <tr>
                            <td>${new Date(t.time).toLocaleTimeString()}</td>
                            <td>${t.symbol}</td>
                            <td><span class="badge badge-${t.side}">${t.side.toUpperCase()}</span></td>
                            <td>${t.quantity}</td>
                            <td>$${t.price.toFixed(2)}</td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                console.error('Error loading trades:', error);
            }
        }

        // Load active forks
        async function loadForks() {
            try {
                const response = await fetch('/api/forks/active');
                const data = await response.json();

                const div = document.getElementById('forks-list');
                if (data.forks.length === 0) {
                    div.innerHTML = '<p>No active forks</p>';
                } else {
                    div.innerHTML = data.forks.map(f => `
                        <div class="event-item">
                            <strong>${f.fork_id}</strong> - ${f.purpose}
                            <div class="event-time">Requested by ${f.requesting_agent}</div>
                        </div>
                    `).join('');
                }
            } catch (error) {
                console.error('Error loading forks:', error);
            }
        }

        // Initialize
        connectWebSocket();
        loadPortfolio();
        loadTrades();
        loadForks();

        // Refresh data periodically
        setInterval(loadPortfolio, 10000);  // Every 10s
        setInterval(loadTrades, 15000);     // Every 15s
        setInterval(loadForks, 30000);      // Every 30s
    </script>
</body>
</html>
```

### 4.2 Add static file serving
**File**: `src/web/api.py` (add after imports)

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Serve index.html at /dashboard
    from fastapi.responses import FileResponse

    @app.get("/dashboard")
    async def dashboard():
        """Serve dashboard HTML"""
        return FileResponse(str(static_dir / "index.html"))
```

### 4.3 Test dashboard manually
```bash
# In one terminal, start a simple test server
python -c "
from src.web.api import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# In another terminal or browser, open:
# http://localhost:8000/dashboard
```

### ✅ CHECKPOINT 4: Commit & Request Review
```bash
git add src/web/
git commit -m "feat(web): add complete dashboard UI with real-time updates"
git push
```

**🛑 STOP AND REQUEST REVIEW**: Post in chat: "Agent 1 - Checkpoint 4 complete. Dashboard UI implemented. Ready for review."

---

## Step 5: Integration with Main Application (30 min)

### 5.1 Write integration test
**File**: `tests/test_web/test_integration.py` (new file)

```python
"""Test integration with main application"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_web_server_starts():
    """Test that web server can start"""
    from src.web.api import app
    assert app is not None


@pytest.mark.asyncio
async def test_startup_shutdown_events():
    """Test app lifecycle events"""
    from src.web.api import startup, shutdown

    # Should not raise exceptions
    await startup()
    await shutdown()
```

### 5.2 Create web server runner module
**File**: `src/web/server.py` (new file)

```python
"""
Web Server Runner

Runs FastAPI application in a separate thread for integration with main app.
"""
import asyncio
import logging
import uvicorn
from threading import Thread

logger = logging.getLogger(__name__)


class WebServer:
    """Web server wrapper for FastAPI app"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start web server in background thread"""
        logger.info(f"Starting web server on {self.host}:{self.port}")

        def run_server():
            from src.web.api import app
            uvicorn.run(
                app,
                host=self.host,
                port=self.port,
                log_level="info"
            )

        self.thread = Thread(target=run_server, daemon=True)
        self.thread.start()
        logger.info("Web server started")

    def stop(self):
        """Stop web server"""
        logger.info("Stopping web server")
        # Uvicorn handles cleanup on daemon thread termination


def start_web_server(host: str = "0.0.0.0", port: int = 8000) -> WebServer:
    """
    Convenience function to start web server

    Args:
        host: Host to bind to
        port: Port to bind to

    Returns:
        WebServer instance
    """
    server = WebServer(host, port)
    server.start()
    return server
```

### 5.3 Update main.py to include web server
**File**: `src/main.py` (add near the top, after imports)

Read the existing `src/main.py` first to understand structure:
```bash
# Just read it, don't modify yet
cat src/main.py
```

Then add web server integration. Find the `main()` function and add:

```python
# Add this import at top of file
from src.web.server import start_web_server

# In main() function, after agents are created but before they run:
# Start web server
logger.info("Starting web dashboard")
web_server = start_web_server(host="0.0.0.0", port=8000)
logger.info("Web dashboard available at http://localhost:8000/dashboard")
```

### 5.4 Test full integration
**File**: `tests/test_web/test_integration.py` (add test)

```python
def test_web_server_module():
    """Test WebServer class"""
    from src.web.server import WebServer

    server = WebServer(host="127.0.0.1", port=8001)
    assert server.host == "127.0.0.1"
    assert server.port == 8001
```

Run all web tests:
```bash
pytest tests/test_web/ -v
```

### ✅ CHECKPOINT 5: Commit & Request Review
```bash
git add src/web/server.py src/main.py tests/test_web/test_integration.py
git commit -m "feat(web): integrate web server with main application"
git push
```

**🛑 STOP AND REQUEST REVIEW**: Post in chat: "Agent 1 - Checkpoint 5 complete. Web server integrated with main app. Ready for final review."

---

## Step 6: Documentation & Final Polish (15 min)

### 6.1 Create README for web module
**File**: `src/web/README.md`

```markdown
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
```

### 6.2 Add module docstrings
Verify all Python files have proper docstrings at the top. Update if needed.

### 6.3 Run full test suite
```bash
# Run all tests
pytest tests/test_web/ -v --cov=src.web

# Verify coverage > 80%
```

### 6.4 Create quick start guide
**File**: `docs/web-dashboard-quickstart.md`

```markdown
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
```

### ✅ FINAL CHECKPOINT: Commit & Request Review
```bash
git add src/web/README.md docs/web-dashboard-quickstart.md
git commit -m "docs(web): add comprehensive documentation for web dashboard"
git push
```

**🛑 STOP AND REQUEST FINAL REVIEW**: Post in chat: "Agent 1 - ALL WORK COMPLETE. Web dashboard fully implemented with tests and documentation. Ready for final review and merge."

---

## Testing Checklist

Before requesting final review, verify:

- [ ] All tests pass: `pytest tests/test_web/ -v`
- [ ] Test coverage > 80%: `pytest tests/test_web/ --cov=src.web`
- [ ] Dashboard loads at http://localhost:8000/dashboard
- [ ] WebSocket connects (check connection status indicator)
- [ ] REST endpoints return data (check browser network tab)
- [ ] No console errors in browser
- [ ] Code follows existing patterns in codebase
- [ ] All files have proper docstrings
- [ ] Git history is clean with meaningful commits

## Success Criteria

✅ FastAPI app created with CORS
✅ REST endpoints for portfolio, trades, forks
✅ WebSocket endpoint for real-time events
✅ Dashboard UI with real-time updates
✅ Static file serving configured
✅ Integration with main application
✅ Comprehensive test coverage
✅ Documentation complete

---

## Common Issues & Solutions

### Issue: Import errors for get_db_manager
**Solution**: Ensure `src/core/database.py` exports `get_db_manager` function

### Issue: WebSocket not receiving events
**Solution**: Check that EventBus singleton is properly initialized and agents are publishing events

### Issue: Static files not serving
**Solution**: Verify `src/web/static/` directory exists and contains `index.html`

### Issue: Port 8000 already in use
**Solution**: Change port in `src/web/server.py` or kill process using port

### Issue: Tests fail with database connection
**Solution**: Use mocked database in tests (see examples in test files)

---

## Notes

- Follow DRY: Reuse database connection patterns
- Follow YAGNI: Don't add features not in spec
- Follow TDD: Write tests first
- Commit frequently: After each major step
- Request review: At each checkpoint

**Good luck! Remember to ask for review at checkpoints.**
