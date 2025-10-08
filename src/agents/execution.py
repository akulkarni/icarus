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
    TradeErrorEvent,
    AllocationEvent,
    MarketTickEvent
)
from src.models.trading import Position, Trade
from src.core.database import get_db_manager_sync

# Binance imports
try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    BinanceClient = None
    BinanceAPIException = None

logger = logging.getLogger(__name__)


def calculate_slippage_price(market_price: Decimal, side: str, slippage_pct: Decimal) -> Decimal:
    """
    Calculate fill price with slippage

    Args:
        market_price: Current market price
        side: 'buy' or 'sell'
        slippage_pct: Slippage as decimal (0.001 = 0.1%)

    Returns:
        Price after slippage
    """
    if side == 'buy':
        # Buying costs more (unfavorable slippage)
        return market_price * (Decimal('1') + slippage_pct)
    else:  # sell
        # Selling gets less (unfavorable slippage)
        return market_price * (Decimal('1') - slippage_pct)


class TradeExecutionAgent(BaseAgent):
    """
    Executes trades based on signals.

    Paper trading mode: simulates fills instantly at market price.
    """

    def __init__(self, event_bus, initial_capital: Decimal = Decimal('10000'), config: dict = None):
        super().__init__("execution", event_bus)
        self.initial_capital = initial_capital
        self.config = config or {}

        # Position sizing configuration
        self.position_size_pct = Decimal(str(
            self.config.get('trading', {}).get('position_size_pct', 20)
        )) / Decimal('100')  # Convert 20 -> 0.2
        self.position_exit_pct = Decimal(str(
            self.config.get('trading', {}).get('position_exit_pct', 50)
        )) / Decimal('100')  # Convert 50 -> 0.5

        # Portfolio tracking
        self.strategy_portfolios: Dict[str, dict] = {}  # strategy_name -> {cash, positions}
        self.current_allocations: Dict[str, float] = {}  # strategy_name -> allocation_pct
        self.current_prices: Dict[str, Decimal] = {}  # symbol -> last price

        # Trading mode configuration
        self.trade_mode = self.config.get('trading', {}).get('mode', 'paper')

        # Initialize Binance client for real trading
        self.binance = None
        if self.trade_mode == 'real':
            if not BINANCE_AVAILABLE:
                raise RuntimeError("python-binance not installed. Install with: pip install python-binance")

            binance_config = self.config.get('binance', {})
            api_key = binance_config.get('api_key') or os.getenv('BINANCE_API_KEY')
            api_secret = binance_config.get('api_secret') or os.getenv('BINANCE_API_SECRET')
            testnet = binance_config.get('testnet', True)

            if not api_key or not api_secret:
                raise ValueError(
                    "Binance API credentials not configured. "
                    "Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables."
                )

            logger.warning("=" * 80)
            logger.warning("REAL TRADING MODE ENABLED - REAL MONEY AT RISK")
            logger.warning(f"Testnet mode: {testnet}")
            logger.warning("=" * 80)

            # Initialize Binance client
            self.binance = BinanceClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )

            # Verify connection
            try:
                account = self.binance.get_account()
                logger.info(f"✅ Binance connection verified. Account type: {account.get('accountType', 'UNKNOWN')}")
            except Exception as e:
                logger.error(f"❌ Failed to verify Binance connection: {e}")
                raise RuntimeError(f"Binance connection failed: {e}")
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

        # Route to paper or real execution
        if self.trade_mode == 'paper':
            # Execute based on signal
            if signal.side == 'buy':
                await self._execute_buy(signal, portfolio)
            elif signal.side == 'sell':
                await self._execute_sell(signal, portfolio)
        else:  # real mode
            # Calculate quantity for real trading
            if signal.side == 'buy':
                # Calculate how much to buy
                allocated_capital = self.initial_capital * (Decimal(str(allocation)) / Decimal('100'))
                cash_to_use = allocated_capital * self.position_size_pct
                cash_to_use = min(cash_to_use, portfolio['cash'])

                if cash_to_use < Decimal('10'):
                    self.logger.warning(f"Insufficient cash for {signal.symbol}: ${portfolio['cash']}")
                    return

                market_price = self.current_prices.get(signal.symbol)
                if not market_price:
                    self.logger.warning(f"No price data for {signal.symbol}")
                    return

                quantity = cash_to_use / market_price
                await self._execute_order_real(signal, quantity, portfolio)
            elif signal.side == 'sell':
                # Calculate how much to sell
                if signal.symbol not in portfolio['positions']:
                    self.logger.debug(f"No position in {signal.symbol} to sell")
                    return

                position_quantity = portfolio['positions'][signal.symbol]
                if position_quantity <= 0:
                    self.logger.debug(f"No position in {signal.symbol} to sell")
                    return

                quantity = position_quantity * self.position_exit_pct
                await self._execute_order_real(signal, quantity, portfolio)

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

        # Get current market price
        market_price = self.current_prices.get(signal.symbol)
        if not market_price:
            self.logger.warning(f"No price data for {signal.symbol}")
            return

        # Apply slippage for paper trading
        slippage_enabled = self.config.get('slippage', {}).get('enabled', False)
        slippage_pct = Decimal(str(self.config.get('slippage', {}).get('percentage', 0.1))) / Decimal('100')

        if slippage_enabled:
            fill_price = calculate_slippage_price(market_price, 'buy', slippage_pct)
        else:
            fill_price = market_price

        # Calculate quantity and fee
        quantity = cash_to_use / fill_price
        fee = quantity * fill_price * Decimal('0.001')  # 0.1% fee

        # Update portfolio
        portfolio['cash'] -= (quantity * fill_price + fee)

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
            price=fill_price,
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
            price=fill_price,
            fee=fee,
            order_id=None
        ))

        self.logger.info(
            f"Executed BUY: {quantity:.6f} {signal.symbol} @ ${fill_price} "
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

        # Get current market price
        market_price = self.current_prices.get(signal.symbol)
        if not market_price:
            self.logger.warning(f"No price data for {signal.symbol}")
            return

        # Apply slippage for paper trading
        slippage_enabled = self.config.get('slippage', {}).get('enabled', False)
        slippage_pct = Decimal(str(self.config.get('slippage', {}).get('percentage', 0.1))) / Decimal('100')

        if slippage_enabled:
            fill_price = calculate_slippage_price(market_price, 'sell', slippage_pct)
        else:
            fill_price = market_price

        # Sell configurable % of position
        quantity = position_quantity * self.position_exit_pct
        fee = quantity * fill_price * Decimal('0.001')  # 0.1% fee

        # Update portfolio
        cash_received = quantity * fill_price - fee
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
            price=fill_price,
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
            price=fill_price,
            fee=fee,
            order_id=None
        ))

        self.logger.info(
            f"Executed SELL: {quantity:.6f} {signal.symbol} @ ${fill_price} "
            f"(fee: ${fee:.2f}, cash received: ${cash_received:.2f}, new cash: ${portfolio['cash']:.2f})"
        )

    async def _execute_order_real(self, signal: TradingSignalEvent, quantity: Decimal, portfolio: dict):
        """
        Execute real order on Binance

        SAFETY: This uses real money. All checks must pass.
        """
        try:
            self.logger.warning(f"🚨 Executing REAL order: {signal.side} {quantity:.6f} {signal.symbol}")

            # Safety checks
            if not self.binance:
                raise ValueError("Binance client not initialized")

            # Format quantity according to Binance requirements
            # Binance requires specific precision for different pairs
            # For now, round to 6 decimals (adjust per symbol if needed)
            quantity_str = f"{float(quantity):.6f}".rstrip('0').rstrip('.')

            # Execute order on Binance
            if signal.side == 'buy':
                result = self.binance.order_market_buy(
                    symbol=signal.symbol,
                    quantity=quantity_str
                )
            else:  # sell
                result = self.binance.order_market_sell(
                    symbol=signal.symbol,
                    quantity=quantity_str
                )

            self.logger.info(f"Binance order result: {result}")

            # Parse fill information
            fills = result.get('fills', [])
            if not fills:
                raise ValueError("No fills returned from Binance")

            # Calculate weighted average fill price
            total_qty = Decimal('0')
            total_cost = Decimal('0')
            total_fee = Decimal('0')

            for fill in fills:
                fill_qty = Decimal(str(fill['qty']))
                fill_price = Decimal(str(fill['price']))
                fill_fee = Decimal(str(fill['commission']))

                total_qty += fill_qty
                total_cost += fill_qty * fill_price
                total_fee += fill_fee

            avg_fill_price = total_cost / total_qty if total_qty > 0 else Decimal('0')

            # Update portfolio
            if signal.side == 'buy':
                portfolio['cash'] -= (total_cost + total_fee)
                if signal.symbol not in portfolio['positions']:
                    portfolio['positions'][signal.symbol] = Decimal('0')
                portfolio['positions'][signal.symbol] += total_qty
            else:  # sell
                portfolio['cash'] += (total_cost - total_fee)
                portfolio['positions'][signal.symbol] -= total_qty
                if portfolio['positions'][signal.symbol] <= Decimal('0.0001'):
                    del portfolio['positions'][signal.symbol]

            # Create trade record
            trade = Trade(
                id=None,
                time=datetime.now(),
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                side=signal.side,
                quantity=total_qty,
                price=avg_fill_price,
                fee=total_fee,
                trade_mode='real'
            )

            # Persist trade
            await self._persist_trade(trade)

            # Publish trade executed event
            await self.publish(TradeExecutedEvent(
                trade_id=None,
                order_id=str(result['orderId']),
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                side=signal.side,
                quantity=total_qty,
                price=avg_fill_price,
                fee=total_fee,
                trade_mode='real'
            ))

            self.logger.warning(
                f"✅ REAL TRADE EXECUTED: {signal.side} {total_qty:.6f} {signal.symbol} @ ${avg_fill_price} "
                f"(fee: ${total_fee:.2f}, order_id: {result['orderId']})"
            )

        except BinanceAPIException as e:
            self.logger.error(f"❌ Binance API error: {e.message} (code: {e.code})")

            # Publish error event
            await self.publish(TradeErrorEvent(
                order_id=None,
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                error_type='binance_api_error',
                error_message=f"{e.code}: {e.message}"
            ))

        except Exception as e:
            self.logger.error(f"❌ Unexpected error executing real order: {e}", exc_info=True)

            await self.publish(TradeErrorEvent(
                order_id=None,
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                error_type='execution_error',
                error_message=str(e)
            ))

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
