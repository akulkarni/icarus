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
                metadata = {'fork_id': event.fork_id, 'purpose': event.purpose if hasattr(event, 'purpose') else 'unknown'}

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
        purpose = getattr(event, 'purpose', 'unknown purpose')
        return f"🔱 {event.requesting_agent} created database fork '{event.fork_id}' for {purpose}"

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
