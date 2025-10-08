"""
Breakout Strategy

Signals:
- BUY: Price breaks above 20-period high with volume > 1.5x average
- SELL: Price breaks below 20-period low

Reference: backtest_breakout.py
"""
import pandas as pd
from decimal import Decimal
from typing import Optional
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


def calculate_rolling_high_low(df, period=20):
    """Calculate rolling high/low bands"""
    df['high_band'] = df['high'].rolling(window=period).max()
    df['low_band'] = df['low'].rolling(window=period).min()
    return df


class BreakoutStrategy(StrategyAgent):
    """Breakout trading strategy"""

    def __init__(self, event_bus, symbol='SOLUSDT', period=20, volume_multiplier=1.5, warmup_period=20):
        params = {
            'period': period,
            'volume_multiplier': volume_multiplier,
            'warmup_period': warmup_period,
            'max_history': 200
        }
        super().__init__('breakout', event_bus, symbol, params)
        self.previous_signal = None
        # Store OHLCV data
        self.highs = []
        self.lows = []
        self.volumes = []

    def add_ohlcv(self, high: Decimal, low: Decimal, volume: Decimal):
        """Add OHLCV data point"""
        self.highs.append(float(high))
        self.lows.append(float(low))
        self.volumes.append(float(volume))

        # Trim to max history
        max_hist = self.params['max_history']
        if len(self.highs) > max_hist:
            self.highs = self.highs[-max_hist:]
            self.lows = self.lows[-max_hist:]
            self.volumes = self.volumes[-max_hist:]

    async def analyze(self) -> Optional[TradingSignalEvent]:
        """Generate trading signal"""
        df = self.get_prices_df()

        if len(df) < self.params['period']:
            return None

        # Use price as high/low if not provided (simplified for now)
        if 'high' not in df.columns:
            df['high'] = df['price']
        if 'low' not in df.columns:
            df['low'] = df['price']

        # Calculate bands
        df = calculate_rolling_high_low(df, period=self.params['period'])
        df['volume_avg'] = df['volume'].rolling(window=self.params['period']).mean()

        # Get current and previous
        current = df.iloc[-1]
        previous = df.iloc[-2] if len(df) > 1 else None

        if pd.isna(current['high_band']) or previous is None:
            return None

        current_price = current['price']
        current_high = current['high']
        current_low = current['low']
        current_volume = current['volume']
        volume_avg = current['volume_avg']
        prev_high_band = previous['high_band']
        prev_low_band = previous['low_band']

        signal = None

        # Buy: breakout above with volume
        if (current_high > prev_high_band and
            current_volume > self.params['volume_multiplier'] * volume_avg and
            self.previous_signal != 'buy'):
            self.previous_signal = 'buy'
            signal = TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side='buy',
                confidence=Decimal('0.75'),
                reason=f"Breakout above ${prev_high_band:.2f} with volume",
                metadata={
                    'price': float(current_price),
                    'high_band': float(prev_high_band),
                    'volume': float(current_volume),
                    'volume_avg': float(volume_avg)
                }
            )

        # Sell: breakdown below
        elif (current_low < prev_low_band and self.previous_signal != 'sell'):
            self.previous_signal = 'sell'
            signal = TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side='sell',
                confidence=Decimal('0.70'),
                reason=f"Breakdown below ${prev_low_band:.2f}",
                metadata={
                    'price': float(current_price),
                    'low_band': float(prev_low_band)
                }
            )

        return signal
