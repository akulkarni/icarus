"""
MACD Strategy

Moving Average Convergence Divergence (MACD) indicator strategy.
- Buy when MACD line crosses above signal line
- Sell when MACD line crosses below signal line
"""
import pandas as pd
from decimal import Decimal
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


class MACDStrategy(StrategyAgent):
    """MACD indicator strategy"""

    def __init__(self, event_bus, symbol: str = 'BTCUSDT',
                 fast_period: int = 12, slow_period: int = 26,
                 signal_period: int = 9, warmup_period: int = 50):
        params = {
            'fast_period': fast_period,      # Use parameter instead of hardcoded 12
            'slow_period': slow_period,      # Use parameter instead of hardcoded 26
            'signal_period': signal_period,  # Use parameter instead of hardcoded 9
            'warmup_period': warmup_period,  # Use parameter instead of hardcoded 50
            'max_history': 200
        }
        super().__init__('macd', event_bus, symbol, params)
        self.previous_signal = None

    async def analyze(self) -> TradingSignalEvent | None:
        """Generate signal based on MACD crossover"""
        df = self.get_prices_df()

        if len(df) < self.params['slow_period'] + self.params['signal_period']:
            return None

        # Calculate MACD
        fast_period = self.params['fast_period']
        slow_period = self.params['slow_period']
        signal_period = self.params['signal_period']

        # Calculate EMAs
        df['ema_fast'] = df['price'].ewm(span=fast_period, adjust=False).mean()
        df['ema_slow'] = df['price'].ewm(span=slow_period, adjust=False).mean()

        # MACD line = Fast EMA - Slow EMA
        df['macd'] = df['ema_fast'] - df['ema_slow']

        # Signal line = EMA of MACD
        df['signal'] = df['macd'].ewm(span=signal_period, adjust=False).mean()

        # MACD histogram
        df['histogram'] = df['macd'] - df['signal']

        # Get current and previous values
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Check for NaN values
        if pd.isna(current['macd']) or pd.isna(current['signal']):
            return None
        if pd.isna(previous['macd']) or pd.isna(previous['signal']):
            return None

        # Detect crossover
        current_signal = 'buy' if current['macd'] > current['signal'] else 'sell'
        previous_signal = 'buy' if previous['macd'] > previous['signal'] else 'sell'

        # Only signal on crossover
        if current_signal != previous_signal:
            # Check we haven't just sent this signal
            if self.previous_signal == current_signal:
                return None

            self.previous_signal = current_signal

            # Calculate confidence based on histogram strength
            histogram_abs = abs(float(current['histogram']))
            price = float(current['price'])
            histogram_pct = (histogram_abs / price) * 100 if price > 0 else 0

            # Higher confidence for stronger divergence
            confidence = min(0.9, 0.6 + (histogram_pct * 10))

            return TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side=current_signal,
                confidence=confidence,
                reason=f"MACD {'bullish' if current_signal == 'buy' else 'bearish'} crossover",
                metadata={
                    'macd': float(current['macd']),
                    'signal': float(current['signal']),
                    'histogram': float(current['histogram']),
                    'price': float(current['price'])
                }
            )

        return None
