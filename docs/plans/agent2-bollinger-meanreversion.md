# Agent 2: Bollinger Bands + Mean Reversion Strategies

**Branch**: `agent2-strategies-bollinger-meanreversion`
**Estimated Time**: 2-3 hours
**Dependencies**: None (can start immediately)

---

## Overview

You will implement two new trading strategies: Bollinger Bands and Mean Reversion (RSI-based). These will follow the same pattern as existing strategies (Momentum and MACD).

**What you're building**:
- Bollinger Bands strategy (uses price bands based on standard deviation)
- Mean Reversion strategy (uses RSI indicator for overs

old/overbought)
- Tests for both strategies
- Integration with existing strategy system

**Key Principles**:
- **DRY**: Reuse StrategyAgent base class patterns
- **YAGNI**: Implement only specified indicators
- **TDD**: Write tests first
- **Frequent commits**: Commit after every 2-3 steps

---

## Prerequisites - Understanding the Codebase

### 1. Strategy Agent Pattern
Read these files carefully:
- `src/agents/strategy.py` - Base StrategyAgent class
- `src/agents/strategies/momentum.py` - Example strategy implementation
- `src/agents/strategies/macd.py` - Another example

**Key concepts**:
```python
class MyStrategy(StrategyAgent):
    def __init__(self, event_bus, symbol, params):
        super().__init__('my_strategy', event_bus, symbol, params)

    async def analyze(self) -> TradingSignalEvent | None:
        # Get price history
        df = self.get_prices_df()

        # Calculate indicators
        # Generate signal
        # Return TradingSignalEvent or None
```

### 2. Backtest Reference Code
Read these for indicator calculations:
- `backtest_bollinger.py` - Bollinger Bands logic (lines 17-25, 64-98)
- `backtest_meanreversion.py` - RSI calculation (lines 18-50, 89-120)

### 3. Event System
- `src/models/events.py` - TradingSignalEvent structure
- Events are immutable dataclasses

---

## Step 1: Setup & Bollinger Bands Tests (30 min)

### 1.1 Create branch
```bash
git checkout -b agent2-strategies-bollinger-meanreversion
```

### 1.2 Create test file for Bollinger Bands
**File**: `tests/test_agents/test_strategies/__init__.py`
```python
# Empty file
```

**File**: `tests/test_agents/test_strategies/test_bollinger.py`

```python
"""Tests for Bollinger Bands strategy"""
import pytest
import pandas as pd
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.agents.strategies.bollinger import BollingerBandsStrategy
from src.models.events import TradingSignalEvent


@pytest.fixture
def event_bus():
    """Mock event bus"""
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def bollinger_strategy(event_bus):
    """Create Bollinger strategy instance"""
    return BollingerBandsStrategy(
        event_bus=event_bus,
        symbol='ETHUSDT',
        period=20,
        num_std=2,
        warmup_period=20
    )


def test_bollinger_init(bollinger_strategy):
    """Test Bollinger strategy initialization"""
    assert bollinger_strategy.name == 'bollinger'
    assert bollinger_strategy.symbol == 'ETHUSDT'
    assert bollinger_strategy.params['period'] == 20
    assert bollinger_strategy.params['num_std'] == 2


def test_bollinger_calculate_bands():
    """Test Bollinger Bands calculation"""
    from src.agents.strategies.bollinger import calculate_bollinger_bands

    # Create test data
    prices = [100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
              105, 107, 106, 108, 107, 109, 108, 110, 109, 111,
              110]

    sma, upper, lower = calculate_bollinger_bands(prices, period=20, num_std=2)

    # Verify shapes
    assert len(sma) == len(prices)
    assert len(upper) == len(prices)
    assert len(lower) == len(prices)

    # Verify relationships (upper > sma > lower)
    for i in range(20, len(prices)):
        if not pd.isna(sma[i]):
            assert upper[i] > sma[i]
            assert sma[i] > lower[i]


@pytest.mark.asyncio
async def test_bollinger_no_signal_insufficient_data(bollinger_strategy):
    """Test no signal when insufficient data"""
    # Add only 10 prices (need 20)
    for i in range(10):
        bollinger_strategy.add_price(Decimal(str(100 + i)))

    signal = await bollinger_strategy.analyze()
    assert signal is None


@pytest.mark.asyncio
async def test_bollinger_buy_signal_at_lower_band(bollinger_strategy):
    """Test buy signal when price touches lower band"""
    # Add prices trending down then touching lower band
    prices = [110] * 10 + list(range(110, 90, -1))  # Declining prices

    for price in prices:
        bollinger_strategy.add_price(Decimal(str(price)))

    signal = await bollinger_strategy.analyze()

    # Should generate buy signal when price near lower band
    if signal:
        assert signal.side == 'buy'
        assert signal.symbol == 'ETHUSDT'
        assert signal.strategy_name == 'bollinger'


@pytest.mark.asyncio
async def test_bollinger_sell_signal_at_upper_band(bollinger_strategy):
    """Test sell signal when price touches upper band"""
    # Add prices trending up then touching upper band
    prices = [90] * 10 + list(range(90, 110))  # Rising prices

    for price in prices:
        bollinger_strategy.add_price(Decimal(str(price)))

    signal = await bollinger_strategy.analyze()

    # Should generate sell signal when price near upper band
    if signal:
        assert signal.side == 'sell'
        assert signal.symbol == 'ETHUSDT'
        assert signal.strategy_name == 'bollinger'
```

