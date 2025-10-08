"""
Stochastic Oscillator Strategy

Signals:
- BUY: %K crosses above %D in oversold zone (<20)
- SELL: %K crosses below %D in overbought zone (>80)

Reference: backtest_stochastic.py
"""
import pandas as pd
import numpy as np
from decimal import Decimal
from typing import Optional
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Calculate Stochastic %K and %D"""
    lowest_low = pd.Series(low).rolling(window=k_period).min().values
    highest_high = pd.Series(high).rolling(window=k_period).max().values

    k_values = np.zeros(len(close))
    for i in range(len(close)):
        if not np.isnan(lowest_low[i]) and not np.isnan(highest_high[i]):
            denom = highest_high[i] - lowest_low[i]
            if denom != 0:
                k_values[i] = ((close[i] - lowest_low[i]) / denom) * 100
            else:
                k_values[i] = 50

    d_values = pd.Series(k_values).rolling(window=d_period).mean().values
    return k_values, d_values


class StochasticStrategy(StrategyAgent):
    """Stochastic Oscillator strategy"""

    def __init__(self, event_bus, symbol='ETHUSDT', k_period=14, d_period=3,
                 oversold=20, overbought=80, warmup_period=17):
        params = {
            'k_period': k_period,
            'd_period': d_period,
            'oversold': oversold,
            'overbought': overbought,
            'warmup_period': warmup_period,
            'max_history': 200
        }
        super().__init__('stochastic', event_bus, symbol, params)
        self.previous_k = None
        self.previous_d = None

    async def analyze(self) -> Optional[TradingSignalEvent]:
        """Generate signal"""
        df = self.get_prices_df()

        if len(df) < self.params['k_period'] + self.params['d_period']:
            return None

        # Use price as high/low if not provided
        if 'high' not in df.columns:
            df['high'] = df['price']
        if 'low' not in df.columns:
            df['low'] = df['price']

        high = df['high'].values
        low = df['low'].values
        close = df['price'].values

        k, d = calculate_stochastic(high, low, close,
                                     self.params['k_period'],
                                     self.params['d_period'])

        current_k = k[-1]
        current_d = d[-1]
        current_price = float(df.iloc[-1]['price'])

        if np.isnan(current_k) or np.isnan(current_d) or self.previous_k is None:
            self.previous_k = current_k
            self.previous_d = current_d
            return None

        signal = None

        # Buy: %K crosses above %D in oversold
        if (self.previous_k <= self.previous_d and
            current_k > current_d and
            current_k < self.params['oversold']):
            signal = TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side='buy',
                confidence=Decimal('0.70'),
                reason=f"Stochastic oversold crossover (%K: {current_k:.1f}, %D: {current_d:.1f})",
                metadata={'k': float(current_k), 'd': float(current_d), 'price': current_price}
            )

        # Sell: %K crosses below %D in overbought
        elif (self.previous_k >= self.previous_d and
              current_k < current_d and
              current_k > self.params['overbought']):
            signal = TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side='sell',
                confidence=Decimal('0.70'),
                reason=f"Stochastic overbought crossover (%K: {current_k:.1f}, %D: {current_d:.1f})",
                metadata={'k': float(current_k), 'd': float(current_d), 'price': current_price}
            )

        self.previous_k = current_k
        self.previous_d = current_d
        return signal
