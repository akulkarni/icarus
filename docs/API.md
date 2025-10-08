# API Documentation

## Overview

The Icarus Trading System provides a REST API and WebSocket interface for monitoring and interaction. The web dashboard (planned) will provide a browser-based interface to these APIs.

**Note**: The web API is planned for implementation in Agent 1 (FastAPI Dashboard). This document serves as the specification for that implementation.

## Base Information

- **Base URL**: `http://localhost:8000`
- **Protocol**: HTTP/1.1
- **Content-Type**: `application/json`
- **WebSocket**: `ws://localhost:8000/ws`

## Authentication

Currently, the API is designed for local use and does not require authentication. For production deployments, consider adding:
- API key authentication
- JWT tokens
- OAuth2
- IP whitelist

## REST API Endpoints

### Health & Status

#### GET `/`

Health check endpoint.

**Response**:
```json
{
  "status": "running",
  "service": "icarus-trading-system",
  "version": "1.0.0",
  "timestamp": "2025-10-08T15:30:00Z"
}
```

**Status Codes**:
- `200 OK`: System is running

---

#### GET `/api/health`

Detailed health status including agent and database status.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-08T15:30:00Z",
  "agents": {
    "market_data": "running",
    "momentum": "running",
    "macd": "running",
    "meta_strategy": "running",
    "execution": "running",
    "risk_monitor": "running",
    "fork_manager": "running"
  },
  "database": {
    "status": "connected",
    "pool_size": 15,
    "pool_available": 10
  },
  "event_bus": {
    "published_count": 12543,
    "total_subscribers": 25
  }
}
```

**Status Codes**:
- `200 OK`: System is healthy
- `503 Service Unavailable`: System has issues

---

### Portfolio

#### GET `/api/portfolio`

Get current portfolio state including positions and strategy allocations.

**Response**:
```json
{
  "timestamp": "2025-10-08T15:30:00Z",
  "total_value": 10500.00,
  "total_cash": 5000.00,
  "total_pnl": 500.00,
  "positions": [
    {
      "strategy_name": "momentum",
      "symbol": "BTCUSDT",
      "quantity": 0.5,
      "avg_entry_price": 50000.00,
      "current_price": 51000.00,
      "current_value": 25500.00,
      "unrealized_pnl": 500.00,
      "unrealized_pnl_pct": 2.0,
      "last_updated": "2025-10-08T15:29:00Z"
    },
    {
      "strategy_name": "macd",
      "symbol": "ETHUSDT",
      "quantity": 5.0,
      "avg_entry_price": 3000.00,
      "current_price": 3050.00,
      "current_value": 15250.00,
      "unrealized_pnl": 250.00,
      "unrealized_pnl_pct": 1.67,
      "last_updated": "2025-10-08T15:28:00Z"
    }
  ],
  "strategies": [
    {
      "strategy_name": "momentum",
      "portfolio_value": 10500.00,
      "cash_balance": 5000.00,
      "total_pnl": 500.00,
      "allocation_pct": 40.0,
      "allocated_capital": 4000.00,
      "is_active": true,
      "total_trades": 25,
      "win_rate": 0.60,
      "sharpe_ratio": 1.5
    },
    {
      "strategy_name": "macd",
      "portfolio_value": 10250.00,
      "cash_balance": 5000.00,
      "total_pnl": 250.00,
      "allocation_pct": 30.0,
      "allocated_capital": 3000.00,
      "is_active": true,
      "total_trades": 18,
      "win_rate": 0.55,
      "sharpe_ratio": 1.2
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Portfolio retrieved successfully
- `500 Internal Server Error`: Database error

---

### Trades

#### GET `/api/trades/recent`

Get recent trade history.

**Query Parameters**:
- `limit` (optional): Number of trades to return (default: 50, max: 500)
- `strategy` (optional): Filter by strategy name
- `symbol` (optional): Filter by symbol
- `since` (optional): ISO 8601 timestamp to get trades after

**Example Request**:
```
GET /api/trades/recent?limit=10&strategy=momentum
```

**Response**:
```json
{
  "trades": [
    {
      "time": "2025-10-08T15:25:00Z",
      "trade_id": "trade_abc123",
      "strategy_name": "momentum",
      "symbol": "BTCUSDT",
      "side": "buy",
      "quantity": 0.5,
      "price": 50000.00,
      "value": 25000.00,
      "fee": 25.00,
      "trade_mode": "paper"
    },
    {
      "time": "2025-10-08T15:20:00Z",
      "trade_id": "trade_def456",
      "strategy_name": "momentum",
      "symbol": "BTCUSDT",
      "side": "sell",
      "quantity": 0.25,
      "price": 51000.00,
      "value": 12750.00,
      "fee": 12.75,
      "trade_mode": "paper"
    }
  ],
  "count": 2,
  "limit": 10
}
```

**Status Codes**:
- `200 OK`: Trades retrieved successfully
- `400 Bad Request`: Invalid query parameters
- `500 Internal Server Error`: Database error

---

#### GET `/api/trades/summary`

Get trade summary statistics.

**Query Parameters**:
- `strategy` (optional): Filter by strategy name
- `period` (optional): Time period - "24h", "7d", "30d", "all" (default: "24h")

**Response**:
```json
{
  "period": "24h",
  "total_trades": 45,
  "buy_trades": 23,
  "sell_trades": 22,
  "total_volume": 1250000.00,
  "total_pnl": 500.00,
  "win_rate": 0.60,
  "avg_trade_size": 27777.78,
  "largest_win": 150.00,
  "largest_loss": -75.00,
  "by_strategy": [
    {
      "strategy_name": "momentum",
      "trades": 25,
      "pnl": 300.00,
      "win_rate": 0.64
    },
    {
      "strategy_name": "macd",
      "trades": 20,
      "pnl": 200.00,
      "win_rate": 0.55
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Summary retrieved successfully
- `400 Bad Request`: Invalid parameters

---

### Signals

#### GET `/api/signals/recent`

Get recent trading signals generated by strategies.

**Query Parameters**:
- `limit` (optional): Number of signals (default: 20, max: 200)
- `strategy` (optional): Filter by strategy name

**Response**:
```json
{
  "signals": [
    {
      "time": "2025-10-08T15:30:00Z",
      "strategy_name": "momentum",
      "symbol": "BTCUSDT",
      "signal_type": "buy",
      "confidence": 0.85,
      "price": 51000.00,
      "indicators": {
        "ma_short": 50800.00,
        "ma_long": 50200.00
      }
    },
    {
      "time": "2025-10-08T15:28:00Z",
      "strategy_name": "macd",
      "symbol": "ETHUSDT",
      "signal_type": "sell",
      "confidence": 0.75,
      "price": 3050.00,
      "indicators": {
        "macd": -5.2,
        "signal": -3.1,
        "histogram": -2.1
      }
    }
  ],
  "count": 2
}
```

**Status Codes**:
- `200 OK`: Signals retrieved successfully

---

### Forks

#### GET `/api/forks/active`

Get currently active database forks.

**Response**:
```json
{
  "forks": [
    {
      "fork_id": "fork_abc123xyz",
      "requesting_agent": "meta_strategy",
      "purpose": "scenario_analysis",
      "created_at": "2025-10-08T15:20:00Z",
      "ttl_seconds": 600,
      "expires_at": "2025-10-08T15:30:00Z",
      "status": "active",
      "connection_info": {
        "host": "fork-abc123.tiger.cloud",
        "port": 5432,
        "database": "tsdb"
      }
    },
    {
      "fork_id": "fork_def456xyz",
      "requesting_agent": "meta_strategy",
      "purpose": "validation",
      "created_at": "2025-10-08T15:25:00Z",
      "ttl_seconds": 300,
      "expires_at": "2025-10-08T15:30:00Z",
      "status": "active"
    }
  ],
  "count": 2,
  "max_concurrent": 10
}
```

**Status Codes**:
- `200 OK`: Forks retrieved successfully

---

#### GET `/api/forks/history`

Get fork creation history and usage statistics.

**Query Parameters**:
- `limit` (optional): Number of records (default: 50)

**Response**:
```json
{
  "history": [
    {
      "fork_id": "fork_abc123xyz",
      "purpose": "validation",
      "created_at": "2025-10-08T14:00:00Z",
      "destroyed_at": "2025-10-08T14:10:00Z",
      "duration_seconds": 600,
      "status": "destroyed"
    }
  ],
  "statistics": {
    "total_created_24h": 45,
    "avg_duration_seconds": 450,
    "most_common_purpose": "scenario_analysis"
  }
}
```

**Status Codes**:
- `200 OK`: History retrieved successfully

---

### PR Narratives

#### GET `/api/pr/narratives`

Get PR agent generated narratives (activity feed).

**Query Parameters**:
- `limit` (optional): Number of narratives (default: 20, max: 100)
- `category` (optional): Filter by event category
- `min_importance` (optional): Minimum importance score (1-10)

**Response**:
```json
{
  "narratives": [
    {
      "time": "2025-10-08T15:30:00Z",
      "event_id": "evt_123",
      "narrative": "💰 momentum strategy bought 0.5000 BTCUSDT at $50,000.00 (confidence: 85%)",
      "event_category": "trade",
      "importance_score": 7
    },
    {
      "time": "2025-10-08T15:28:00Z",
      "event_id": "evt_124",
      "narrative": "🔄 Meta-strategy rebalanced: momentum 40% (+5%), macd 30% (-3%)",
      "event_category": "allocation",
      "importance_score": 6
    },
    {
      "time": "2025-10-08T15:25:00Z",
      "event_id": "evt_125",
      "narrative": "⚠️ Risk alert: Portfolio exposure at 75% (limit: 80%)",
      "event_category": "risk",
      "importance_score": 8
    },
    {
      "time": "2025-10-08T15:20:00Z",
      "event_id": "evt_126",
      "narrative": "🍴 Fork created for scenario analysis (TTL: 10 minutes)",
      "event_category": "fork",
      "importance_score": 4
    }
  ],
  "count": 4
}
```

**Status Codes**:
- `200 OK`: Narratives retrieved successfully

---

### Configuration

#### GET `/api/config`

Get current system configuration (sanitized - no secrets).

**Response**:
```json
{
  "trading": {
    "mode": "paper",
    "initial_capital": 10000,
    "position_size_pct": 20,
    "symbols": ["BTCUSDT", "ETHUSDT"]
  },
  "risk": {
    "max_position_size_pct": 20,
    "max_daily_loss_pct": 5,
    "max_exposure_pct": 80
  },
  "strategies": {
    "momentum": {
      "enabled": true,
      "symbol": "BTCUSDT"
    },
    "macd": {
      "enabled": true,
      "symbol": "BTCUSDT"
    }
  },
  "meta_strategy": {
    "evaluation_interval_minutes": 5,
    "initial_allocation": "equal"
  }
}
```

**Status Codes**:
- `200 OK`: Configuration retrieved

---

## WebSocket API

### Connection

Connect to WebSocket for real-time event streaming:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    console.log('Connected to Icarus WebSocket');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('WebSocket connection closed');
};
```

### Message Format

All WebSocket messages follow this format:

```json
{
  "type": "event_type",
  "data": { /* event-specific data */ },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

### Event Types

#### Market Tick Event

```json
{
  "type": "market_tick",
  "data": {
    "symbol": "BTCUSDT",
    "price": 51000.00,
    "volume": 123.45
  },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

#### Trading Signal Event

```json
{
  "type": "trading_signal",
  "data": {
    "strategy_name": "momentum",
    "symbol": "BTCUSDT",
    "signal_type": "buy",
    "confidence": 0.85,
    "price": 51000.00
  },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

#### Trade Executed Event

```json
{
  "type": "trade_executed",
  "data": {
    "trade_id": "trade_abc123",
    "strategy_name": "momentum",
    "symbol": "BTCUSDT",
    "side": "buy",
    "quantity": 0.5,
    "price": 51000.00,
    "value": 25500.00,
    "fee": 25.50,
    "trade_mode": "paper"
  },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

#### Allocation Event

```json
{
  "type": "allocation",
  "data": {
    "strategy_name": "momentum",
    "allocation_pct": 40.0,
    "allocated_capital": 4000.00,
    "is_active": true
  },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

#### Risk Alert Event

```json
{
  "type": "risk_alert",
  "data": {
    "alert_type": "exposure_warning",
    "message": "Portfolio exposure at 75% (limit: 80%)",
    "severity": "warning",
    "current_value": 75.0,
    "limit_value": 80.0
  },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

#### Fork Event

```json
{
  "type": "fork_created",
  "data": {
    "fork_id": "fork_abc123xyz",
    "requesting_agent": "meta_strategy",
    "purpose": "scenario_analysis",
    "ttl_seconds": 600
  },
  "timestamp": "2025-10-08T15:30:00Z"
}
```

### Subscription Filtering

Future enhancement: Allow clients to subscribe to specific event types.

```json
{
  "action": "subscribe",
  "events": ["trade_executed", "risk_alert"]
}
```

## Error Responses

All API endpoints return errors in a consistent format:

```json
{
  "error": "Brief error message",
  "detail": "Detailed error information",
  "code": "ERROR_CODE",
  "timestamp": "2025-10-08T15:30:00Z"
}
```

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Codes

- `INVALID_PARAMETER`: Invalid query parameter
- `DATABASE_ERROR`: Database operation failed
- `NOT_FOUND`: Resource not found
- `INTERNAL_ERROR`: Unexpected server error
- `RATE_LIMIT_EXCEEDED`: Too many requests

**Example Error Response**:
```json
{
  "error": "Invalid parameter",
  "detail": "limit must be between 1 and 500",
  "code": "INVALID_PARAMETER",
  "timestamp": "2025-10-08T15:30:00Z"
}
```

## Rate Limiting

Currently not implemented. For production:
- Recommended: 100 requests per minute per IP
- WebSocket: 1 connection per client
- Burst: Allow short bursts up to 200 requests

## CORS

For development, all origins are allowed. For production:
```python
# Restrict to specific origins
origins = [
    "https://dashboard.icarus.example.com",
    "https://icarus.example.com"
]
```

## Dashboard Integration

The dashboard (to be implemented) will:
1. Connect to WebSocket on load
2. Poll REST endpoints for initial data
3. Update UI in real-time from WebSocket events
4. Display portfolio, trades, forks, narratives
5. Provide interactive charts and visualizations

**Dashboard Features**:
- Real-time portfolio value and P&L
- Active positions table
- Recent trades feed
- Trading signals visualization
- Fork activity monitoring
- PR narratives timeline
- Strategy performance comparison
- Risk metrics dashboard

## Development Tools

### Testing with curl

```bash
# Health check
curl http://localhost:8000/api/health

# Get portfolio
curl http://localhost:8000/api/portfolio

# Get recent trades
curl "http://localhost:8000/api/trades/recent?limit=5"

# Get active forks
curl http://localhost:8000/api/forks/active
```

### Testing WebSocket

Using `wscat`:
```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws
```

Using Python:
```python
import asyncio
import websockets

async def test_websocket():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        while True:
            message = await ws.recv()
            print(f"Received: {message}")

asyncio.run(test_websocket())
```

## Future Enhancements

1. **Authentication**: JWT-based auth for production
2. **Rate Limiting**: Protect against abuse
3. **Pagination**: Cursor-based pagination for large datasets
4. **Filtering**: Advanced query filters
5. **Aggregations**: Pre-computed aggregates via TimescaleDB
6. **GraphQL**: GraphQL API for flexible queries
7. **Webhooks**: Outbound webhooks for events
8. **API Versioning**: Version API endpoints (/v1/, /v2/)
9. **Swagger/OpenAPI**: Auto-generated API documentation
10. **Metrics**: Prometheus metrics endpoint

## Implementation Checklist

- [ ] FastAPI application setup
- [ ] REST endpoint implementations
- [ ] WebSocket server
- [ ] Database query functions
- [ ] Error handling middleware
- [ ] CORS configuration
- [ ] Static file serving (dashboard)
- [ ] Health check endpoints
- [ ] WebSocket event broadcasting
- [ ] API documentation (Swagger)
- [ ] Unit tests for endpoints
- [ ] Integration tests

## References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- WebSocket Protocol: https://tools.ietf.org/html/rfc6455
- RESTful API Design: https://restfulapi.net/
