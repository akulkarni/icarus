# AGENTS.md - Project Overview for AI Agents

## Project Purpose

This is a **cryptocurrency algorithmic trading backtesting framework** built on TimescaleDB. The project enables quantitative analysis of various trading strategies against historical cryptocurrency price data from Binance and CoinGecko APIs.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Flow Pipeline                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
│  External APIs  │───▶│   TimescaleDB   │───▶│  Backtesting │
│                 │    │   Hypertables   │    │  Strategies  │
│  • Binance      │    │                 │    │              │
│  • CoinGecko    │    │  • crypto_prices│    │  • Bollinger │
└─────────────────┘    │  • Aggregates   │    │  • MACD      │
                       └─────────────────┘    │  • RSI       │
                                              │  • Momentum  │
                                              │  • Breakout  │
                                              │  • Stochastic│
                                              └──────────────┘
```

## Core Components

### 1. Data Ingestion Scripts

#### `binance_ingest.py` (PRIMARY DATA SOURCE - RECOMMENDED)
- **Purpose**: Fetches high-quality, granular OHLCV (Open, High, Low, Close, Volume) data from Binance public API
- **Key Features**:
  - No API key required
  - Multiple timeframes: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M
  - Historical data going back years (since coin listing)
  - High rate limits (1200 requests/minute)
  - Automatic pagination for large datasets (handles >1000 records)
  - Includes trade counts and quote volume
- **Data Format**: Uses Binance's BTCUSDT format, converts to base symbols (BTC, ETH, etc.)
- **Usage Pattern**:
  ```bash
  # Fetch 2 years of daily data for backtesting
  python binance_ingest.py --symbols BTC ETH SOL --interval 1d --days 730

  # Fetch 30 days of hourly data for detailed analysis
  python binance_ingest.py --symbols BTC ETH --interval 1h --days 30
  ```

#### `crypto_ingest.py` (ALTERNATIVE SOURCE)
- **Purpose**: Fetches cryptocurrency data from CoinGecko API
- **Key Features**:
  - No API key required
  - Broader coin coverage (thousands of coins)
  - Lower rate limits (~10-50 calls/minute)
  - Max 365 days of daily data
  - Separate volume fetching (may have timestamp mismatches)
- **Use Case**: When you need less common cryptocurrencies not on Binance

### 2. Database Schema (TimescaleDB)

#### Main Hypertable: `crypto_prices`
```sql
CREATE TABLE crypto_prices (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    exchange    TEXT,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    quote_volume DOUBLE PRECISION,
    num_trades  INTEGER
);
```

**Partitioning**: Time-series optimized with automatic partitioning
**Compression**: Automatically compresses data older than 7 days
**Conflict Handling**: `ON CONFLICT DO NOTHING` prevents duplicate inserts

#### Continuous Aggregates (Pre-computed Views)
- **`crypto_prices_5min`**: 5-minute candles
- **`crypto_prices_1hour`**: Hourly candles
- **`crypto_prices_1day`**: Daily candles with statistics (price_stddev, daily_range_pct)

These aggregates are automatically maintained by TimescaleDB and provide faster query performance for longer time periods.

### 3. Backtesting Strategies

All backtesting scripts follow a common pattern:
1. Connect to TimescaleDB
2. Fetch historical OHLCV data for specified timeframe
3. Calculate technical indicators
4. Simulate trades based on strategy rules
5. Calculate ROI (Return on Investment)

#### `backtest_bollinger.py`
**Strategy**: Bollinger Bands Mean Reversion
- **Indicator**: 20-period SMA ± 2 standard deviations
- **Entry**: Buy when price touches/crosses below lower band
- **Exit**: Sell when price touches/crosses above upper band
- **Asset**: ETH (Ethereum)
- **Timeframe**: 90 days of hourly data
- **Logic**: Assumes price will revert to mean after extreme moves

#### `backtest_macd.py`
**Strategy**: MACD (Moving Average Convergence Divergence) Crossover
- **Indicator**: MACD(12, 26, 9) - Fast EMA minus Slow EMA with signal line
- **Entry**: Buy when MACD line crosses above signal line (bullish crossover)
- **Exit**: Sell when MACD line crosses below signal line (bearish crossover)
- **Asset**: ETH
- **Timeframe**: 90 days of hourly data
- **Logic**: Follows momentum shifts and trend changes

#### `backtest_momentum.py`
**Strategy**: Moving Average Crossover
- **Indicator**: 20-period MA and 50-period MA
- **Entry**: Buy when 20MA crosses above 50MA (golden cross)
- **Exit**: Sell when 20MA crosses below 50MA (death cross)
- **Asset**: ETH
- **Timeframe**: 90 days of hourly data
- **Logic**: Trend-following strategy capturing sustained directional moves

#### `backtest_meanreversion.py`
**Strategy**: RSI (Relative Strength Index) Mean Reversion
- **Indicator**: 14-period RSI
- **Entry**: Buy when RSI < 30 (oversold)
- **Exit**: Sell when RSI > 70 (overbought)
- **Asset**: BTC (Bitcoin)
- **Timeframe**: 90 days of hourly data
- **Logic**: Trades against extremes, assumes price will return to equilibrium

#### `backtest_breakout.py`
**Strategy**: Volume-Confirmed Breakout
- **Indicator**: 20-period high/low bands with volume filter
- **Entry**: Buy when price breaks above 20-period high AND volume > 1.5x average
- **Exit**: Sell when price breaks below 20-period low
- **Asset**: SOL (Solana)
- **Timeframe**: 90 days of hourly data
- **Logic**: Captures strong momentum moves confirmed by volume

#### `backtest_stochastic.py`
**Strategy**: Stochastic Oscillator Crossover
- **Indicator**: Stochastic(14, 3, 3) - %K and %D lines
- **Entry**: Buy when %K crosses above %D in oversold zone (< 20)
- **Exit**: Sell when %K crosses below %D in overbought zone (> 80)
- **Asset**: ETH
- **Timeframe**: 90 days of hourly data
- **Logic**: Identifies momentum changes at extreme price levels

## Key Design Patterns & Conventions

### Database Connection Pattern
All scripts use the same connection configuration:
```python
DB_CONFIG = {
    'host': 'vqmau49y7s.ye4xypn0ge.tsdb.cloud.timescale.com',
    'port': 34170,
    'user': 'tsdbadmin',
    'password': 'SecurePass123!@#',
    'database': 'tsdb'
}
```

### Transaction Cost Model
- Default: 0.1% per trade (0.001 multiplier)
- Applied on both buys and sells
- Realistic model for exchange fees

### Position Management
- **All-in/all-out**: Strategies use entire capital for each trade
- **No position sizing**: Doesn't split capital across multiple positions
- **No leverage**: 1:1 capital to position ratio

### Warmup Periods
Each strategy requires a warmup period before trading begins:
- Bollinger Bands: 20 periods
- MACD: 26 periods (slow EMA)
- Momentum: 50 periods (longest MA)
- RSI: 14 periods
- Breakout: 20 periods
- Stochastic: 17 periods (14 + 3)

### Command-Line Interface
All scripts follow the same argument pattern:
```bash
python <script>.py --db-host <host:port>
```

The `--db-host` parameter accepts `hostname:port` format and automatically parses it.

## Database Optimization Features

### 1. Hypertable Partitioning
TimescaleDB automatically partitions data by time, enabling:
- Faster time-range queries
- Efficient data retention policies
- Parallel query execution

### 2. Automatic Compression
- Compresses data older than 7 days
- Reduces storage costs
- Maintains query performance

### 3. Continuous Aggregates
Pre-computed rollups for:
- 5-minute candles
- Hourly candles
- Daily candles with statistics

These are refreshed automatically and provide 10-100x faster queries for aggregated data.

### 4. Indexing Strategy
Primary index on `(symbol, time)` for fast symbol-specific time-range queries.

## Data Quality Considerations

### Binance Data
- **Completeness**: Very high, minimal gaps
- **Accuracy**: Exchange-grade data
- **Granularity**: From 1-minute to monthly
- **Reliability**: 99.9%+ uptime

### CoinGecko Data
- **Completeness**: Moderate, may have gaps
- **Accuracy**: Good but aggregated from multiple sources
- **Granularity**: Daily (fewer points than requested)
- **Reliability**: Rate-limited, occasional timeouts

## Typical Workflow for Agents

### When Adding New Strategies
1. Copy an existing backtest script as template
2. Modify the indicator calculation function
3. Update entry/exit logic in the backtest loop
4. Test with known data ranges first
5. Document strategy parameters in docstring

### When Debugging Poor ROI
1. Check data availability: Query `crypto_prices` for symbol/timeframe
2. Verify indicator calculations: Print intermediate values
3. Examine trade frequency: Add logging for buy/sell signals
4. Review warmup period: Ensure sufficient data before trading starts
5. Validate transaction costs: 0.1% is typical for spot trading

### When Scaling Data Ingestion
1. Use Binance for primary data (faster, more reliable)
2. Batch symbols in groups of 5-10 to respect rate limits
3. Use appropriate intervals:
   - 1m for high-frequency strategies (< 7 days)
   - 1h for medium-term strategies (30-90 days)
   - 1d for long-term strategies (1-5 years)
4. Monitor database size and compression status

### When Optimizing Queries
1. Use continuous aggregates for multi-day/week queries
2. Filter by symbol first, then time range
3. Use `bucket` column for aggregate tables, `time` for raw data
4. Limit result sets with appropriate date ranges

## Environment & Dependencies

### Required Python Packages
```
requests>=2.31.0      # HTTP client for API calls
psycopg2-binary>=2.9.9  # PostgreSQL adapter
pandas                # Data manipulation (implicit requirement)
numpy                 # Numerical computations (implicit requirement)
```

### Database Requirements
- TimescaleDB 2.0+ (PostgreSQL extension)
- Sufficient storage for time-series data (estimate: 1GB per year per symbol at 1-minute granularity)

## Performance Characteristics

### Data Ingestion Speed
- Binance: ~1000 candles per API call, ~10 calls/second sustainable
- CoinGecko: ~50-200 candles per call, ~1 call/2 seconds safe

### Backtest Execution Time
- 90 days hourly data (~2,160 data points): < 1 second per strategy
- 1 year daily data (~365 data points): < 0.5 seconds per strategy
- 30 days 1-minute data (~43,200 data points): 2-5 seconds per strategy

### Query Performance
- Raw data queries: 50-500ms for 90-day range
- Aggregate queries: 10-100ms for 1-year range
- Full table scan: Not recommended (use time-range filters)

## Security Considerations

### Credentials in Code
**WARNING**: Database credentials are hardcoded in all scripts:
- Username: `tsdbadmin`
- Password: `SecurePass123!@#`

