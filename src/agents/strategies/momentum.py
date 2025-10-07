"""
Momentum Strategy

Uses 20-period and 50-period moving averages.
- Buy when 20MA crosses above 50MA
- Sell when 20MA crosses below 50MA
"""
import pandas as pd
from decimal import Decimal
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


class MomentumStrategy(StrategyAgent):
    """Moving average crossover strategy"""

    def __init__(self, event_bus, symbol: str = 'BTCUSDT',
                 ma_short: int = 20, ma_long: int = 50, warmup_period: int = 50):
        params = {
            'ma_short': ma_short,      # Use parameter instead of hardcoded 20
            'ma_long': ma_long,        # Use parameter instead of hardcoded 50
            'warmup_period': warmup_period,  # Use parameter instead of hardcoded 50
            'max_history': 200
        }
        super().__init__('momentum', event_bus, symbol, params)
        self.previous_signal = None

    async def analyze(self) -> TradingSignalEvent | None:
        """Generate signal based on MA crossover"""
        df = self.get_prices_df()

        if len(df) < self.params['ma_long']:
            return None

        # Calculate moving averages
        ma_short = self.params['ma_short']
        ma_long = self.params['ma_long']

        df['ma_short'] = df['price'].rolling(window=ma_short).mean()
        df['ma_long'] = df['price'].rolling(window=ma_long).mean()

        # Get current and previous values
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Check for NaN values
        if pd.isna(current['ma_short']) or pd.isna(current['ma_long']):
            return None
        if pd.isna(previous['ma_short']) or pd.isna(previous['ma_long']):
            return None

        # Detect crossover
        current_signal = 'buy' if current['ma_short'] > current['ma_long'] else 'sell'
        previous_signal = 'buy' if previous['ma_short'] > previous['ma_long'] else 'sell'

        # Only signal on crossover (change in signal)
        if current_signal != previous_signal:
            # Also check we haven't just sent this signal
            if self.previous_signal == current_signal:
                return None

            self.previous_signal = current_signal

            return TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side=current_signal,
                confidence=0.7,
                reason=f"MA crossover: {ma_short}MA {'above' if current_signal == 'buy' else 'below'} {ma_long}MA",
                metadata={
                    'ma_short': float(current['ma_short']),
                    'ma_long': float(current['ma_long']),
                    'price': float(current['price'])
                }
            )

        return None
