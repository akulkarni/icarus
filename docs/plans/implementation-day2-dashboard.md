# Day 2: Web Dashboard + Intelligence

**Goal**: Add web UI with real-time updates, advanced meta-strategy, PR agent
**Estimated Time**: 10-12 hours
**Prerequisites**: Day 1 complete (all agents running, CLI output working)

---

## Overview

Day 2 adds a web interface for monitoring the system and enhances the intelligence of the meta-strategy agent. You'll also add the PR Agent for narrative generation and 2 more trading strategies.

**What you'll build:**
- FastAPI backend with REST + WebSocket
- Real-time web dashboard
- Advanced meta-strategy with market regime detection
- PR Agent for interesting development tracking
- Bollinger Bands and Mean Reversion strategies
- Slippage simulation

---

## Task 2.1: FastAPI Backend Setup (1 hour)

### Create Web API Structure

**File**: `src/web/__init__.py`
```python
# Empty for now
```

**File**: `src/web/api.py`

```python
"""
FastAPI application for web dashboard

Provides:
- REST endpoints for current state
- WebSocket for real-time updates
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import asyncio
import logging
from decimal import Decimal
from datetime import datetime

from src.core.database import get_db_manager
from src.core.event_bus import get_event_bus
from src.models.events import (
    MarketTickEvent, TradingSignalEvent, TradeExecutedEvent,
    AllocationEvent, ForkCreatedEvent, ForkCompletedEvent
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Live Trading System Dashboard")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections
active_connections: List[WebSocket] = []


@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    logger.info("FastAPI starting up")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("FastAPI shutting down")


# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {"status": "running", "service": "live-trading-system"}


@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio summary"""
    db = get_db_manager()
    conn = await db.get_connection()

    try:
        # Get all positions
        positions = await conn.fetch("""
            SELECT strategy_name, symbol, quantity, avg_entry_price,
                   current_value, unrealized_pnl, last_updated
            FROM positions
            WHERE quantity > 0
            ORDER BY strategy_name, symbol
        """)

        # Get strategy performance
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


@app.get("/api/pr/narratives")
async def get_narratives(limit: int = 20):
    """Get PR narratives"""
    db = get_db_manager()
    conn = await db.get_connection()

    try:
        narratives = await conn.fetch("""
            SELECT time, narrative, event_category, importance_score
            FROM pr_events
            ORDER BY time DESC
            LIMIT $1
        """, limit)

        return {"narratives": [dict(n) for n in narratives]}

    finally:
        await db.release_connection(conn)


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket connection for real-time updates.

    Subscribes to all event types and forwards to connected clients.
    """
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket connected. Total connections: {len(active_connections)}")

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
                            'data': event.__dict__,
                            'timestamp': datetime.now().isoformat()
                        })

                await asyncio.sleep(0.1)  # 100ms poll

        await forward_events()

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(active_connections)}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
```

