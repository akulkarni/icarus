# Agent 4: PR Agent (Public Relations / Narrative Generation)

**Branch**: `agent4-pr-agent`
**Estimated Time**: 2 hours
**Dependencies**: None (can start immediately)

---

## Overview

Build PR Agent that monitors all system events and generates human-readable narratives about interesting developments. This provides storytelling for the dashboard and logs.

**What you're building**:
- Event-driven agent that subscribes to all event types
- Pattern detection (exceptional performance, regime changes, risk events)
- Narrative generation with importance scoring
- Database storage for narratives

**References**:
- `src/agents/base.py` - EventDrivenAgent pattern
- `src/models/events.py` - All event types
- Day 2 implementation plan for narrative examples

---

## Step 1: Database Schema & Setup (15 min)

### 1.1 Create branch
```bash
git checkout -b agent4-pr-agent
```

### 1.2 Create migration for PR events table
**File**: `sql/migrations/002_add_pr_events_table.sql`

```sql
-- PR Events Table for narrative generation
CREATE TABLE IF NOT EXISTS pr_events (
    time TIMESTAMPTZ NOT NULL,
    narrative TEXT NOT NULL,
    event_category VARCHAR(50) NOT NULL,  -- performance, risk, allocation, fork, trade
    importance_score INTEGER NOT NULL CHECK (importance_score BETWEEN 1 AND 10),
    related_strategy VARCHAR(50),
    metadata JSONB,
    PRIMARY KEY (time, event_category)
);

SELECT create_hypertable('pr_events', 'time', if_not_exists => TRUE);

CREATE INDEX idx_pr_events_category ON pr_events (event_category, time DESC);
CREATE INDEX idx_pr_events_importance ON pr_events (importance_score, time DESC);
CREATE INDEX idx_pr_events_strategy ON pr_events (related_strategy, time DESC) WHERE related_strategy IS NOT NULL;

COMMENT ON TABLE pr_events IS 'Public relations narratives generated from system events';
```

Apply migration:
```bash
./scripts/run_migration.py 002_add_pr_events_table
```

---

## Step 2: PR Agent Tests (30 min)

### 2.1 Create test file
**File**: `tests/test_agents/test_pr_agent.py`

```python
"""Tests for PR Agent"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.pr_agent import PRAgent
from src.models.events import (
    TradeExecutedEvent,
    AllocationEvent,
    RiskAlertEvent,
    ForkCreatedEvent
)


@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=asyncio.Queue())
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_db():
    conn = AsyncMock()
    conn.execute = AsyncMock()

    manager = MagicMock()
    manager.get_connection = AsyncMock(return_value=conn)
    manager.release_connection = AsyncMock()
    return manager


@pytest.fixture
def pr_agent(event_bus, mock_db):
    return PRAgent(event_bus=event_bus, db_manager=mock_db)


def test_pr_agent_init(pr_agent):
    """Test PR agent initialization"""
    assert pr_agent.name == 'pr_agent'
    assert pr_agent.db is not None


@pytest.mark.asyncio
async def test_pr_agent_handles_trade_event(pr_agent):
    """Test PR agent processes trade events"""
    event = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('0.5'),
        price=Decimal('50000'),
        fee=Decimal('25')
    )

    narrative = await pr_agent._generate_trade_narrative(event)

    assert narrative is not None
    assert 'momentum' in narrative.lower()
    assert 'buy' in narrative.lower() or 'bought' in narrative.lower()


@pytest.mark.asyncio
async def test_pr_agent_handles_allocation_event(pr_agent):
    """Test PR agent processes allocation events"""
    event = AllocationEvent(
        allocations={'momentum': 0.4, 'macd': 0.6},
        reason='Performance rebalance'
    )

    narrative = await pr_agent._generate_allocation_narrative(event)

    assert narrative is not None
    assert 'allocation' in narrative.lower() or 'rebalance' in narrative.lower()


@pytest.mark.asyncio
async def test_pr_agent_calculates_importance(pr_agent):
    """Test importance scoring"""
    # High importance: large trade
    high_event = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('10.0'),  # Large
        price=Decimal('50000'),
        fee=Decimal('2500')
    )

    high_score = pr_agent._calculate_importance(high_event, 'trade')
    assert high_score >= 7

    # Low importance: small trade
    low_event = TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('0.01'),  # Small
        price=Decimal('50000'),
        fee=Decimal('0.25')
    )

    low_score = pr_agent._calculate_importance(low_event, 'trade')
    assert low_score <= 5


@pytest.mark.asyncio
async def test_pr_agent_stores_narrative(pr_agent, mock_db):
    """Test narrative storage in database"""
    await pr_agent._store_narrative(
        narrative="Test narrative",
        category="test",
        importance=5,
        strategy=None,
        metadata=None
    )

    # Verify database insert was called
    pr_agent.db.get_connection.assert_called_once()
    conn = await pr_agent.db.get_connection()
    conn.execute.assert_called_once()
```

