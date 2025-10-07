# Crypto Backtesting Database Setup

This directory contains scripts for ingesting historical cryptocurrency price data into TimescaleDB for backtesting trading algorithms.

## Database Setup

Your TimescaleDB instance is configured with:

- **Main table**: `crypto_prices` - stores OHLCV data with automatic compression after 7 days
- **Continuous aggregates**:
  - `crypto_prices_5min` - 5-minute candles
  - `crypto_prices_1hour` - hourly candles
  - `crypto_prices_1day` - daily candles with statistics

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Using Binance (Recommended)

Fetch 1 year of daily data:
```bash
python binance_ingest.py --symbols BTC ETH --interval 1d --days 365
```

Fetch 30 days of hourly data for detailed backtesting:
```bash
python binance_ingest.py --symbols BTC ETH SOL ADA --interval 1h --days 30
```

Fetch 7 days of 1-minute data for high-frequency strategies:
```bash
python binance_ingest.py --symbols BTC ETH --interval 1m --days 7
```

### Using CoinGecko (Alternative)

Fetch 90 days for multiple cryptocurrencies:
```bash
python crypto_ingest.py --symbols BTC ETH SOL ADA DOT --days 90
```

## Supported Symbols

Pre-configured symbols (add more in the script):
- BTC (Bitcoin)
- ETH (Ethereum)
- SOL (Solana)
- ADA (Cardano)
- DOT (Polkadot)
- MATIC (Polygon)
- LINK (Chainlink)
- UNI (Uniswap)
- AVAX (Avalanche)
- ATOM (Cosmos)

## Example Queries for Backtesting

### Get Raw Minute Data
```sql
SELECT time, symbol, open, high, low, close, volume
FROM crypto_prices
WHERE symbol = 'BTC'
  AND time >= '2024-01-01'
  AND time < '2024-02-01'
ORDER BY time;
```

### Get Hourly Aggregates (Faster for Longer Periods)
```sql
SELECT bucket, symbol, open, high, low, close, volume
FROM crypto_prices_1hour
WHERE symbol = 'ETH'
  AND bucket >= '2023-01-01'
ORDER BY bucket;
```

### Get Daily Statistics
```sql
SELECT
    bucket as date,
    symbol,
    close,
    volume,
    price_stddev,
    daily_range_pct
FROM crypto_prices_1day
WHERE symbol IN ('BTC', 'ETH', 'SOL')
  AND bucket >= '2024-01-01'
ORDER BY bucket, symbol;
```

### Calculate Returns
```sql
SELECT
    bucket,
    symbol,
    close,
    LAG(close) OVER (PARTITION BY symbol ORDER BY bucket) as prev_close,
    (close - LAG(close) OVER (PARTITION BY symbol ORDER BY bucket))
        / LAG(close) OVER (PARTITION BY symbol ORDER BY bucket) * 100 as return_pct
FROM crypto_prices_1day
WHERE symbol = 'BTC'
  AND bucket >= '2024-01-01'
ORDER BY bucket;
```

### Compare Multiple Tokens
```sql
SELECT
    bucket,
    symbol,
    close,
    volume,
    SUM(volume) OVER (PARTITION BY symbol ORDER BY bucket
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as volume_7day_sum
FROM crypto_prices_1day
WHERE symbol IN ('BTC', 'ETH', 'SOL')
  AND bucket >= '2024-01-01'
ORDER BY bucket, symbol;
```

## Data Sources

### Binance API (Recommended - `binance_ingest.py`)
**Best for backtesting** - High quality, complete historical data:
- **Free, no API key required**
- **Full historical data** from when each coin was listed (years of data available)
- **Multiple timeframes**: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M
- **High rate limits**: 1200 requests/minute
- **Complete OHLCV + trade counts**
- Uses Binance US API (no geo-restrictions for US users)

```bash
# Fetch 5 years of daily data
python binance_ingest.py --symbols BTC ETH SOL --interval 1d --days 1825

# Fetch 30 days of 1-hour data for backtesting
python binance_ingest.py --symbols BTC ETH --interval 1h --days 30

# Fetch 7 days of 1-minute data (high resolution)
python binance_ingest.py --symbols BTC ETH --interval 1m --days 7
```

### CoinGecko API (`crypto_ingest.py`)
Alternative source with broader coin coverage:
- Requires no API key for basic usage
- Lower rate limits (~10-50 calls/minute)
- Provides up to 365 days but returns fewer data points
- Covers thousands of cryptocurrencies including smaller cap coins

## Database Connection

The script connects to your TimescaleDB instance:
- Host: `vqmau49y7s.ye4xypn0ge.tsdb.cloud.timescale.com`
- Port: `34170`
- Database: `tsdb`
- User: `tsdbadmin`

## Next Steps

1. **Run your first ingestion**: Start with a comprehensive backfill
   ```bash
   # Load 2 years of daily data (recommended for backtesting)
   python binance_ingest.py --symbols BTC ETH SOL ADA --interval 1d --days 730
   ```

2. **Add hourly data for detailed analysis**: Load recent hourly data
   ```bash
   # Load 90 days of hourly data for recent backtesting
   python binance_ingest.py --symbols BTC ETH SOL --interval 1h --days 90
   ```

3. **Set up scheduled updates**: Use cron or a scheduler to run daily updates
   ```bash
   # Add to crontab: run daily at 1 AM to update with latest data
   0 1 * * * cd /Users/ajay/code/icarus && python binance_ingest.py --symbols BTC ETH SOL --interval 1d --days 2
   ```

4. **Build your backtesting algorithms**: Query the database to test trading strategies

## Notes

- Data is automatically compressed after 7 days for storage efficiency
- Continuous aggregates are automatically refreshed by TimescaleDB
- The `ON CONFLICT DO NOTHING` clause prevents duplicate data insertion
- Volume data is fetched separately and may not align perfectly with OHLC timestamps
