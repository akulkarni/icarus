"""
Trading Data Models

Core data structures for trading operations.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Position:
    """Represents an open trading position"""
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    side: str  # 'long' or 'short'
    strategy_name: str
    entry_time: datetime
    unrealized_pnl: Decimal = Decimal('0')

    def update_price(self, new_price: Decimal):
        """Update current price and recalculate PnL"""
        self.current_price = new_price
        if self.side == 'long':
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - new_price) * self.quantity

    @property
    def value(self) -> Decimal:
        """Current market value of position"""
        return self.current_price * self.quantity

    @property
    def cost_basis(self) -> Decimal:
        """Original cost of position"""
        return self.entry_price * self.quantity


@dataclass
class Trade:
    """Represents a completed trade"""
    id: Optional[int]
    time: datetime
    strategy_name: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: Decimal
    price: Decimal
    fee: Decimal
    trade_mode: str  # 'paper' or 'live'

    @property
    def value(self) -> Decimal:
        """Total trade value (excluding fees)"""
        return self.quantity * self.price

    @property
    def total_cost(self) -> Decimal:
        """Total cost including fees"""
        return self.value + self.fee


@dataclass
class Portfolio:
    """Represents a portfolio state"""
    strategy_name: str
    cash: Decimal
    positions: dict  # symbol -> Position
    total_value: Decimal
    total_pnl: Decimal
    timestamp: datetime

    @property
    def equity(self) -> Decimal:
        """Total equity (cash + position values)"""
        position_value = sum(pos.value for pos in self.positions.values())
        return self.cash + position_value

    @property
    def exposure(self) -> Decimal:
        """Total market exposure (sum of position values)"""
        return sum(pos.value for pos in self.positions.values())

    @property
    def exposure_pct(self) -> float:
        """Exposure as percentage of equity"""
        if self.equity == 0:
            return 0.0
        return float(self.exposure / self.equity)
