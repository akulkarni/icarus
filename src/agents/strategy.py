"""
Base Strategy Agent

All trading strategies inherit from this class.
Provides common functionality for signal generation.
"""
import logging
from abc import abstractmethod
from decimal import Decimal
import pandas as pd
from src.agents.base import BaseAgent
from src.models.events import MarketTickEvent, TradingSignalEvent

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    Base class for all trading strategies.

    Subclasses implement analyze() method to generate signals.
    """

    def __init__(self, name: str, event_bus, symbol: str, params: dict):
        super().__init__(name, event_bus)
        self.symbol = symbol
        self.params = params
        self.price_history = []  # Store recent prices
        self.max_history = params.get('max_history', 200)

    async def start(self):
        """Start strategy event loop"""
        self.logger.info(f"Starting strategy {self.name} for {self.symbol}")

        # Subscribe to market data
        queue = self.event_bus.subscribe(MarketTickEvent)

        async for event in self._consume_events(queue):
            if event.symbol == self.symbol:
                await self._handle_tick(event)

    async def _handle_tick(self, tick: MarketTickEvent):
        """Process price update"""
        # Add to history
        self.price_history.append({
            'time': tick.timestamp,
            'price': float(tick.price),
            'volume': float(tick.volume)
        })

        # Keep only recent history
        if len(self.price_history) > self.max_history:
            self.price_history.pop(0)

        # Need minimum history before analyzing
        warmup_period = self.params.get('warmup_period', 50)
        if len(self.price_history) < warmup_period:
            self.logger.debug(f"Warming up: {len(self.price_history)}/{warmup_period}")
            return

        # Run strategy analysis
        try:
            signal = await self.analyze()

            if signal:
                self.logger.info(f"Signal generated: {signal.side} {signal.symbol} (confidence: {signal.confidence})")
                await self.publish(signal)
        except Exception as e:
            self.logger.error(f"Error analyzing prices: {e}")

    @abstractmethod
    async def analyze(self) -> TradingSignalEvent | None:
        """
        Analyze price data and generate signal.

        Returns:
            TradingSignalEvent if signal generated, None otherwise
        """
        pass

    def get_prices_df(self) -> pd.DataFrame:
        """Get price history as DataFrame"""
        return pd.DataFrame(self.price_history)
