"""
FastAPI Application for Trading System Dashboard

Provides:
- REST endpoints for system state
- WebSocket for real-time updates
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
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

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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


@app.get("/dashboard")
async def dashboard():
    """Serve dashboard HTML"""
    static_dir = Path(__file__).parent / "static"
    return FileResponse(str(static_dir / "index.html"))


from src.core.database import get_db_manager_sync


@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio summary"""
    db = get_db_manager_sync()
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
    db = get_db_manager_sync()
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
    db = get_db_manager_sync()
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


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

from src.core.event_bus import get_event_bus
from src.models.events import (
    MarketTickEvent,
    TradingSignalEvent,
    TradeExecutedEvent,
    AllocationEvent,
    ForkCreatedEvent,
    ForkCompletedEvent
)


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
        event_bus = await get_event_bus()
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