**For Production**: Move credentials to environment variables or secure vault.

### API Keys
Both Binance and CoinGecko endpoints used are public and require no authentication.

## Known Limitations & Gotchas

1. **Volume Data Mismatch**: CoinGecko's volume data is fetched separately and may not align perfectly with OHLC timestamps
2. **No Multi-Asset Trading**: Current backtests only handle one asset at a time
3. **No Stop-Loss**: Strategies don't implement stop-loss or take-profit levels
4. **No Slippage Model**: Assumes orders execute at exact close price
5. **Look-Ahead Bias**: Strategies use close price for decisions made during the same candle
6. **No Portfolio Rebalancing**: Each strategy operates independently

## Extending the Project

### Adding New Indicators
Create calculation functions that return numpy arrays matching input length. Examples:
- EMA: Use pandas `ewm()`
- ATR: Calculate true range and apply SMA
- Volume-based: Use rolling windows on volume column

### Adding New Strategies
1. Define indicator parameters in docstring
2. Implement indicator calculation (separate function)
3. Create backtest function with entry/exit logic
4. Use consistent variable names: `cash`, `position`, `portfolio_value`
5. Handle warmup period appropriately
6. Return ROI as percentage

### Integrating New Data Sources
1. Map external format to database schema
2. Handle timestamp conversions (most APIs use Unix milliseconds)
3. Implement rate limiting and retry logic
4. Use batch inserts with `execute_batch()` for efficiency
5. Include `ON CONFLICT DO NOTHING` to handle re-runs

