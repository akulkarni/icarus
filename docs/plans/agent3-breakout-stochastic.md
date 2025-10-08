# Agent 3: Breakout + Stochastic Strategies

**Branch**: `agent3-strategies-breakout-stochastic`
**Estimated Time**: 2-3 hours
**Dependencies**: None (can start immediately)

---

## Overview

Implement Breakout (price/volume based) and Stochastic Oscillator strategies following the same pattern as Agent 2.

**References**:
- `backtest_breakout.py` - Breakout logic (lines 18-28, 66-108)
- `backtest_stochastic.py` - Stochastic logic (lines 17-35, 74-113)
- `src/agents/strategies/momentum.py` - Pattern to follow

---

## Step 1: Breakout Strategy (45 min)

### 1.1 Setup
```bash
git checkout -b agent3-strategies-breakout-stochastic
mkdir -p tests/test_agents/test_strategies
```

### 1.2 Write Tests
**File**: `tests/test_agents/test_strategies/test_breakout.py`

```python
"""Tests for Breakout strategy"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from src.agents.strategies.breakout import BreakoutStrategy

@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def breakout_strategy(event_bus):
    return BreakoutStrategy(event_bus=event_bus, symbol='SOLUSDT')

def test_breakout_init(breakout_strategy):
    assert breakout_strategy.name == 'breakout'
    assert breakout_strategy.symbol == 'SOLUSDT'
    assert breakout_strategy.params['period'] == 20

def test_calculate_rolling_bands():
    from src.agents.strategies.breakout import calculate_rolling_high_low
    import pandas as pd

    df = pd.DataFrame({
        'high': [100, 102, 101, 103, 102],
        'low': [98, 99, 97, 100, 99]
    })
    df = calculate_rolling_high_low(df, period=3)
    assert 'high_band' in df.columns
    assert 'low_band' in df.columns

@pytest.mark.asyncio
async def test_breakout_insufficient_data(breakout_strategy):
    for i in range(10):
        breakout_strategy.add_price(Decimal(str(100 + i)))
    signal = await breakout_strategy.analyze()
    assert signal is None

@pytest.mark.asyncio
async def test_breakout_buy_signal(breakout_strategy):
    # Flat then breakout up
    for i in range(20):
        breakout_strategy.add_price(Decimal('100'))
    breakout_strategy.add_price(Decimal('110'))  # Breakout

    signal = await breakout_strategy.analyze()
    if signal:
        assert signal.side == 'buy'
```

### 1.3 Implement Strategy
**File**: `src/agents/strategies/breakout.py`

```python
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
        if len(self.prices) < self.params['period']:
            return None

        # Create dataframe with OHLCV
        df = pd.DataFrame({
            'price': [float(p) for p in self.prices],
            'high': self.highs[-len(self.prices):] if self.highs else [float(p) for p in self.prices],
            'low': self.lows[-len(self.prices):] if self.lows else [float(p) for p in self.prices],
            'volume': self.volumes[-len(self.prices):] if self.volumes else [1.0] * len(self.prices)
        })

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
```

### ✅ CHECKPOINT 1: Commit
```bash
git add src/agents/strategies/breakout.py tests/test_agents/test_strategies/test_breakout.py
git commit -m "feat(strategies): implement Breakout strategy"
pytest tests/test_agents/test_strategies/test_breakout.py -v
```

---

## Step 2: Stochastic Strategy (45 min)

### 2.1 Write Tests
**File**: `tests/test_agents/test_strategies/test_stochastic.py`