Run tests (will fail initially):
```bash
pytest tests/test_agents/test_pr_agent.py -v
```

---

## Step 3: PR Agent Implementation (45 min)

### 3.1 Implement PR Agent
**File**: `src/agents/pr_agent.py`

```python
"""
PR Agent - Public Relations / Narrative Generation

Monitors system events and generates human-readable narratives
about interesting developments for dashboard and logging.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime

from src.agents.base import EventDrivenAgent
from src.core.database import DatabaseManager
from src.models.events import (
    Event,
    TradeExecutedEvent,
    AllocationEvent,
    RiskAlertEvent,
    ForkCreatedEvent,
    ForkCompletedEvent,
    PositionClosedEvent,
    EmergencyHaltEvent,
)

logger = logging.getLogger(__name__)


class PRAgent(EventDrivenAgent):
    """
    PR Agent generates narratives from system events

    Monitors:
    - Trade execution
    - Portfolio allocation changes
    - Risk alerts
    - Fork lifecycle
    - Position closures
    - Emergency events
    """

    def __init__(self, event_bus, db_manager: DatabaseManager):
        super().__init__('pr_agent', event_bus)
        self.db = db_manager

        # Subscribe to relevant events
        self.add_subscription(TradeExecutedEvent)
        self.add_subscription(AllocationEvent)
        self.add_subscription(RiskAlertEvent)
        self.add_subscription(ForkCreatedEvent)
        self.add_subscription(ForkCompletedEvent)
        self.add_subscription(PositionClosedEvent)
        self.add_subscription(EmergencyHaltEvent)

    async def handle_event(self, event: Event) -> None:
        """Process event and generate narrative if interesting"""
        try:
            narrative = None
            category = None
            importance = 0
            strategy = None
            metadata = {}

            # Generate narrative based on event type
            if isinstance(event, TradeExecutedEvent):
                narrative = await self._generate_trade_narrative(event)
                category = 'trade'
                importance = self._calculate_importance(event, 'trade')
                strategy = event.strategy_name
                metadata = {'symbol': event.symbol, 'side': event.side}

            elif isinstance(event, AllocationEvent):
                narrative = await self._generate_allocation_narrative(event)
                category = 'allocation'
                importance = self._calculate_importance(event, 'allocation')
                metadata = {'allocations': event.allocations}

            elif isinstance(event, RiskAlertEvent):
                narrative = await self._generate_risk_narrative(event)
                category = 'risk'
                importance = self._calculate_importance(event, 'risk')
                strategy = event.strategy_name
                metadata = {'alert_type': event.alert_type, 'severity': event.severity}

            elif isinstance(event, ForkCreatedEvent):
                narrative = await self._generate_fork_narrative(event)
                category = 'fork'
                importance = self._calculate_importance(event, 'fork')
                metadata = {'fork_id': event.fork_id, 'purpose': event.purpose}

            elif isinstance(event, PositionClosedEvent):
                narrative = await self._generate_position_narrative(event)
                category = 'performance'
                importance = self._calculate_importance(event, 'position')
                strategy = event.strategy_name
                metadata = {
                    'symbol': event.symbol,
                    'pnl': float(event.pnl),
                    'return_pct': float(event.return_pct)
                }

            elif isinstance(event, EmergencyHaltEvent):
                narrative = f"🚨 EMERGENCY HALT: {event.reason}"
                category = 'risk'
                importance = 10  # Maximum importance
                metadata = {'reason': event.reason}

            # Store narrative if generated and important enough
            if narrative and importance >= 5:  # Only store important narratives
                await self._store_narrative(narrative, category, importance, strategy, metadata)
                self.logger.info(f"[PR] {narrative} (importance: {importance}/10)")

        except Exception as e:
            self.logger.error(f"Error handling event in PR agent: {e}", exc_info=True)

    async def _generate_trade_narrative(self, event: TradeExecutedEvent) -> Optional[str]:
        """Generate narrative for trade execution"""
        action = "bought" if event.side == 'buy' else "sold"
        value = float(event.quantity) * float(event.price)

        if value > 1000:
            return (f"💰 {event.strategy_name} strategy {action} {float(event.quantity):.4f} "
                   f"{event.symbol} at ${float(event.price):.2f} "
                   f"(${value:.2f} value)")
        return None

    async def _generate_allocation_narrative(self, event: AllocationEvent) -> Optional[str]:
        """Generate narrative for allocation change"""
        alloc_str = ", ".join([f"{name}: {pct:.1f}%" for name, pct in event.allocations.items()])
        return f"📊 Meta-strategy rebalanced allocations: {alloc_str}. Reason: {event.reason}"

    async def _generate_risk_narrative(self, event: RiskAlertEvent) -> Optional[str]:
        """Generate narrative for risk alert"""
        severity_emoji = {
            'warning': '⚠️',
            'critical': '🔴',
            'emergency': '🚨'
        }
        emoji = severity_emoji.get(event.severity, '⚠️')

        return f"{emoji} Risk alert ({event.severity}): {event.message}"

    async def _generate_fork_narrative(self, event: ForkCreatedEvent) -> Optional[str]:
        """Generate narrative for fork creation"""
        return f"🔱 {event.requesting_agent} created database fork '{event.fork_id}' for {event.purpose}"

    async def _generate_position_narrative(self, event: PositionClosedEvent) -> Optional[str]:
        """Generate narrative for position closure"""
        pnl = float(event.pnl)
        return_pct = float(event.return_pct)

        emoji = "✅" if pnl > 0 else "❌"
        action = "profit" if pnl > 0 else "loss"

        return (f"{emoji} {event.strategy_name} closed {event.symbol} position: "
               f"${abs(pnl):.2f} {action} ({return_pct:+.1f}%)")

    def _calculate_importance(self, event: Event, category: str) -> int:
        """
        Calculate importance score (1-10) for an event

        Higher scores = more interesting/important
        """
        importance = 5  # Default

        if category == 'trade':
            # Larger trades are more important
            value = float(event.quantity) * float(event.price)
            if value > 5000:
                importance = 9
            elif value > 2000:
                importance = 7
            elif value > 1000:
                importance = 6
            else:
                importance = 4

        elif category == 'allocation':
            # Allocation changes always important
            importance = 8

        elif category == 'risk':
            # Risk events by severity
            severity_scores = {'warning': 6, 'critical': 9, 'emergency': 10}
            importance = severity_scores.get(event.severity, 7)

        elif category == 'fork':
            # Fork creation moderately important
            importance = 6

        elif category == 'position':
            # Position closure by P&L
            pnl = abs(float(event.pnl))
            if pnl > 500:
                importance = 9
            elif pnl > 100:
                importance = 7
            elif pnl > 50:
                importance = 6
            else:
                importance = 5

        return min(10, max(1, importance))

    async def _store_narrative(
        self,
        narrative: str,
        category: str,
        importance: int,
        strategy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store narrative in database"""
        conn = await self.db.get_connection()

        try:
            await conn.execute("""
                INSERT INTO pr_events (time, narrative, event_category, importance_score,
                                       related_strategy, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, datetime.now(), narrative, category, importance, strategy, metadata)

        finally:
            await self.db.release_connection(conn)
```

