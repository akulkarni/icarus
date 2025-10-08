"""
Bollinger Bands Strategy

Uses Bollinger Bands indicator:
- Buy when price touches or crosses below lower band
- Sell when price touches or crosses above upper band

Reference: backtest_bollinger.py
"""
import pandas as pd
import numpy as np
from decimal import Decimal
from typing import Optional
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent


def calculate_bollinger_bands(prices, period=20, num_std=2):
    """
    Calculate Bollinger Bands

    Args:
        prices: List or array of prices
        period: Moving average period (default 20)
        num_std: Number of standard deviations (default 2)

    Returns:
        Tuple of (sma, upper_band, lower_band) as numpy arrays
    """
    prices_series = pd.Series(prices)

    # Calculate SMA (Simple Moving Average)
    sma = prices_series.rolling(window=period).mean().values

    # Calculate standard deviation
    std = prices_series.rolling(window=period).std().values

    # Calculate bands
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)

    return sma, upper_band, lower_band


class BollingerBandsStrategy(StrategyAgent):
    """
    Bollinger Bands trading strategy

    Signals:
    - BUY: Price at or below lower band
    - SELL: Price at or above upper band
    """

    def __init__(
        self,
        event_bus,
        symbol: str = 'ETHUSDT',
        period: int = 20,
        num_std: int = 2,
        warmup_period: int = 20
    ):
        """
        Initialize Bollinger Bands strategy

        Args:
            event_bus: Event bus for publishing signals
            symbol: Trading symbol (default ETHUSDT)
            period: Bollinger Bands period (default 20)
            num_std: Number of standard deviations (default 2)
            warmup_period: Minimum data points before signals
        """
        params = {
            'period': period,
            'num_std': num_std,
            'warmup_period': warmup_period,
            'max_history': 200
        }
        super().__init__('bollinger', event_bus, symbol, params)
        self.previous_signal = None

    async def analyze(self) -> Optional[TradingSignalEvent]:
        """
        Analyze prices and generate trading signal

        Returns:
            TradingSignalEvent if signal generated, else None
        """
        df = self.get_prices_df()

        # Check if enough data
        if len(df) < self.params['period']:
            return None

        # Calculate Bollinger Bands
        sma, upper_band, lower_band = calculate_bollinger_bands(
            df['price'].values,
            period=self.params['period'],
            num_std=self.params['num_std']
        )

        # Add to dataframe
        df['sma'] = sma
        df['upper_band'] = upper_band
        df['lower_band'] = lower_band

        # Get current values
        current = df.iloc[-1]
        current_price = current['price']
        current_lower = current['lower_band']
        current_upper = current['upper_band']
        current_sma = current['sma']

        # Check for NaN
        if pd.isna(current_lower) or pd.isna(current_upper):
            return None

        # Determine signal
        signal = None

        # Buy signal: Price at or below lower band
        if current_price <= current_lower:
            if self.previous_signal != 'buy':
                self.previous_signal = 'buy'
                signal = TradingSignalEvent(
                    strategy_name=self.name,
                    symbol=self.symbol,
                    side='buy',
                    confidence=Decimal('0.75'),
                    reason=f"Price ${current_price:.2f} at/below lower band ${current_lower:.2f}",
                    metadata={
                        'price': float(current_price),
                        'lower_band': float(current_lower),
                        'sma': float(current_sma),
                        'upper_band': float(current_upper)
                    }
                )

        # Sell signal: Price at or above upper band
        elif current_price >= current_upper:
            if self.previous_signal != 'sell':
                self.previous_signal = 'sell'
                signal = TradingSignalEvent(
                    strategy_name=self.name,
                    symbol=self.symbol,
                    side='sell',
                    confidence=Decimal('0.75'),
                    reason=f"Price ${current_price:.2f} at/above upper band ${current_upper:.2f}",
                    metadata={
                        'price': float(current_price),
                        'upper_band': float(current_upper),
                        'sma': float(current_sma),
                        'lower_band': float(current_lower)
                    }
                )

        return signal
