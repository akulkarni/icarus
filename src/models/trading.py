"""
Trading Data Models

Core data models for trading entities: positions, trades, portfolios.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


# ============================================================================
# Position Models
# ============================================================================

@dataclass
class Position:
    """
    Trading position (open or closed)

    Represents a holding in a specific symbol by a strategy.
    """
    position_id: UUID
    strategy_name: str
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    opened_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

    @property
    def entry_value(self) -> Decimal:
        """Total entry value of position"""
        return self.quantity * self.entry_price

    @property
    def current_value(self) -> Decimal:
        """Current market value of position"""
        if self.current_price is None:
            return self.entry_value
        return self.quantity * self.current_price

    def update_price(self, new_price: Decimal) -> None:
        """Update current price and recalculate PnL"""
        self.current_price = new_price
        self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        self.updated_at = datetime.now()

    def calculate_return_pct(self) -> Decimal:
        """Calculate return percentage"""
        if self.entry_price == 0:
            return Decimal('0')
        if self.current_price is None:
            return Decimal('0')
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'position_id': str(self.position_id),
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'quantity': float(self.quantity),
            'entry_price': float(self.entry_price),
            'current_price': float(self.current_price) if self.current_price else None,
            'unrealized_pnl': float(self.unrealized_pnl) if self.unrealized_pnl else None,
            'opened_at': self.opened_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class ClosedPosition:
    """
    Closed trading position with realized PnL

    Represents a position that has been fully closed.
    """
    position_id: UUID
    strategy_name: str
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal
    return_pct: Decimal
    opened_at: datetime
    closed_at: datetime
    hold_duration: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_position(cls, position: Position, exit_price: Decimal, closed_at: datetime) -> 'ClosedPosition':
        """Create ClosedPosition from an open Position"""
        pnl = (exit_price - position.entry_price) * position.quantity
        return_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
        hold_duration = str(closed_at - position.opened_at)

        return cls(
            position_id=position.position_id,
            strategy_name=position.strategy_name,
            symbol=position.symbol,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            return_pct=return_pct,
            opened_at=position.opened_at,
            closed_at=closed_at,
            hold_duration=hold_duration,
            metadata=position.metadata
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'position_id': str(self.position_id),
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'quantity': float(self.quantity),
            'entry_price': float(self.entry_price),
            'exit_price': float(self.exit_price),
            'pnl': float(self.pnl),
            'return_pct': float(self.return_pct),
            'opened_at': self.opened_at.isoformat(),
            'closed_at': self.closed_at.isoformat(),
            'hold_duration': self.hold_duration,
            'metadata': self.metadata
        }


# ============================================================================
# Trade Models
# ============================================================================

@dataclass
class Trade:
    """
    Individual trade execution

    Represents a single buy or sell transaction.
    """
    id: Optional[UUID]
    time: datetime
    strategy_name: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: Decimal
    price: Decimal
    fee: Decimal
    order_id: Optional[str] = None
    trade_mode: str = "paper"  # 'paper' or 'live'
    metadata: Optional[Dict[str, Any]] = None

    @property
    def value(self) -> Decimal:
        """Total trade value (excluding fee)"""
        return self.quantity * self.price

    @property
    def total_cost(self) -> Decimal:
        """Total cost including fee"""
        return self.value + self.fee

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': str(self.id) if self.id else None,
            'time': self.time.isoformat(),
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': float(self.quantity),
            'price': float(self.price),
            'value': float(self.value),
            'fee': float(self.fee),
            'total_cost': float(self.total_cost),
            'order_id': self.order_id,
            'trade_mode': self.trade_mode,
            'metadata': self.metadata
        }


# ============================================================================
# Portfolio Models
# ============================================================================

@dataclass
class Portfolio:
    """
    Portfolio state for a strategy

    Tracks cash and positions for a single trading strategy.
    """
    strategy_name: str
    initial_capital: Decimal
    cash: Decimal
    positions: Dict[str, Position] = field(default_factory=dict)  # symbol -> Position
    trades: list[Trade] = field(default_factory=list)
    closed_positions: list[ClosedPosition] = field(default_factory=list)

    @property
    def positions_value(self) -> Decimal:
        """Total value of all open positions"""
        return sum(pos.current_value for pos in self.positions.values())

    @property
    def total_value(self) -> Decimal:
        """Total portfolio value (cash + positions)"""
        return self.cash + self.positions_value

    @property
    def unrealized_pnl(self) -> Decimal:
        """Total unrealized PnL from open positions"""
        return sum(
            pos.unrealized_pnl for pos in self.positions.values()
            if pos.unrealized_pnl is not None
        )

    @property
    def realized_pnl(self) -> Decimal:
        """Total realized PnL from closed positions"""
        return sum(pos.pnl for pos in self.closed_positions)

    @property
    def total_pnl(self) -> Decimal:
        """Total PnL (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_return_pct(self) -> Decimal:
        """Total return percentage"""
        if self.initial_capital == 0:
            return Decimal('0')
        return ((self.total_value - self.initial_capital) / self.initial_capital) * 100

    @property
    def num_positions(self) -> int:
        """Number of open positions"""
        return len(self.positions)

    @property
    def exposure_pct(self) -> Decimal:
        """Portfolio exposure percentage"""
        if self.total_value == 0:
            return Decimal('0')
        return (self.positions_value / self.total_value) * 100

    def add_position(self, position: Position) -> None:
        """Add or update a position"""
        self.positions[position.symbol] = position

    def remove_position(self, symbol: str) -> Optional[Position]:
        """Remove and return a position"""
        return self.positions.pop(symbol, None)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol"""
        return self.positions.get(symbol)

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to history"""
        self.trades.append(trade)

    def close_position(self, symbol: str, exit_price: Decimal, closed_at: datetime) -> Optional[ClosedPosition]:
        """Close a position and record it"""
        position = self.remove_position(symbol)
        if position is None:
            return None

        closed_pos = ClosedPosition.from_position(position, exit_price, closed_at)
        self.closed_positions.append(closed_pos)
        return closed_pos

    def update_prices(self, prices: Dict[str, Decimal]) -> None:
        """Update current prices for all positions"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'strategy_name': self.strategy_name,
            'initial_capital': float(self.initial_capital),
            'cash': float(self.cash),
            'positions_value': float(self.positions_value),
            'total_value': float(self.total_value),
            'unrealized_pnl': float(self.unrealized_pnl),
            'realized_pnl': float(self.realized_pnl),
            'total_pnl': float(self.total_pnl),
            'total_return_pct': float(self.total_return_pct),
            'num_positions': self.num_positions,
            'exposure_pct': float(self.exposure_pct),
            'positions': {symbol: pos.to_dict() for symbol, pos in self.positions.items()},
            'num_trades': len(self.trades),
            'num_closed_positions': len(self.closed_positions)
        }


# ============================================================================
# Order Models
# ============================================================================

@dataclass
class Order:
    """
    Trading order (limit, market, stop)

    Represents an order that may or may not be filled yet.
    """
    order_id: str
    strategy_name: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', 'stop'
    quantity: Decimal
    price: Optional[Decimal] = None  # For limit/stop orders
    status: str = "pending"  # pending, filled, cancelled, error
    filled_quantity: Decimal = Decimal('0')
    filled_price: Optional[Decimal] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    trade_mode: str = "paper"
    metadata: Optional[Dict[str, Any]] = None

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.filled_quantity >= self.quantity

    @property
    def is_partial_fill(self) -> bool:
        """Check if order is partially filled"""
        return Decimal('0') < self.filled_quantity < self.quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'order_id': self.order_id,
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'quantity': float(self.quantity),
            'price': float(self.price) if self.price else None,
            'status': self.status,
            'filled_quantity': float(self.filled_quantity),
            'filled_price': float(self.filled_price) if self.filled_price else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'trade_mode': self.trade_mode,
            'metadata': self.metadata
        }


# ============================================================================
# Performance Metrics
# ============================================================================

@dataclass
class StrategyMetrics:
    """
    Performance metrics for a trading strategy
    """
    strategy_name: str
    time_period: str  # e.g., '7d', '30d', 'all'
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    avg_win: Decimal = Decimal('0')
    avg_loss: Decimal = Decimal('0')
    profit_factor: Decimal = Decimal('0')
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown: Decimal = Decimal('0')
    current_drawdown: Decimal = Decimal('0')
    volatility: Optional[Decimal] = None
    total_fees: Decimal = Decimal('0')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'strategy_name': self.strategy_name,
            'time_period': self.time_period,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': float(self.win_rate),
            'total_pnl': float(self.total_pnl),
            'avg_win': float(self.avg_win),
            'avg_loss': float(self.avg_loss),
            'profit_factor': float(self.profit_factor),
            'sharpe_ratio': float(self.sharpe_ratio) if self.sharpe_ratio else None,
            'max_drawdown': float(self.max_drawdown),
            'current_drawdown': float(self.current_drawdown),
            'volatility': float(self.volatility) if self.volatility else None,
            'total_fees': float(self.total_fees)
        }
