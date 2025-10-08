"""
Mean Reversion Strategy

Uses RSI (Relative Strength Index):
- Buy when RSI < 30 (oversold)
- Sell when RSI > 70 (overbought)

Reference: backtest_meanreversion.py
"""
import pandas as pd
import numpy as np
from decimal import Decimal
from typing import Optional
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


def calculate_rsi(prices, period=14):
    """
    Calculate RSI (Relative Strength Index)

    Args:
        prices: Array of prices
        period: RSI period (default 14)

    Returns:
        Array of RSI values (0-100)
    """
    # Calculate price changes
    deltas = np.diff(prices)

    # Separate gains and losses
    seed = deltas[:period + 1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period

    # Handle division by zero
    if down == 0:
        return np.full(len(prices), 100.0)

    # Calculate initial RS and RSI
    rs = up / down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100.0 - 100.0 / (1.0 + rs)

    # Calculate RSI for remaining values using smoothed RS
    for i in range(period, len(prices)):
        delta = deltas[i - 1]

        if delta > 0:
            upval = delta
            downval = 0.0
        else:
            upval = 0.0
            downval = -delta

        # Smooth the average gains/losses
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period

        # Calculate RSI
        if down == 0:
            rsi[i] = 100.0
        else:
            rs = up / down
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)

    return rsi


class MeanReversionStrategy(StrategyAgent):
    """
    Mean Reversion trading strategy using RSI

    Signals:
    - BUY: RSI < oversold threshold (default 30)
    - SELL: RSI > overbought threshold (default 70)
    """

    def __init__(
        self,
        event_bus,
        symbol: str = 'BTCUSDT',
        rsi_period: int = 14,
        oversold_threshold: int = 30,
        overbought_threshold: int = 70,
        warmup_period: int = 14
    ):
        """
        Initialize Mean Reversion strategy

        Args:
            event_bus: Event bus for publishing signals
            symbol: Trading symbol (default BTCUSDT)
            rsi_period: RSI calculation period (default 14)
            oversold_threshold: RSI threshold for buy signal (default 30)
            overbought_threshold: RSI threshold for sell signal (default 70)
            warmup_period: Minimum data points before signals
        """
        params = {
            'rsi_period': rsi_period,
            'oversold_threshold': oversold_threshold,
            'overbought_threshold': overbought_threshold,
            'warmup_period': warmup_period,
            'max_history': 200
        }
        super().__init__('meanreversion', event_bus, symbol, params)
        self.previous_signal = None

    async def analyze(self) -> Optional[TradingSignalEvent]:
        """
        Analyze prices and generate trading signal

        Returns:
            TradingSignalEvent if signal generated, else None
        """
        df = self.get_prices_df()

        # Check if enough data
        if len(df) < self.params['rsi_period']:
            return None

        # Calculate RSI
        rsi_values = calculate_rsi(
            df['price'].values,
            period=self.params['rsi_period']
        )

        df['rsi'] = rsi_values

        # Get current values
        current = df.iloc[-1]
        current_price = current['price']
        current_rsi = current['rsi']

        # Check for NaN
        if pd.isna(current_rsi):
            return None

        # Determine signal
        signal = None

        # Buy signal: RSI < oversold threshold
        if current_rsi < self.params['oversold_threshold']:
            if self.previous_signal != 'buy':
                self.previous_signal = 'buy'
                signal = TradingSignalEvent(
                    strategy_name=self.name,
                    symbol=self.symbol,
                    side='buy',
                    confidence=Decimal('0.70'),
                    reason=f"RSI {current_rsi:.1f} < {self.params['oversold_threshold']} (oversold)",
                    metadata={
                        'price': float(current_price),
                        'rsi': float(current_rsi),
                        'threshold': self.params['oversold_threshold']
                    }
                )

        # Sell signal: RSI > overbought threshold
        elif current_rsi > self.params['overbought_threshold']:
            if self.previous_signal != 'sell':
                self.previous_signal = 'sell'
                signal = TradingSignalEvent(
                    strategy_name=self.name,
                    symbol=self.symbol,
                    side='sell',
                    confidence=Decimal('0.70'),
                    reason=f"RSI {current_rsi:.1f} > {self.params['overbought_threshold']} (overbought)",
                    metadata={
                        'price': float(current_price),
                        'rsi': float(current_rsi),
                        'threshold': self.params['overbought_threshold']
                    }
                )

        return signal