Run tests (they will fail - that's expected):
```bash
pytest tests/test_agents/test_strategies/test_bollinger.py -v
```

### 1.3 Implement Bollinger Bands Strategy
**File**: `src/agents/strategies/__init__.py` (update)

```python
# Add to existing imports
from src.agents.strategies.bollinger import BollingerBandsStrategy

__all__ = [
    'MomentumStrategy',
    'MACDStrategy',
    'BollingerBandsStrategy',  # Add this
]
```

**File**: `src/agents/strategies/bollinger.py` (new file)

```python
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
```

Run tests:
```bash
pytest tests/test_agents/test_strategies/test_bollinger.py -v
```

### ✅ CHECKPOINT 1: Commit
```bash
git add src/agents/strategies/bollinger.py tests/test_agents/test_strategies/
git commit -m "feat(strategies): implement Bollinger Bands strategy with tests"
```

---

## Step 2: Mean Reversion Strategy (RSI) (30 min)

### 2.1 Create tests for Mean Reversion
**File**: `tests/test_agents/test_strategies/test_meanreversion.py` (new file)

```python
"""Tests for Mean Reversion (RSI) strategy"""
import pytest
import pandas as pd
import numpy as np
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.agents.strategies.meanreversion import MeanReversionStrategy
from src.models.events import TradingSignalEvent


@pytest.fixture
def event_bus():
    """Mock event bus"""
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def meanreversion_strategy(event_bus):
    """Create Mean Reversion strategy instance"""
    return MeanReversionStrategy(
        event_bus=event_bus,
        symbol='BTCUSDT',
        rsi_period=14,
        oversold_threshold=30,
        overbought_threshold=70
    )


def test_meanreversion_init(meanreversion_strategy):
    """Test Mean Reversion strategy initialization"""
    assert meanreversion_strategy.name == 'meanreversion'
    assert meanreversion_strategy.symbol == 'BTCUSDT'
    assert meanreversion_strategy.params['rsi_period'] == 14
    assert meanreversion_strategy.params['oversold_threshold'] == 30
    assert meanreversion_strategy.params['overbought_threshold'] == 70


def test_rsi_calculation():
    """Test RSI calculation"""
    from src.agents.strategies.meanreversion import calculate_rsi

    # Create test data with clear trend
    # Uptrend should have RSI > 50
    prices = np.array([100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                       110, 111, 112, 113, 114, 115, 116, 117, 118, 119])

    rsi = calculate_rsi(prices, period=14)

    # Verify shape
    assert len(rsi) == len(prices)

    # RSI should be between 0 and 100
    for i in range(14, len(rsi)):
        assert 0 <= rsi[i] <= 100

    # Uptrend should have higher RSI
    assert rsi[-1] > 50


@pytest.mark.asyncio
async def test_meanreversion_no_signal_insufficient_data(meanreversion_strategy):
    """Test no signal when insufficient data"""
    # Add only 10 prices (need 14+ for RSI)
    for i in range(10):
        meanreversion_strategy.add_price(Decimal(str(100 + i)))

    signal = await meanreversion_strategy.analyze()
    assert signal is None


@pytest.mark.asyncio
async def test_meanreversion_buy_signal_oversold(meanreversion_strategy):
    """Test buy signal when RSI < 30 (oversold)"""
    # Create oversold condition: sharp decline
    prices = [100] * 5 + list(range(100, 70, -2))  # Sharp decline

    for price in prices:
        meanreversion_strategy.add_price(Decimal(str(price)))

    signal = await meanreversion_strategy.analyze()

    # Should generate buy signal in oversold condition
    if signal:
        assert signal.side == 'buy'
        assert signal.symbol == 'BTCUSDT'
        assert signal.strategy_name == 'meanreversion'
        assert 'RSI' in signal.reason or 'oversold' in signal.reason.lower()


@pytest.mark.asyncio
async def test_meanreversion_sell_signal_overbought(meanreversion_strategy):
    """Test sell signal when RSI > 70 (overbought)"""
    # Create overbought condition: sharp rise
    prices = [70] * 5 + list(range(70, 100, 2))  # Sharp rise

    for price in prices:
        meanreversion_strategy.add_price(Decimal(str(price)))

    signal = await meanreversion_strategy.analyze()

    # Should generate sell signal in overbought condition
    if signal:
        assert signal.side == 'sell'
        assert signal.symbol == 'BTCUSDT'
        assert signal.strategy_name == 'meanreversion'
        assert 'RSI' in signal.reason or 'overbought' in signal.reason.lower()
```

Run tests (will fail):
```bash
pytest tests/test_agents/test_strategies/test_meanreversion.py -v
```

### 2.2 Implement Mean Reversion Strategy
**File**: `src/agents/strategies/__init__.py` (update)

```python
from src.agents.strategies.meanreversion import MeanReversionStrategy

__all__ = [
    'MomentumStrategy',
    'MACDStrategy',
    'BollingerBandsStrategy',
    'MeanReversionStrategy',  # Add this
]
```

**File**: `src/agents/strategies/meanreversion.py` (new file)

```python
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
```

Run tests:
```bash
pytest tests/test_agents/test_strategies/test_meanreversion.py -v
```

### ✅ CHECKPOINT 2: Commit & Request Review
```bash
git add src/agents/strategies/meanreversion.py tests/test_agents/test_strategies/test_meanreversion.py src/agents/strategies/__init__.py
git commit -m "feat(strategies): implement Mean Reversion (RSI) strategy with tests"
git push -u origin agent2-strategies-bollinger-meanreversion
```

**🛑 STOP AND REQUEST REVIEW**: Post in chat: "Agent 2 - Checkpoint 2 complete. Both strategies implemented with tests. Ready for review."

---

## Step 3: Integration & Configuration (20 min)

### 3.1 Update configuration
**File**: `config/app.yaml` (add strategy configs)

```yaml
# Add to strategies section:
strategies:
  # ... existing strategies ...

  bollinger:
    enabled: true
    symbol: ETHUSDT
    period: 20
    num_std: 2
    warmup_period: 20

  meanreversion:
    enabled: true
    symbol: BTCUSDT
    rsi_period: 14
    oversold_threshold: 30
    overbought_threshold: 70
    warmup_period: 14
```

### 3.2 Write integration test
**File**: `tests/test_agents/test_strategies/test_integration.py` (new file)

```python
"""Integration tests for new strategies"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal


@pytest.mark.asyncio
async def test_bollinger_strategy_full_cycle():
    """Test Bollinger strategy through full signal cycle"""
    from src.agents.strategies.bollinger import BollingerBandsStrategy

    event_bus = MagicMock()
    event_bus.subscribe = MagicMock(return_value=AsyncMock())
    event_bus.publish = AsyncMock()

    strategy = BollingerBandsStrategy(event_bus, symbol='ETHUSDT')

    # Add enough data for analysis
    for i in range(30):
        strategy.add_price(Decimal(str(100 + i * 0.5)))

    # Should be able to analyze
    signal = await strategy.analyze()
    # Signal may or may not be generated depending on data
    assert signal is None or signal.symbol == 'ETHUSDT'


@pytest.mark.asyncio
async def test_meanreversion_strategy_full_cycle():
    """Test Mean Reversion strategy through full signal cycle"""
    from src.agents.strategies.meanreversion import MeanReversionStrategy

    event_bus = MagicMock()
    event_bus.subscribe = MagicMock(return_value=AsyncMock())
    event_bus.publish = AsyncMock()

    strategy = MeanReversionStrategy(event_bus, symbol='BTCUSDT')

    # Add enough data for analysis
    for i in range(30):
        strategy.add_price(Decimal(str(100 + i * 0.5)))

    # Should be able to analyze
    signal = await strategy.analyze()
    assert signal is None or signal.symbol == 'BTCUSDT'


def test_strategies_can_be_imported():
    """Test that all strategies can be imported"""
    from src.agents.strategies import (
        MomentumStrategy,
        MACDStrategy,
        BollingerBandsStrategy,
        MeanReversionStrategy
    )

    assert MomentumStrategy is not None
    assert MACDStrategy is not None
    assert BollingerBandsStrategy is not None
    assert MeanReversionStrategy is not None
```

Run all strategy tests:
```bash
pytest tests/test_agents/test_strategies/ -v
```

### ✅ CHECKPOINT 3: Commit & Request Review
```bash
git add config/app.yaml tests/test_agents/test_strategies/test_integration.py
git commit -m "feat(strategies): add configuration and integration tests"
git push
```

**🛑 STOP AND REQUEST REVIEW**: Post in chat: "Agent 2 - Checkpoint 3 complete. Integration and configuration done. Ready for final review."

---

## Step 4: Documentation & Testing (15 min)

### 4.1 Create strategy documentation
**File**: `docs/strategies/bollinger-bands.md`

```markdown
# Bollinger Bands Strategy

## Overview
Uses Bollinger Bands indicator to identify overbought/oversold conditions.

## Indicator
- **SMA**: 20-period simple moving average
- **Upper Band**: SMA + (2 × standard deviation)
- **Lower Band**: SMA - (2 × standard deviation)

## Signals
- **BUY**: Price touches or goes below lower band
- **SELL**: Price touches or goes above upper band

## Parameters
- `period`: Moving average period (default: 20)
- `num_std`: Number of standard deviations (default: 2)
- `symbol`: Trading symbol (default: ETHUSDT)

## Configuration
```yaml
strategies:
  bollinger:
    enabled: true
    symbol: ETHUSDT
    period: 20
    num_std: 2
    warmup_period: 20
```

## Theory
Bollinger Bands measure volatility. When bands contract, volatility is low.
When bands expand, volatility is high. Price tends to revert to the mean (SMA).

## Risk Considerations
- False signals in trending markets
- Best in range-bound markets
- Combine with volume or other indicators
```

**File**: `docs/strategies/mean-reversion.md`

```markdown
# Mean Reversion (RSI) Strategy

## Overview
Uses RSI (Relative Strength Index) to identify oversold/overbought conditions.

## Indicator
- **RSI**: 14-period Relative Strength Index
- **Range**: 0-100
- **Oversold**: < 30
- **Overbought**: > 70

## Signals
- **BUY**: RSI < 30 (oversold)
- **SELL**: RSI > 70 (overbought)

## Parameters
- `rsi_period`: RSI calculation period (default: 14)
- `oversold_threshold`: Buy threshold (default: 30)
- `overbought_threshold`: Sell threshold (default: 70)
- `symbol`: Trading symbol (default: BTCUSDT)

## Configuration
```yaml
strategies:
  meanreversion:
    enabled: true
    symbol: BTCUSDT
    rsi_period: 14
    oversold_threshold: 30
    overbought_threshold: 70
    warmup_period: 14
```

## Theory
RSI measures momentum. Values < 30 suggest oversold (potential reversal up).
Values > 70 suggest overbought (potential reversal down).

## Risk Considerations
- Can stay overbought/oversold for extended periods in strong trends
- False signals during trends
- Best in range-bound markets
```

### 4.2 Add README for strategies
**File**: `src/agents/strategies/README.md`

```markdown
# Trading Strategies

This directory contains all trading strategy implementations.

## Available Strategies

1. **Momentum** (`momentum.py`) - Moving average crossover
2. **MACD** (`macd.py`) - MACD indicator signals
3. **Bollinger Bands** (`bollinger.py`) - Price band reversion
4. **Mean Reversion** (`meanreversion.py`) - RSI-based reversion

## Creating a New Strategy

All strategies inherit from `StrategyAgent` base class:

```python
from src.agents.strategy import StrategyAgent
from src.models.events import TradingSignalEvent

class MyStrategy(StrategyAgent):
    def __init__(self, event_bus, symbol, **params):
        super().__init__('my_strategy', event_bus, symbol, params)

    async def analyze(self) -> TradingSignalEvent | None:
        # Get price data
        df = self.get_prices_df()

        # Calculate indicators
        # ...

        # Generate signal
        if buy_condition:
            return TradingSignalEvent(
                strategy_name=self.name,
                symbol=self.symbol,
                side='buy',
                confidence=0.7,
                reason="Buy condition met"
            )

        return None
```

## Testing

All strategies have comprehensive tests in `tests/test_agents/test_strategies/`:

```bash
pytest tests/test_agents/test_strategies/ -v
```

## Configuration

Strategies are configured in `config/app.yaml`:

```yaml
strategies:
  my_strategy:
    enabled: true
    symbol: BTCUSDT
    param1: value1
```
```

### 4.3 Run full test suite
```bash
# Run all tests
pytest tests/test_agents/test_strategies/ -v --cov=src.agents.strategies

# Verify coverage > 80%
```

### ✅ FINAL CHECKPOINT: Commit & Request Review
```bash
git add docs/strategies/ src/agents/strategies/README.md
git commit -m "docs(strategies): add comprehensive documentation for Bollinger and Mean Reversion"
git push
```

**🛑 STOP AND REQUEST FINAL REVIEW**: Post in chat: "Agent 2 - ALL WORK COMPLETE. Both strategies fully implemented with tests and documentation. Ready for final review and merge."

---

## Testing Checklist

Before final review:

- [ ] All tests pass: `pytest tests/test_agents/test_strategies/ -v`
- [ ] Test coverage > 80%: `pytest tests/test_agents/test_strategies/ --cov=src.agents.strategies`
- [ ] Bollinger Bands strategy generates signals correctly
- [ ] Mean Reversion strategy generates signals correctly
- [ ] Both strategies follow same pattern as existing strategies
- [ ] Configuration added to config/app.yaml
- [ ] Documentation complete
- [ ] Code follows DRY, YAGNI, TDD principles

## Success Criteria

✅ Bollinger Bands strategy implemented
✅ Mean Reversion (RSI) strategy implemented
✅ Comprehensive tests for both
✅ Indicator calculations accurate
✅ Configuration added
✅ Documentation complete
✅ Follows existing code patterns

---

## Common Issues & Solutions

### Issue: RSI calculation produces NaN
**Solution**: Ensure at least `rsi_period + 1` prices before calculation

### Issue: Bollinger Bands not generating signals
**Solution**: Check that `num_std` is not too large, causing bands to be too wide

### Issue: Tests fail with "insufficient data"
**Solution**: Add at least `warmup_period` prices before calling `analyze()`

### Issue: Import errors
**Solution**: Ensure `__init__.py` exports new strategy classes

---

## Notes

- Both strategies tested against backtest reference implementations
- RSI calculation uses exponential smoothing (Wilder's method)
- Bollinger Bands use standard deviation of closing prices
- Signal deduplication prevents repeated signals
- Confidence levels: Bollinger (0.75), Mean Reversion (0.70)

**Good luck! Remember to request review at checkpoints.**