### Multi-Asset Portfolio Backtesting
Would require:
1. Position tracking per symbol
2. Capital allocation strategy
3. Rebalancing logic
4. Correlation analysis
5. Risk management (portfolio-level stop-loss)

## Testing & Validation Strategies

### Data Validation
```sql
-- Check for gaps in data
SELECT symbol,
       time_bucket('1 day', time) as day,
       COUNT(*) as records
FROM crypto_prices
WHERE symbol = 'BTC'
GROUP BY symbol, day
ORDER BY day;

-- Check for outliers
SELECT symbol, time, close
FROM crypto_prices
WHERE symbol = 'BTC'
  AND (close > LAG(close, 1) OVER (ORDER BY time) * 1.5
   OR close < LAG(close, 1) OVER (ORDER BY time) * 0.5);
```

### Strategy Validation
1. **Benchmark Against Buy-and-Hold**: Compare strategy ROI to simple buy-at-start, sell-at-end
2. **Parameter Sensitivity**: Test with different indicator periods
3. **Transaction Cost Impact**: Run with 0%, 0.1%, 0.5% fees to understand sensitivity
4. **Time Period Robustness**: Test across bull markets, bear markets, sideways markets

## Future Enhancement Opportunities

1. **Walk-Forward Optimization**: Train on historical data, test on future data
2. **Multi-Timeframe Analysis**: Combine signals from different timeframes
3. **Machine Learning Integration**: Use indicators as features for ML models
4. **Real-Time Trading Integration**: Connect to exchange APIs for live trading
5. **Risk Metrics**: Sharpe ratio, max drawdown, win rate, profit factor
6. **Parameter Optimization**: Grid search or genetic algorithms for indicator tuning
7. **Web Dashboard**: Visualize strategy performance with charts
8. **Alert System**: Notify when strategy signals trigger

