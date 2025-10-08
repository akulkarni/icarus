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