Run tests:
```bash
pytest tests/test_agents/test_pr_agent.py -v
```

### ✅ CHECKPOINT 1: Commit & Review
```bash
git add src/agents/pr_agent.py tests/test_agents/test_pr_agent.py sql/migrations/002_add_pr_events_table.sql
git commit -m "feat(agents): implement PR Agent for narrative generation"
git push -u origin agent4-pr-agent
```

**🛑 REQUEST REVIEW**: "Agent 4 - Checkpoint 1. PR Agent implemented with tests."

---

## Step 4: Integration & Dashboard Update (20 min)

### 4.1 Register agent in main
**File**: `src/main.py` (add PR agent initialization)

Find where agents are created and add:

```python
from src.agents.pr_agent import PRAgent

# In main() where agents are initialized:
pr_agent = PRAgent(event_bus=event_bus, db_manager=db_manager)
agents.append(pr_agent)
```

### 4.2 Update web API for PR narratives
**File**: `src/web/api.py` (endpoint already exists, verify it works)

The endpoint should already be there from Agent 1:
```python
@app.get("/api/pr/narratives")
async def get_narratives(limit: int = 20):
    ...
```

Test it manually after starting system.

### 4.3 Integration test
**File**: `tests/test_integration/test_pr_agent_integration.py`

```python
"""Integration tests for PR Agent"""
import pytest
import asyncio
from decimal import Decimal
from src.agents.pr_agent import PRAgent
from src.core.event_bus import EventBus
from src.models.events import TradeExecutedEvent


@pytest.mark.asyncio
async def test_pr_agent_end_to_end(mock_db):
    """Test PR agent processes events end-to-end"""
    event_bus = EventBus()
    pr_agent = PRAgent(event_bus, mock_db)

    # Start agent
    agent_task = asyncio.create_task(pr_agent.run())

    # Give it time to start
    await asyncio.sleep(0.1)

    # Publish event
    await event_bus.publish(TradeExecutedEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('1.0'),
        price=Decimal('50000'),
        fee=Decimal('25')
    ))

    # Give it time to process
    await asyncio.sleep(0.1)

    # Stop agent
    agent_task.cancel()

    try:
        await agent_task
    except asyncio.CancelledError:
        pass

    # Verify database was called
    assert mock_db.get_connection.called
```

### ✅ CHECKPOINT 2: Commit & Review
```bash
git add src/main.py tests/test_integration/test_pr_agent_integration.py
git commit -m "feat(agents): integrate PR Agent into main application"
git push
```

**🛑 REQUEST REVIEW**: "Agent 4 - Checkpoint 2. PR Agent integrated."

---

## Step 5: Documentation (10 min)

### 5.1 Create PR Agent docs
**File**: `docs/agents/pr-agent.md`

```markdown
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
```

### ✅ FINAL: Commit & Review
```bash
git add docs/agents/pr-agent.md
git commit -m "docs(agents): add PR Agent documentation"
git push
```

**🛑 FINAL REVIEW**: "Agent 4 - Complete. PR Agent fully implemented with docs."

---

## Testing Checklist

- [ ] All tests pass
- [ ] Migration applied successfully
- [ ] Narratives stored in database
- [ ] Dashboard shows narratives
- [ ] Importance scoring works correctly
- [ ] All event types handled

## Success Criteria

✅ PR Agent implemented
✅ Event-driven architecture
✅ Narrative generation for all event types
✅ Importance scoring
✅ Database storage
✅ Integration with main app
✅ Tests pass
✅ Documentation complete
