#!/usr/bin/env python3
"""
Binance Crypto Price Data Ingestion Script for TimescaleDB

This script fetches historical cryptocurrency OHLCV data from Binance's public API
and ingests it into a TimescaleDB database.

Binance API is free and doesn't require an API key for public market data.
Rate limits: 1200 requests per minute (weight-based)
Historical data: Available from when the symbol was listed (years of data)

Usage:
    # Fetch 1 year of 1-hour data
    python binance_ingest.py --symbols BTCUSDT ETHUSDT --interval 1h --days 365

    # Fetch 30 days of 1-minute data
    python binance_ingest.py --symbols BTCUSDT ETHUSDT --interval 1m --days 30

    # Fetch 5 years of daily data
    python binance_ingest.py --symbols BTCUSDT ETHUSDT SOLUSDT --interval 1d --days 1825
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
import psycopg2
from psycopg2.extras import execute_batch


# Database connection parameters
DB_CONFIG = {
    'host': 'vqmau49y7s.ye4xypn0ge.tsdb.cloud.timescale.com',
    'port': 34170,
    'user': 'tsdbadmin',
    'password': 'SecurePass123!@#',
    'database': 'tsdb'
}

# Binance API base URL
# Use Binance US for US-based users (no geo-restrictions)
BINANCE_API_BASE = "https://api.binance.us"

# Binance interval mapping
BINANCE_INTERVALS = {
    '1m': '1 minute',
    '3m': '3 minutes',
    '5m': '5 minutes',
    '15m': '15 minutes',
    '30m': '30 minutes',
    '1h': '1 hour',
    '2h': '2 hours',
    '4h': '4 hours',
    '6h': '6 hours',
    '8h': '8 hours',
    '12h': '12 hours',
    '1d': '1 day',
    '3d': '3 days',
    '1w': '1 week',
    '1M': '1 month'
}

# Common symbol mappings (Binance uses BTCUSDT format)
SYMBOL_MAPPINGS = {
    'BTC': 'BTCUSDT',
    'ETH': 'ETHUSDT',
    'SOL': 'SOLUSDT',
    'ADA': 'ADAUSDT',
    'DOT': 'DOTUSDT',
    'MATIC': 'MATICUSDT',
    'LINK': 'LINKUSDT',
    'UNI': 'UNIUSDT',
    'AVAX': 'AVAXUSDT',
    'ATOM': 'ATOMUSDT',
}


def normalize_symbol(symbol: str) -> str:
    """Convert symbol to Binance format if needed."""
    symbol_upper = symbol.upper()
    if symbol_upper in SYMBOL_MAPPINGS:
        return SYMBOL_MAPPINGS[symbol_upper]
    return symbol_upper


def extract_base_symbol(binance_symbol: str) -> str:
    """Extract base symbol from Binance format (BTCUSDT -> BTC)."""
    # Common quote currencies
    for quote in ['USDT', 'BUSD', 'USD', 'USDC']:
        if binance_symbol.endswith(quote):
            return binance_symbol[:-len(quote)]
    return binance_symbol


def fetch_klines(symbol: str, interval: str, start_time: int, end_time: int, limit: int = 1000) -> List[List]:
    """
    Fetch candlestick/kline data from Binance API.

    Args:
        symbol: Binance trading pair (e.g., 'BTCUSDT')
        interval: Kline interval (e.g., '1m', '1h', '1d')
        start_time: Start time in milliseconds
        end_time: End time in milliseconds
        limit: Max number of results (default 1000, max 1000)

    Returns:
        List of kline data arrays: [open_time, open, high, low, close, volume, close_time, ...]
    """
    url = f"{BINANCE_API_BASE}/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': limit
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error fetching data: {e}")
        return []


def fetch_all_historical_data(symbol: str, interval: str, days: int) -> List[List]:
    """
    Fetch all historical data by making multiple API calls if necessary.

    Binance API returns max 1000 records per call, so we need to paginate.

    Args:
        symbol: Binance trading pair
        interval: Kline interval
        days: Number of days of historical data

    Returns:
        Complete list of kline data
    """
    print(f"Fetching {days} days of {interval} data for {symbol}...")

    # Calculate time range
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    all_data = []
    current_start = start_time
    batch_count = 0

    while current_start < end_time:
        batch_count += 1
        data = fetch_klines(symbol, interval, current_start, end_time, limit=1000)

        if not data:
            break

        all_data.extend(data)
        print(f"  Batch {batch_count}: Fetched {len(data)} candles")

        # Update start time for next batch (use close time of last candle + 1ms)
        if len(data) == 1000:  # More data might be available
            current_start = data[-1][6] + 1  # close_time + 1
            time.sleep(0.1)  # Rate limiting - be nice to Binance
        else:
            break  # No more data available

    print(f"  ✓ Total: {len(all_data)} candles fetched")
    return all_data


def insert_kline_data(conn, symbol: str, interval: str, kline_data: List[List]):
    """
    Insert kline/candlestick data into the crypto_prices table.

    Binance kline format:
    [
      open_time,     # 0
      open,          # 1
      high,          # 2
      low,           # 3
      close,         # 4
      volume,        # 5
      close_time,    # 6
      quote_volume,  # 7
      num_trades,    # 8
      taker_buy_base_volume,   # 9
      taker_buy_quote_volume,  # 10
      unused         # 11
    ]

    Args:
        conn: Database connection
        symbol: Binance trading pair (e.g., 'BTCUSDT')
        interval: Kline interval
        kline_data: List of kline arrays from Binance API
    """
    if not kline_data:
        print(f"No data to insert for {symbol}")
        return

    insert_query = """
        INSERT INTO crypto_prices (time, symbol, exchange, open, high, low, close, volume, quote_volume, num_trades)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
    """

    # Extract base symbol for storage (BTCUSDT -> BTC)
    base_symbol = extract_base_symbol(symbol)

    # Prepare data for batch insert
    rows = []
    for kline in kline_data:
        open_time = kline[0]
        open_price = float(kline[1])
        high_price = float(kline[2])
        low_price = float(kline[3])
        close_price = float(kline[4])
        volume = float(kline[5])
        quote_volume = float(kline[7])
        num_trades = int(kline[8])

        # Convert timestamp to datetime
        dt = datetime.fromtimestamp(open_time / 1000)

        rows.append((
            dt,                      # time
            base_symbol,             # symbol (BTC, ETH, etc.)
            'binance',              # exchange
            open_price,             # open
            high_price,             # high
            low_price,              # low
            close_price,            # close
            volume,                 # volume (in base currency)
            quote_volume,           # quote_volume (in USD/USDT)
            num_trades              # num_trades
        ))

    # Batch insert
    with conn.cursor() as cur:
        execute_batch(cur, insert_query, rows, page_size=1000)
        conn.commit()
        print(f"  ✓ Inserted {len(rows)} rows for {base_symbol}")


def ingest_binance_data(symbols: List[str], interval: str, days: int):
    """
    Main function to ingest Binance data for multiple symbols.

    Args:
        symbols: List of trading pairs (e.g., ['BTCUSDT', 'ETHUSDT'] or ['BTC', 'ETH'])
        interval: Kline interval (e.g., '1m', '1h', '1d')
        days: Number of days of historical data to fetch
    """
    print(f"\n{'='*70}")
    print(f"Starting Binance data ingestion")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Interval: {interval} ({BINANCE_INTERVALS.get(interval, 'unknown')})")
    print(f"Days: {days}")
    print(f"{'='*70}\n")

    # Validate interval
    if interval not in BINANCE_INTERVALS:
        print(f"✗ Invalid interval: {interval}")
        print(f"Valid intervals: {', '.join(BINANCE_INTERVALS.keys())}")
        sys.exit(1)

    # Connect to database
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Connected to TimescaleDB\n")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)

    try:
        total_inserted = 0

        for symbol in symbols:
            # Normalize symbol to Binance format
            binance_symbol = normalize_symbol(symbol)

            # Fetch all historical data
            kline_data = fetch_all_historical_data(binance_symbol, interval, days)

            # Insert into database
            if kline_data:
                insert_kline_data(conn, binance_symbol, interval, kline_data)
                total_inserted += len(kline_data)

            print()  # Empty line between symbols

        print(f"{'='*70}")
        print(f"✓ Ingestion complete!")
        print(f"Total candles inserted: {total_inserted}")
        print(f"{'='*70}\n")

    except Exception as e:
        print(f"\n✗ Error during ingestion: {e}")
        raise
    finally:
        conn.close()
        print("Database connection closed")


def main():
    parser = argparse.ArgumentParser(
        description='Ingest crypto price data from Binance into TimescaleDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch 1 year of daily data for BTC and ETH
  python binance_ingest.py --symbols BTC ETH --interval 1d --days 365

  # Fetch 30 days of 1-hour data
  python binance_ingest.py --symbols BTCUSDT ETHUSDT SOLUSDT --interval 1h --days 30

  # Fetch 7 days of 1-minute data (high resolution for recent backtesting)
  python binance_ingest.py --symbols BTC ETH --interval 1m --days 7

  # Fetch 5 years of daily data
  python binance_ingest.py --symbols BTC ETH SOL ADA DOT --interval 1d --days 1825

Supported intervals:
  1m, 3m, 5m, 15m, 30m (minutes)
  1h, 2h, 4h, 6h, 8h, 12h (hours)
  1d, 3d (days)
  1w (week)
  1M (month)

Supported symbols: BTC, ETH, SOL, ADA, DOT, MATIC, LINK, UNI, AVAX, ATOM
Or use Binance format directly: BTCUSDT, ETHUSDT, etc.
        """
    )

    parser.add_argument(
        '--symbols',
        nargs='+',
        required=True,
        help='Trading pairs to fetch (e.g., BTC ETH or BTCUSDT ETHUSDT)'
    )

    parser.add_argument(
        '--interval',
        type=str,
        default='1h',
        help='Kline interval (default: 1h). Options: 1m, 5m, 15m, 1h, 4h, 1d, etc.'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days of historical data (default: 30)'
    )

    args = parser.parse_args()

    # Validate days parameter
    if args.days < 1:
        print("Error: --days must be at least 1")
        sys.exit(1)

    # Run ingestion
    ingest_binance_data(args.symbols, args.interval, args.days)


if __name__ == '__main__':
    main()