**File**: `src/web/static/index.html` (create static directory)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Trading System</title>
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

        .badge-active {
            background: #3b82f6;
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
        <h1>🚀 Live Trading System Dashboard</h1>
        <div class="connection-status disconnected" id="connection-status">
            ⚫ Disconnected
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

        <!-- PR Narratives -->
        <div class="card" style="grid-column: 1 / -1;">
            <h2>Interesting Developments</h2>
            <div id="narratives-list">Loading...</div>
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
                document.getElementById('connection-status').textContent = '🟢 Connected';
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'connection-status disconnected';
                document.getElementById('connection-status').textContent = '⚫ Disconnected';
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
                    <div><strong>${e.type}</strong>: ${JSON.stringify(e.data)}</div>
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
            const response = await fetch('/api/portfolio');
            const data = await response.json();

            const tbody = document.getElementById('portfolio-body');
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

            const positionsBody = document.getElementById('positions-body');
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

        // Load recent trades
        async function loadTrades() {
            const response = await fetch('/api/trades/recent?limit=10');
            const data = await response.json();

            const tbody = document.getElementById('trades-body');
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

        // Load active forks
        async function loadForks() {
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
        }

        // Load PR narratives
        async function loadNarratives() {
            const response = await fetch('/api/pr/narratives');
            const data = await response.json();

            const div = document.getElementById('narratives-list');
            if (data.narratives.length === 0) {
                div.innerHTML = '<p>No narratives yet</p>';
            } else {
                div.innerHTML = data.narratives.map(n => `
                    <div class="event-item">
                        <strong>⭐ ${n.importance_score}/10</strong> - ${n.narrative}
                        <div class="event-time">${new Date(n.time).toLocaleString()}</div>
                    </div>
                `).join('');
            }
        }

        // Initialize
        connectWebSocket();
        loadPortfolio();
        loadTrades();
        loadForks();
        loadNarratives();

        // Refresh data periodically
        setInterval(loadPortfolio, 10000);  // Every 10s
        setInterval(loadTrades, 15000);     // Every 15s
        setInterval(loadForks, 30000);      // Every 30s
        setInterval(loadNarratives, 20000); // Every 20s
    </script>
</body>
</html>
```

**Update main.py** to run FastAPI alongside agents:

Add this to `src/main.py`:

```python
import uvicorn
from src.web.api import app as fastapi_app

# In main() function, add:
# Start FastAPI in separate thread
import threading
def run_web():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

web_thread = threading.Thread(target=run_web, daemon=True)
web_thread.start()
```

**Test**:
```bash
# Start system
python src/main.py

# Open browser
open http://localhost:8000
```

**Commit**: `git add src/web/ && git commit -m "feat(web): add FastAPI backend and dashboard UI"`

---

## Task 2.2: Advanced Meta-Strategy (2 hours)

Enhance meta-strategy with market regime detection. See `docs/plans/live-trading-system-design.md` section "Meta-Strategy Intelligence" for full spec.

**Key enhancements**:
1. Volatility calculation (rolling standard deviation)
2. Trend strength (ADX-like indicator)
3. Regime classification (trending_bull, ranging, high_volatility, etc.)
4. Fork-based scenario testing before reallocation

Refer to existing backtest files for indicator calculations.

**Commit**: `git add src/agents/meta_strategy.py && git commit -m "feat(meta-strategy): add regime detection and advanced allocation"`

---

## Task 2.3: PR Agent (1.5 hours)

Create PR Agent that monitors events and generates narratives.

**File**: `src/agents/pr_agent.py`

**Key features**:
- Subscribe to all event types
- Pattern detection (exceptional performance, regime changes, risk avoidance)
- Narrative generation with importance scoring
- Write to database pr_events table

**Commit**: `git add src/agents/pr_agent.py && git commit -m "feat(agents): add PR Agent for narrative generation"`

---

## Task 2.4: Additional Strategies (2 hours)

Add Bollinger Bands and Mean Reversion strategies.

**Reference existing files**:
- `backtest_bollinger.py` - has Bollinger Band calculation logic
- `backtest_meanreversion.py` - has mean reversion logic

**Create**:
- `src/agents/strategies/bollinger.py`
- `src/agents/strategies/mean_reversion.py`

**Commit**: `git add src/agents/strategies/ && git commit -m "feat(strategies): add Bollinger Bands and Mean Reversion"`

---

## Task 2.5: Slippage Simulation (30 min)

Update Trade Execution Agent to add 0.05-0.1% slippage on fills.

**File**: `src/agents/execution.py`

```python
# In execute_order method:
slippage_pct = Decimal('0.001')  # 0.1%
if side == 'buy':
    fill_price = market_price * (Decimal('1') + slippage_pct)
else:  # sell
    fill_price = market_price * (Decimal('1') - slippage_pct)
```

**Commit**: `git add src/agents/execution.py && git commit -m "feat(execution): add slippage simulation for realism"`

---

## Testing Day 2

Run full system with dashboard:

```bash
python src/main.py

# In browser: http://localhost:8000
# Verify:
# - Dashboard loads
# - Real-time events appear
# - WebSocket connected
# - Portfolio updates
# - Fork activity visible
# - PR narratives appear

# Run tests
pytest tests/ -v
```

**Success criteria**:
- [ ] Web dashboard accessible
- [ ] Real-time WebSocket updates working
- [ ] 4 strategies running (momentum, MACD, Bollinger, mean reversion)
- [ ] Meta-strategy uses regime detection
- [ ] PR agent generating narratives
- [ ] Slippage applied to trades
- [ ] All tests passing

**Commit**: `git add . && git commit -m "feat: complete Day 2 - Web Dashboard and Intelligence"`
