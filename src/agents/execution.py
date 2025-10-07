"""
Trade Execution Agent

Executes trades in paper trading mode.
Manages positions and persists to database.
"""
import asyncio
import logging
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
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


class TradeExecutionAgent(BaseAgent):
    """
    Executes trades based on signals.

    Paper trading mode: simulates fills instantly at market price.
    """

    def __init__(self, event_bus, initial_capital: Decimal = Decimal('10000'), config: dict = None):
        super().__init__("execution", event_bus)
        self.initial_capital = initial_capital
        self.config = config or {}
        self.position_size_pct = Decimal(str(
            self.config.get('trading', {}).get('position_size_pct', 20)
        )) / Decimal('100')  # Convert 20 -> 0.2
        self.position_exit_pct = Decimal(str(
            self.config.get('trading', {}).get('position_exit_pct', 50)
        )) / Decimal('100')  # Convert 50 -> 0.5
        self.strategy_portfolios: Dict[str, dict] = {}  # strategy_name -> {cash, positions}
        self.current_allocations: Dict[str, float] = {}  # strategy_name -> allocation_pct
        self.current_prices: Dict[str, Decimal] = {}  # symbol -> last price

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
            self._track_prices(market_queue),
            self._performance_tracking_loop()
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
        # Calculate allocated capital for this strategy
        allocation_pct = self.current_allocations.get(signal.strategy_name, 0)
        allocated_capital = self.initial_capital * (Decimal(str(allocation_pct)) / Decimal('100'))

        # Use configured position size % of allocated capital
        cash_to_use = allocated_capital * self.position_size_pct

        # But don't exceed available cash
        cash_to_use = min(cash_to_use, portfolio['cash'])

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

        # Sell configurable % of position
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
        db = get_db_manager()

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

    async def _performance_tracking_loop(self):
        """Calculate and persist strategy performance metrics"""
        self.logger.info("Performance tracking started (15 minute interval)")

        while True:
            await asyncio.sleep(900)  # 15 minutes

            for strategy_name in self.strategy_portfolios.keys():
                try:
                    await self._calculate_and_persist_performance(strategy_name)
                except Exception as e:
                    self.logger.error(f"Error calculating performance for {strategy_name}: {e}")

    async def _calculate_and_persist_performance(self, strategy_name: str):
        """Calculate performance metrics for a strategy"""
        db = get_db_manager()
        conn = await db.get_connection()

        try:
            # Query trades for last 7 days
            trades = await conn.fetch("""
                SELECT side, quantity, price, fee, time
                FROM trades
                WHERE strategy_name = $1
                  AND time >= NOW() - INTERVAL '7 days'
                ORDER BY time ASC
            """, strategy_name)

            if not trades:
                return

            # Calculate metrics
            total_pnl = Decimal('0')
            winning_trades = 0
            losing_trades = 0
            trade_pnls = []

            # Group into round-trip trades (buy -> sell pairs)
            # Simple approach: calculate P&L from all sells
            position_cost = Decimal('0')
            position_qty = Decimal('0')

            for trade in trades:
                if trade['side'] == 'buy':
                    # Add to position
                    cost = Decimal(str(trade['quantity'])) * Decimal(str(trade['price'])) + Decimal(str(trade['fee']))
                    position_cost += cost
                    position_qty += Decimal(str(trade['quantity']))
                else:  # sell
                    if position_qty > 0:
                        # Calculate P&L for this sell
                        avg_cost = position_cost / position_qty if position_qty > 0 else Decimal('0')
                        sell_qty = Decimal(str(trade['quantity']))
                        sell_price = Decimal(str(trade['price']))
                        sell_fee = Decimal(str(trade['fee']))

                        pnl = (sell_price * sell_qty) - (avg_cost * sell_qty) - sell_fee
                        trade_pnls.append(pnl)
                        total_pnl += pnl

                        if pnl > 0:
                            winning_trades += 1
                        elif pnl < 0:
                            losing_trades += 1

                        # Reduce position
                        position_cost -= avg_cost * sell_qty
                        position_qty -= sell_qty

            total_trades = winning_trades + losing_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            # Calculate max drawdown
            max_drawdown = Decimal('0')
            current_drawdown = Decimal('0')
            peak = Decimal('0')
            cumulative_pnl = Decimal('0')

            for pnl in trade_pnls:
                cumulative_pnl += pnl
                if cumulative_pnl > peak:
                    peak = cumulative_pnl
                drawdown = peak - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            current_drawdown = peak - cumulative_pnl

            # Calculate max drawdown percentage (relative to initial capital)
            allocation_pct = self.current_allocations.get(strategy_name, 0)
            allocated_capital = self.initial_capital * (Decimal(str(allocation_pct)) / Decimal('100'))

            max_drawdown_pct = (max_drawdown / allocated_capital * 100) if allocated_capital > 0 else 0
            current_drawdown_pct = (current_drawdown / allocated_capital * 100) if allocated_capital > 0 else 0

            # Insert into strategy_performance
            await conn.execute("""
                INSERT INTO strategy_performance (
                    time, strategy_name, total_trades, winning_trades,
                    losing_trades, win_rate, total_pnl, max_drawdown, current_drawdown
                ) VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8)
            """, strategy_name, total_trades, winning_trades,
                losing_trades, win_rate, total_pnl, max_drawdown_pct, current_drawdown_pct)

            self.logger.info(
                f"Performance persisted for {strategy_name}: "
                f"trades={total_trades}, win_rate={win_rate:.1f}%, "
                f"pnl=${total_pnl:.2f}, max_dd={max_drawdown_pct:.2f}%"
            )

        finally:
            await db.release_connection(conn)