```python
"""Tests for Stochastic Oscillator strategy"""
import pytest
import numpy as np
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from src.agents.strategies.stochastic import StochasticStrategy

@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=AsyncMock())
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def stochastic_strategy(event_bus):
    return StochasticStrategy(event_bus=event_bus, symbol='ETHUSDT')

def test_stochastic_init(stochastic_strategy):
    assert stochastic_strategy.name == 'stochastic'
    assert stochastic_strategy.params['k_period'] == 14
    assert stochastic_strategy.params['d_period'] == 3

def test_calculate_stochastic():
    from src.agents.strategies.stochastic import calculate_stochastic

    high = np.array([102, 103, 104, 103, 102] * 5)
    low = np.array([98, 99, 100, 99, 98] * 5)
    close = np.array([100, 101, 102, 101, 100] * 5)

    k, d = calculate_stochastic(high, low, close, k_period=14, d_period=3)

    assert len(k) == len(close)
    assert len(d) == len(close)
    # Values should be 0-100
    assert all(0 <= v <= 100 for v in k[14:] if not np.isnan(v))

@pytest.mark.asyncio
async def test_stochastic_insufficient_data(stochastic_strategy):
    for i in range(10):
        stochastic_strategy.add_ohlc(
            Decimal('102'), Decimal('98'), Decimal('100')
        )
    signal = await stochastic_strategy.analyze()
    assert signal is None
```

### 2.2 Implement Strategy
**File**: `src/agents/strategies/stochastic.py`

```python
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
        self.highs = []
        self.lows = []
        self.previous_k = None
        self.previous_d = None

    def add_ohlc(self, high: Decimal, low: Decimal, close: Decimal):
        """Add OHLC data"""
        self.highs.append(float(high))
        self.lows.append(float(low))
        self.add_price(close)

        max_hist = self.params['max_history']
        if len(self.highs) > max_hist:
            self.highs = self.highs[-max_hist:]
            self.lows = self.lows[-max_hist:]

    async def analyze(self) -> Optional[TradingSignalEvent]:
        """Generate signal"""
        if len(self.prices) < self.params['k_period'] + self.params['d_period']:
            return None

        high = np.array(self.highs[-len(self.prices):])
        low = np.array(self.lows[-len(self.prices):])
        close = np.array([float(p) for p in self.prices])

        k, d = calculate_stochastic(high, low, close,
                                     self.params['k_period'],
                                     self.params['d_period'])

        current_k = k[-1]
        current_d = d[-1]
        current_price = float(self.prices[-1])

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
```

### ✅ CHECKPOINT 2: Commit & Review
```bash
git add src/agents/strategies/stochastic.py tests/test_agents/test_strategies/test_stochastic.py
git commit -m "feat(strategies): implement Stochastic Oscillator strategy"
git push -u origin agent3-strategies-breakout-stochastic
```

**🛑 REQUEST REVIEW**: "Agent 3 - Checkpoint 2. Both strategies implemented."

---

## Step 3: Integration & Config (20 min)

### 3.1 Update exports
**File**: `src/agents/strategies/__init__.py`

```python
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.macd import MACDStrategy
from src.agents.strategies.bollinger import BollingerBandsStrategy
from src.agents.strategies.meanreversion import MeanReversionStrategy
from src.agents.strategies.breakout import BreakoutStrategy
from src.agents.strategies.stochastic import StochasticStrategy

__all__ = [
    'MomentumStrategy',
    'MACDStrategy',
    'BollingerBandsStrategy',
    'MeanReversionStrategy',
    'BreakoutStrategy',
    'StochasticStrategy',
]
```

### 3.2 Config
**File**: `config/app.yaml` (add)

```yaml
strategies:
  breakout:
    enabled: true
    symbol: SOLUSDT
    period: 20
    volume_multiplier: 1.5
    warmup_period: 20

  stochastic:
    enabled: true
    symbol: ETHUSDT
    k_period: 14
    d_period: 3
    oversold: 20
    overbought: 80
    warmup_period: 17
```

### 3.3 Tests
```bash
pytest tests/test_agents/test_strategies/ -v --cov=src.agents.strategies
```

### ✅ FINAL: Commit & Review
```bash
git add src/agents/strategies/__init__.py config/app.yaml
git commit -m "feat(strategies): integrate Breakout and Stochastic strategies"
git push
```

**🛑 FINAL REVIEW**: "Agent 3 - Complete. Both strategies with tests and config."

---

## Success Criteria

✅ Breakout strategy implemented
✅ Stochastic strategy implemented
✅ Tests pass with >80% coverage
✅ Config added
✅ Follows existing patterns
