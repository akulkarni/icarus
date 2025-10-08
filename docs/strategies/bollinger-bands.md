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
