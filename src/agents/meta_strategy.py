"""
Meta-Strategy Agent

Manages capital allocation across strategies.
Phase 1: Equal weighting initially, then performance-based.
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List

from src.agents.base import BaseAgent
from src.models.events import AllocationEvent, TradeExecutedEvent
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class MetaStrategyAgent(BaseAgent):
    """
    Portfolio manager that allocates capital to strategies.

    Implements adaptive capital allocation based on strategy performance:
    - Initial: Equal weighting across all strategies
    - Ongoing: Performance-based reallocation every N hours

    Publishes AllocationEvent whenever allocations change.
    """

    def __init__(
        self,
        event_bus,
        strategies: List[str],
        evaluation_interval_minutes: int = 5,
        min_allocation_pct: float = 5.0,
        max_allocation_pct: float = 50.0
    ):
        """
        Initialize meta-strategy agent.

        Args:
            event_bus: Event bus for publishing allocation events
            strategies: List of strategy names to manage
            evaluation_interval_minutes: Minutes between reallocation evaluations (changed for frequent fork demos)
            min_allocation_pct: Minimum allocation percentage per strategy
            max_allocation_pct: Maximum allocation percentage per strategy
        """
        super().__init__("meta_strategy", event_bus)
        self.strategies = strategies
        self.evaluation_interval_seconds = evaluation_interval_minutes * 60
        self.min_allocation_pct = Decimal(str(min_allocation_pct))
        self.max_allocation_pct = Decimal(str(max_allocation_pct))
        self.current_allocations: Dict[str, float] = {}
        self.first_allocation = True

    async def start(self):
        """Start meta-strategy agent"""
        logger.info(f"Starting Meta-Strategy Agent managing {len(self.strategies)} strategies")

        # Initial allocation
        await self._allocate_capital()

        # Periodic reallocation (now every 5 minutes instead of 6 hours for frequent fork demos)
        while True:
            await asyncio.sleep(self.evaluation_interval_seconds)
            await self._evaluate_and_reallocate()

    async def _allocate_capital(self):
        """Allocate capital to strategies"""
        if self.first_allocation:
            # Equal weighting initially
            allocation_pct = 100.0 / len(self.strategies)
            self.current_allocations = {
                strategy: allocation_pct for strategy in self.strategies
            }
            reason = "Initial equal weighting allocation"
            self.first_allocation = False
        else:
            # Performance-based allocation
            self.current_allocations = await self._calculate_performance_allocations()
            reason = "Performance-based reallocation"

        # Publish allocation event
        await self.publish(AllocationEvent(
            allocations=self.current_allocations,
            reason=reason
        ))

        logger.info(f"Capital allocated: {self.current_allocations}")

    async def _evaluate_and_reallocate(self):
        """Evaluate strategy performance and reallocate if needed"""
        logger.info("Evaluating strategy performance for reallocation")

        try:
            new_allocations = await self._calculate_performance_allocations()

            # Check if allocations have changed significantly (>5% change)
            needs_reallocation = False
            for strategy in self.strategies:
                old_alloc = self.current_allocations.get(strategy, 0)
                new_alloc = new_allocations.get(strategy, 0)
                if abs(old_alloc - new_alloc) > 5.0:
                    needs_reallocation = True
                    break

            if needs_reallocation:
                self.current_allocations = new_allocations
                await self.publish(AllocationEvent(
                    allocations=self.current_allocations,
                    reason="Performance-based reallocation"
                ))
                logger.info(f"Reallocated capital: {self.current_allocations}")
            else:
                logger.info("No significant allocation changes needed")

        except Exception as e:
            logger.error(f"Error during reallocation: {e}", exc_info=True)

    async def _calculate_performance_allocations(self) -> Dict[str, float]:
        """
        Calculate allocations based on recent performance.

        Uses a combination of metrics:
        - Total PnL (last 7 days)
        - Sharpe ratio
        - Win rate
        - Max drawdown

        Returns:
            Dictionary of strategy_name -> allocation_percentage
        """
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            # Get recent performance for each strategy
            performance_data = await conn.fetch("""
                SELECT
                    strategy_name,
                    total_pnl,
                    sharpe_ratio,
                    win_rate,
                    max_drawdown,
                    total_trades
                FROM strategy_performance
                WHERE time >= NOW() - INTERVAL '7 days'
                ORDER BY time DESC
                LIMIT 1
            """)

            if not performance_data or len(performance_data) == 0:
                # No performance data yet, fallback to equal weighting
                logger.warning("No performance data available, using equal weighting")
                allocation_pct = 100.0 / len(self.strategies)
                return {strategy: allocation_pct for strategy in self.strategies}

            # Calculate performance scores
            strategy_scores = {}
            for row in performance_data:
                strategy_name = row['strategy_name']

                # Skip if not in our managed strategies
                if strategy_name not in self.strategies:
                    continue

                # Calculate composite score (weighted average)
                pnl_score = max(0, float(row['total_pnl'])) if row['total_pnl'] else 0
                sharpe_score = max(0, float(row['sharpe_ratio'])) if row['sharpe_ratio'] else 0
                win_rate_score = float(row['win_rate']) if row['win_rate'] else 0
                drawdown_penalty = abs(float(row['max_drawdown'])) if row['max_drawdown'] else 0

                # Composite score (higher is better)
                score = (
                    pnl_score * 0.4 +           # 40% weight on PnL
                    sharpe_score * 30 * 0.3 +   # 30% weight on Sharpe (scaled)
                    win_rate_score * 100 * 0.2 +  # 20% weight on win rate
                    -drawdown_penalty * 0.1     # 10% penalty for drawdown
                )

                strategy_scores[strategy_name] = max(0, score)  # Ensure non-negative

            # Handle strategies with no data
            for strategy in self.strategies:
                if strategy not in strategy_scores:
                    strategy_scores[strategy] = 0.0

            # Calculate allocations from scores
            total_score = sum(strategy_scores.values())

            if total_score == 0:
                # All strategies have 0 score, fallback to equal weighting
                allocation_pct = 100.0 / len(self.strategies)
                return {strategy: allocation_pct for strategy in self.strategies}

            # Proportional allocation based on scores
            allocations = {}
            for strategy, score in strategy_scores.items():
                raw_allocation = (score / total_score) * 100.0

                # Apply min/max constraints
                allocation = max(
                    float(self.min_allocation_pct),
                    min(float(self.max_allocation_pct), raw_allocation)
                )
                allocations[strategy] = allocation

            # Normalize to ensure sum is 100%
            total_allocation = sum(allocations.values())
            if total_allocation > 0:
                allocations = {
                    strategy: (alloc / total_allocation) * 100.0
                    for strategy, alloc in allocations.items()
                }

            return allocations

        except Exception as e:
            logger.error(f"Error calculating performance allocations: {e}", exc_info=True)
            # Fallback to current allocations
            return self.current_allocations

        finally:
            await db.release_connection(conn)

    async def stop(self):
        """Stop meta-strategy agent"""
        logger.info("Meta-Strategy Agent stopped")