## Critical Agent Guidelines

When working with this codebase:

1. **Always validate data exists** before running backtests - empty results mean no data in database
2. **Check warmup periods** - strategies need sufficient historical data before first trade
3. **Understand the strategy logic** - know whether it's trend-following or mean-reverting
4. **Consider market conditions** - strategies perform differently in trending vs ranging markets
5. **Test incrementally** - start with small date ranges, then expand
6. **Monitor database growth** - 1-minute data accumulates quickly
7. **Use continuous aggregates** - much faster than querying raw data for long periods
8. **Respect API rate limits** - especially CoinGecko (slower than Binance)
9. **Document modifications** - strategy performance is sensitive to parameter changes
10. **Preserve transaction costs** - removing fees creates unrealistic results

## Glossary of Trading Terms

- **OHLCV**: Open, High, Low, Close, Volume - standard candlestick data
- **EMA**: Exponential Moving Average - weights recent prices more heavily
- **SMA**: Simple Moving Average - equal weight to all prices in period
- **RSI**: Relative Strength Index - momentum oscillator (0-100 scale)
- **MACD**: Moving Average Convergence Divergence - trend-following momentum indicator
- **Stochastic**: Momentum indicator comparing close to recent price range
- **Bollinger Bands**: Volatility bands (SMA ± standard deviations)
- **Breakout**: Price moving beyond established support/resistance levels
- **Mean Reversion**: Strategy assuming prices return to average after extremes
- **Momentum**: Strategy following established price trends
- **ROI**: Return on Investment - percentage gain/loss
- **Slippage**: Difference between expected and actual execution price
- **Backtesting**: Testing strategy on historical data
- **Warmup Period**: Initial data needed before strategy can start trading

---

**Last Updated**: October 2025
**Project Status**: Active Development
**Primary Use Case**: Educational/Research Algorithmic Trading
