"""
Trade Execution Agent

Executes trades in paper trading mode.
Manages positions and persists to database.
"""
import asyncio
import logging
import os
from decimal import Decimal
from datetime import datetime
from typing import Dict
from src.agents.base import BaseAgent
from src.models.events import (
    TradingSignalEvent,
    TradeExecutedEvent,
    AllocationEvent,
    MarketTickEvent
)
from src.models.trading import Position, Trade
from src.core.database import get_db_manager_sync

logger = logging.getLogger(__name__)


class TradeExecutionAgent(BaseAgent):
    """
    Executes trades based on signals.

    Paper trading mode: simulates fills instantly at market price.
    """

    def __init__(self, event_bus, initial_capital: Decimal = Decimal('10000'), config: dict = None):
        super().__init__("execution", event_bus)
        self.initial_capital = initial_capital
        self.strategy_portfolios: Dict[str, dict] = {}  # strategy_name -> {cash, positions}
        self.current_allocations: Dict[str, float] = {}  # strategy_name -> allocation_pct
        self.current_prices: Dict[str, Decimal] = {}  # symbol -> last price

        # Get config
        config = config or {}
        self.trade_mode = config.get('trading', {}).get('mode', 'paper')
        self.position_exit_pct = Decimal(str(
            config.get('trading', {}).get('position_exit_pct', 50)
        )) / Decimal('100')  # Convert 50 -> 0.5

        # Safety check for live trading
        if self.trade_mode == 'live':
            if os.getenv('ALLOW_LIVE_TRADING') != 'true':
                raise RuntimeError(
                    "Live trading mode requires ALLOW_LIVE_TRADING=true "
                    "environment variable. This is a safety check to prevent "
                    "accidental real trading."
                )
            logger.warning("=" * 80)
            logger.warning("LIVE TRADING MODE ENABLED - REAL MONEY AT RISK")
            logger.warning("=" * 80)
        else:
            logger.info("Paper trading mode enabled (simulated trades)")

    async def start(self):
        """Start execution agent"""
        self.logger.info(f"Starting trade execution with ${self.initial_capital} capital")

        # Subscribe to signals, allocations, and market data
        signal_queue = self.event_bus.subscribe(TradingSignalEvent)
        allocation_queue = self.event_bus.subscribe(AllocationEvent)
        market_queue = self.event_bus.subscribe(MarketTickEvent)

        # Run event loops concurrently
        await asyncio.gather(
            self._process_signals(signal_queue),
            self._process_allocations(allocation_queue),
            self._track_prices(market_queue)
        )

    async def _process_signals(self, queue):
        """Process trading signals"""
        async for signal in self._consume_events(queue):
            await self._execute_signal(signal)

    async def _process_allocations(self, queue):
        """Process allocation updates"""
        async for allocation in self._consume_events(queue):
            self.current_allocations = allocation.allocations
            self.logger.info(f"Updated allocations: {allocation.allocations}")

    async def _track_prices(self, queue):
        """Track current market prices"""
        async for tick in self._consume_events(queue):
            self.current_prices[tick.symbol] = tick.price

    async def _execute_signal(self, signal: TradingSignalEvent):
        """Execute a trading signal"""
        # Check if strategy has allocation
        allocation = self.current_allocations.get(signal.strategy_name, 0)
        if allocation == 0:
            self.logger.debug(f"Strategy {signal.strategy_name} has 0% allocation, skipping")
            return

        # Get or initialize strategy portfolio
        if signal.strategy_name not in self.strategy_portfolios:
            allocated_capital = self.initial_capital * (Decimal(str(allocation)) / Decimal('100'))
            self.strategy_portfolios[signal.strategy_name] = {
                'cash': allocated_capital,
                'positions': {}
            }
            self.logger.info(f"Initialized portfolio for {signal.strategy_name}: ${allocated_capital}")

        portfolio = self.strategy_portfolios[signal.strategy_name]

        # Execute based on signal
        if signal.side == 'buy':
            await self._execute_buy(signal, portfolio)
        elif signal.side == 'sell':
            await self._execute_sell(signal, portfolio)

    async def _execute_buy(self, signal: TradingSignalEvent, portfolio: dict):
        """Execute buy order (paper trading)"""
        # Use 20% of available cash (position sizing)
        cash_to_use = portfolio['cash'] * Decimal('0.2')

        if cash_to_use < Decimal('10'):  # Minimum order size
            self.logger.warning(f"Insufficient cash for {signal.symbol}: ${portfolio['cash']}")
            return

        # Get current price
        price = self.current_prices.get(signal.symbol)
        if not price:
            self.logger.warning(f"No price data for {signal.symbol}")
            return

        # Calculate quantity and fee
        quantity = cash_to_use / price
        fee = quantity * price * Decimal('0.001')  # 0.1% fee

        # Update portfolio
        portfolio['cash'] -= (quantity * price + fee)

        if signal.symbol not in portfolio['positions']:
            portfolio['positions'][signal.symbol] = Decimal('0')
        portfolio['positions'][signal.symbol] += quantity

        # Create trade record
        trade = Trade(
            id=None,
            time=datetime.now(),
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side='buy',
            quantity=quantity,
            price=price,
            fee=fee,
            trade_mode='paper'
        )

        # Persist trade
        await self._persist_trade(trade)

        # Publish fill event
        await self.publish(TradeExecutedEvent(
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side='buy',
            quantity=quantity,
            price=price,
            fee=fee,
            order_id=None
        ))

        self.logger.info(
            f"Executed BUY: {quantity:.6f} {signal.symbol} @ ${price} "
            f"(fee: ${fee:.2f}, remaining cash: ${portfolio['cash']:.2f})"
        )

    async def _execute_sell(self, signal: TradingSignalEvent, portfolio: dict):
        """Execute sell order (paper trading)"""
        # Check if we have a position
        if signal.symbol not in portfolio['positions']:
            self.logger.debug(f"No position in {signal.symbol} to sell")
            return

        position_quantity = portfolio['positions'][signal.symbol]
        if position_quantity <= 0:
            self.logger.debug(f"No position in {signal.symbol} to sell")
            return

        # Get current price
        price = self.current_prices.get(signal.symbol)
        if not price:
            self.logger.warning(f"No price data for {signal.symbol}")
            return

        # Sell configured % of position
        quantity = position_quantity * self.position_exit_pct
        fee = quantity * price * Decimal('0.001')  # 0.1% fee

        # Update portfolio
        cash_received = quantity * price - fee
        portfolio['cash'] += cash_received
        portfolio['positions'][signal.symbol] -= quantity

        # Remove position if fully closed
        if portfolio['positions'][signal.symbol] <= Decimal('0.0001'):
            del portfolio['positions'][signal.symbol]

        # Create trade record
        trade = Trade(
            id=None,
            time=datetime.now(),
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side='sell',
            quantity=quantity,
            price=price,
            fee=fee,
            trade_mode='paper'
        )

        # Persist trade
        await self._persist_trade(trade)

        # Publish fill event
        await self.publish(TradeExecutedEvent(
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side='sell',
            quantity=quantity,
            price=price,
            fee=fee,
            order_id=None
        ))

        self.logger.info(
            f"Executed SELL: {quantity:.6f} {signal.symbol} @ ${price} "
            f"(fee: ${fee:.2f}, cash received: ${cash_received:.2f}, new cash: ${portfolio['cash']:.2f})"
        )

    async def _persist_trade(self, trade: Trade):
        """Save trade to database"""
        db = get_db_manager_sync()

        try:
            conn = await db.get_connection()
            try:
                await conn.execute("""
                    INSERT INTO trades (
                        time, strategy_name, symbol, side, quantity,
                        price, value, fee, trade_mode
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    trade.time,
                    trade.strategy_name,
                    trade.symbol,
                    trade.side,
                    trade.quantity,
                    trade.price,
                    trade.value,
                    trade.fee,
                    trade.trade_mode
                )
            finally:
                await db.release_connection(conn)
        except Exception as e:
            self.logger.error(f"Failed to persist trade: {e}")

    def get_portfolio_summary(self, strategy_name: str) -> dict:
        """Get portfolio summary for a strategy"""
        if strategy_name not in self.strategy_portfolios:
            return {
                'cash': 0,
                'positions': {},
                'total_value': 0
            }

        portfolio = self.strategy_portfolios[strategy_name]

        # Calculate position values
        position_values = {}
        total_position_value = Decimal('0')

        for symbol, quantity in portfolio['positions'].items():
            price = self.current_prices.get(symbol, Decimal('0'))
            value = quantity * price
            position_values[symbol] = {
                'quantity': float(quantity),
                'price': float(price),
                'value': float(value)
            }
            total_position_value += value

        return {
            'cash': float(portfolio['cash']),
            'positions': position_values,
            'position_value': float(total_position_value),
            'total_value': float(portfolio['cash'] + total_position_value)
        }
