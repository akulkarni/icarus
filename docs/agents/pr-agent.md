# PR Agent (Public Relations / Narrative Generation)

## Purpose
Monitors all system events and generates human-readable narratives about interesting developments.

## Event Monitoring
- Trade executions
- Portfolio allocations
- Risk alerts
- Fork lifecycle
- Position closures
- Emergency halts

## Narrative Generation
Each narrative includes:
- Human-readable description
- Importance score (1-10)
- Event category
- Related strategy (if applicable)
- Metadata

## Importance Scoring
- 1-4: Low importance (not stored)
- 5-7: Medium importance
- 8-9: High importance
- 10: Critical (emergency events)

## Examples
```
💰 momentum strategy bought 0.5000 BTCUSDT at $50000.00 ($25000.00 value)
📊 Meta-strategy rebalanced allocations: momentum: 40.0%, macd: 60.0%
🔱 meta_strategy created database fork 'validation-test' for signal validation
✅ momentum closed BTCUSDT position: $125.50 profit (+2.5%)
🚨 EMERGENCY HALT: Daily loss limit exceeded
```

## Database Schema
```sql
CREATE TABLE pr_events (
    time TIMESTAMPTZ NOT NULL,
    narrative TEXT NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    importance_score INTEGER NOT NULL,
    related_strategy VARCHAR(50),
    metadata JSONB
);
```

## Usage
PR Agent runs automatically when system starts. Narratives appear in:
- Dashboard "Interesting Developments" section
- Logs (INFO level)
- Database pr_events table

## Configuration
No configuration needed. Automatically subscribes to all relevant events.
