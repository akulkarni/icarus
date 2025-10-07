"""
Risk Monitor Agent

Enforces risk limits and can halt trading if thresholds breached.
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.agents.base import BaseAgent
from src.models.events import (
    TradeExecutedEvent,
    RiskAlertEvent,
    EmergencyHaltEvent,
    MarketTickEvent
)
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class RiskMonitorAgent(BaseAgent):
    """
    Monitors risk and enforces limits.

    Phase 1 risk limits:
    - Max position size: 20% of allocated capital per trade
    - Max daily loss: 5% of total portfolio value
    - Max exposure: 80% of portfolio in positions
    - Per-strategy drawdown: 10% max drawdown before halt
    - Max leverage: 1.0 (no leverage in Phase 1)

    Publishes:
    - RiskAlertEvent: When approaching limits (warning)
    - EmergencyHaltEvent: When limits breached (halt trading)
    """

    def __init__(
        self,
        event_bus,
        config: Dict,
        initial_portfolio_value: Decimal = Decimal('10000')
    ):
        """
        Initialize risk monitor.

        Args:
            event_bus: Event bus for publishing alerts
            config: Risk configuration dictionary
            initial_portfolio_value: Initial portfolio value for calculations
        """
        super().__init__("risk_monitor", event_bus)
        self.config = config
        self.initial_portfolio_value = initial_portfolio_value

        # Risk limits from config with defaults
        self.max_position_size_pct = Decimal(
            str(config.get('max_position_size_pct', 20.0))
        )
        self.max_daily_loss_pct = Decimal(
            str(config.get('max_daily_loss_pct', 5.0))
        )
        self.max_exposure_pct = Decimal(
            str(config.get('max_exposure_pct', 80.0))
        )
        self.max_strategy_drawdown_pct = Decimal(
            str(config.get('max_strategy_drawdown_pct', 10.0))
        )
        self.max_leverage = Decimal(
            str(config.get('max_leverage', 1.0))
        )

        # State tracking
        self.daily_start_value: Optional[Decimal] = None
        self.daily_start_time: Optional[datetime] = None
        self.halt_active = False
        self.current_prices: Dict[str, Decimal] = {}
        self.strategy_peak_values: Dict[str, Decimal] = {}

        # Alert thresholds (warn at 80% of limit)
        self.warning_threshold = Decimal('0.8')

    async def start(self):
        """Start risk monitor"""
        logger.info("Starting Risk Monitor Agent")
        logger.info(f"Risk limits: max_daily_loss={self.max_daily_loss_pct}%, "
                   f"max_exposure={self.max_exposure_pct}%, "
                   f"max_strategy_drawdown={self.max_strategy_drawdown_pct}%")

        # Initialize daily start value
        await self._initialize_daily_tracking()

        # Subscribe to events
        trade_queue = self.event_bus.subscribe(TradeExecutedEvent)
        market_queue = self.event_bus.subscribe(MarketTickEvent)

        # Run monitoring loops
        await asyncio.gather(
            self._monitor_trades(trade_queue),
            self._track_prices(market_queue),
            self._periodic_checks()
        )

    async def _initialize_daily_tracking(self):
        """Initialize daily portfolio value tracking"""
        self.daily_start_time = datetime.now()
        self.daily_start_value = await self._get_current_portfolio_value()

        if self.daily_start_value is None:
            self.daily_start_value = self.initial_portfolio_value

        logger.info(f"Daily tracking initialized: start_value=${self.daily_start_value}")

    async def _monitor_trades(self, queue):
        """Monitor each trade execution for risk violations"""
        logger.info("Trade monitoring started")

        async for trade in self._consume_events(queue):
            try:
                await self._check_trade_risk(trade)
            except Exception as e:
                logger.error(f"Error checking trade risk: {e}", exc_info=True)

    async def _track_prices(self, queue):
        """Track current market prices"""
        async for tick in self._consume_events(queue):
            try:
                self.current_prices[tick.symbol] = tick.price
            except Exception as e:
                logger.error(f"Error tracking price: {e}", exc_info=True)

    async def _check_trade_risk(self, trade: TradeExecutedEvent):
        """
        Check if trade violates risk limits.

        Args:
            trade: Trade execution event
        """
        if self.halt_active:
            logger.warning(
                f"Trade executed during halt: {trade.strategy_name} "
                f"{trade.side} {trade.quantity} {trade.symbol}"
            )
            return

        # Check position size limit
        await self._check_position_size(trade)

        # Check exposure limit
        await self._check_exposure()

    async def _check_position_size(self, trade: TradeExecutedEvent):
        """
        Check if position size exceeds limit.

        Args:
            trade: Trade execution event
        """
        trade_value = trade.quantity * trade.price
        portfolio_value = await self._get_current_portfolio_value()

        if portfolio_value is None or portfolio_value == 0:
            return

        position_size_pct = (trade_value / portfolio_value) * 100

        # Check if exceeds limit
        if position_size_pct > self.max_position_size_pct:
            await self.publish(RiskAlertEvent(
                alert_type='position_size',
                severity='critical',
                message=f"Position size {position_size_pct:.2f}% exceeds limit "
                       f"{self.max_position_size_pct}% for {trade.strategy_name}",
                metadata={
                    'strategy_name': trade.strategy_name,
                    'symbol': trade.symbol,
                    'position_size_pct': float(position_size_pct),
                    'limit': float(self.max_position_size_pct)
                }
            ))
            logger.error(
                f"RISK VIOLATION: Position size {position_size_pct:.2f}% "
                f"exceeds {self.max_position_size_pct}%"
            )

        # Warning threshold
        elif position_size_pct > self.max_position_size_pct * self.warning_threshold:
            await self.publish(RiskAlertEvent(
                alert_type='position_size',
                severity='warning',
                message=f"Position size {position_size_pct:.2f}% approaching limit "
                       f"{self.max_position_size_pct}%",
                metadata={
                    'strategy_name': trade.strategy_name,
                    'symbol': trade.symbol,
                    'position_size_pct': float(position_size_pct)
                }
            ))

    async def _check_exposure(self):
        """Check if total exposure exceeds limit"""
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            # Get current positions
            positions = await conn.fetch("""
                SELECT symbol, SUM(quantity) as total_quantity
                FROM trades
                WHERE time >= NOW() - INTERVAL '24 hours'
                GROUP BY symbol
                HAVING SUM(quantity) > 0
            """)

            # Calculate total exposure
            total_exposure = Decimal('0')
            for pos in positions:
                symbol = pos['symbol']
                quantity = Decimal(str(pos['total_quantity']))
                price = self.current_prices.get(symbol)

                if price:
                    total_exposure += quantity * price

            portfolio_value = await self._get_current_portfolio_value()
            if portfolio_value is None or portfolio_value == 0:
                return

            exposure_pct = (total_exposure / portfolio_value) * 100

            # Check if exceeds limit
            if exposure_pct > self.max_exposure_pct:
                await self.publish(RiskAlertEvent(
                    alert_type='exposure',
                    severity='critical',
                    message=f"Total exposure {exposure_pct:.2f}% exceeds limit "
                           f"{self.max_exposure_pct}%",
                    metadata={
                        'exposure_pct': float(exposure_pct),
                        'limit': float(self.max_exposure_pct),
                        'total_exposure': float(total_exposure)
                    }
                ))
                logger.error(
                    f"RISK VIOLATION: Exposure {exposure_pct:.2f}% "
                    f"exceeds {self.max_exposure_pct}%"
                )

            # Warning threshold
            elif exposure_pct > self.max_exposure_pct * self.warning_threshold:
                await self.publish(RiskAlertEvent(
                    alert_type='exposure',
                    severity='warning',
                    message=f"Exposure {exposure_pct:.2f}% approaching limit "
                           f"{self.max_exposure_pct}%",
                    metadata={'exposure_pct': float(exposure_pct)}
                ))

        finally:
            await db.release_connection(conn)

    async def _periodic_checks(self):
        """Run periodic risk checks"""
        logger.info("Periodic risk checks started (5s interval)")

        while True:
            await asyncio.sleep(5)  # Check every 5 seconds

            try:
                # Reset daily tracking if new day
                await self._check_daily_reset()

                # Check daily loss limit
                await self._check_daily_loss()

                # Check per-strategy drawdowns
                await self._check_strategy_drawdowns()

            except Exception as e:
                logger.error(f"Error in periodic checks: {e}", exc_info=True)

    async def _check_daily_reset(self):
        """Reset daily tracking at start of new day"""
        now = datetime.now()

        if self.daily_start_time is None:
            await self._initialize_daily_tracking()
            return

        # Check if new day (UTC)
        if now.date() > self.daily_start_time.date():
            logger.info("New day detected, resetting daily tracking")
            await self._initialize_daily_tracking()

            # Reset halt if active
            if self.halt_active:
                self.halt_active = False
                logger.info("Emergency halt reset for new day")

    async def _check_daily_loss(self):
        """Check if daily loss limit breached"""
        if self.daily_start_value is None:
            return

        current_value = await self._get_current_portfolio_value()
        if current_value is None:
            return

        # Calculate daily PnL
        daily_pnl = current_value - self.daily_start_value
        daily_loss_pct = (daily_pnl / self.daily_start_value) * 100

        # Check if loss exceeds limit (negative PnL)
        if daily_loss_pct < -self.max_daily_loss_pct:
            if not self.halt_active:
                # Trigger emergency halt
                self.halt_active = True

                await self.publish(EmergencyHaltEvent(
                    reason=f"Daily loss {abs(daily_loss_pct):.2f}% exceeds limit "
                          f"{self.max_daily_loss_pct}%",
                    triggered_by='risk_monitor',
                    affected_strategies=None
                ))

                logger.critical(
                    f"EMERGENCY HALT: Daily loss {abs(daily_loss_pct):.2f}% "
                    f"exceeds {self.max_daily_loss_pct}% "
                    f"(start: ${self.daily_start_value}, current: ${current_value})"
                )

        # Warning threshold
        elif daily_loss_pct < -(self.max_daily_loss_pct * self.warning_threshold):
            await self.publish(RiskAlertEvent(
                alert_type='daily_loss',
                severity='warning',
                message=f"Daily loss {abs(daily_loss_pct):.2f}% approaching limit "
                       f"{self.max_daily_loss_pct}%",
                metadata={
                    'daily_loss_pct': float(daily_loss_pct),
                    'limit': float(self.max_daily_loss_pct)
                }
            ))

    async def _check_strategy_drawdowns(self):
        """Check per-strategy drawdown limits"""
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            # Get strategy performance
            strategies = await conn.fetch("""
                SELECT
                    strategy_name,
                    total_pnl,
                    max_drawdown
                FROM strategy_performance
                WHERE time >= NOW() - INTERVAL '24 hours'
                ORDER BY time DESC
            """)

            for strategy in strategies:
                strategy_name = strategy['strategy_name']
                max_drawdown = abs(float(strategy['max_drawdown'])) if strategy['max_drawdown'] else 0

                # Track peak value for drawdown calculation
                if strategy_name not in self.strategy_peak_values:
                    self.strategy_peak_values[strategy_name] = Decimal('0')

                # Check if drawdown exceeds limit
                if max_drawdown > float(self.max_strategy_drawdown_pct):
                    await self.publish(RiskAlertEvent(
                        alert_type='strategy_drawdown',
                        severity='critical',
                        message=f"Strategy {strategy_name} drawdown {max_drawdown:.2f}% "
                               f"exceeds limit {self.max_strategy_drawdown_pct}%",
                        metadata={
                            'strategy_name': strategy_name,
                            'drawdown_pct': max_drawdown,
                            'limit': float(self.max_strategy_drawdown_pct)
                        }
                    ))
                    logger.error(
                        f"RISK VIOLATION: Strategy {strategy_name} drawdown "
                        f"{max_drawdown:.2f}% exceeds {self.max_strategy_drawdown_pct}%"
                    )

        finally:
            await db.release_connection(conn)

    async def _get_current_portfolio_value(self) -> Optional[Decimal]:
        """
        Get current total portfolio value.

        Returns:
            Current portfolio value or None if unavailable
        """
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            # Get total cash and positions
            result = await conn.fetchrow("""
                SELECT
                    SUM(CASE WHEN side = 'sell' THEN value ELSE -value END) as net_cash
                FROM trades
                WHERE time >= NOW() - INTERVAL '30 days'
            """)

            net_cash = Decimal(str(result['net_cash'])) if result['net_cash'] else Decimal('0')
            cash_value = self.initial_portfolio_value + net_cash

            # Get position values
            positions = await conn.fetch("""
                SELECT symbol, SUM(quantity) as total_quantity
                FROM trades
                WHERE time >= NOW() - INTERVAL '24 hours'
                GROUP BY symbol
                HAVING SUM(quantity) > 0
            """)

            position_value = Decimal('0')
            for pos in positions:
                symbol = pos['symbol']
                quantity = Decimal(str(pos['total_quantity']))
                price = self.current_prices.get(symbol)

                if price:
                    position_value += quantity * price

            total_value = cash_value + position_value
            return total_value

        except Exception as e:
            logger.error(f"Error getting portfolio value: {e}", exc_info=True)
            return None
        finally:
            await db.release_connection(conn)

    def is_halt_active(self) -> bool:
        """Check if emergency halt is active"""
        return self.halt_active

    async def stop(self):
        """Stop risk monitor"""
        logger.info("Risk Monitor Agent stopped")
