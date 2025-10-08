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
