#!/usr/bin/env python3
"""
Crypto Price Data Ingestion Script for TimescaleDB

This script fetches historical cryptocurrency OHLCV data from CoinGecko's free API
and ingests it into a TimescaleDB database.

CoinGecko API is free and doesn't require an API key for basic usage.
Rate limits: 10-50 calls/minute depending on endpoint.

Usage:
    python crypto_ingest.py --symbols BTC ETH SOL --days 365
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
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

# CoinGecko API base URL (free, no API key required)
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"

# Mapping of common symbols to CoinGecko IDs
SYMBOL_TO_ID = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'SOL': 'solana',
    'ADA': 'cardano',
    'DOT': 'polkadot',
    'MATIC': 'matic-network',
    'LINK': 'chainlink',
    'UNI': 'uniswap',
    'AVAX': 'avalanche-2',
    'ATOM': 'cosmos',
}


def get_coingecko_id(symbol: str) -> str:
    """Convert a crypto symbol to CoinGecko ID."""
    return SYMBOL_TO_ID.get(symbol.upper(), symbol.lower())


def fetch_ohlcv_data(coin_id: str, days: int = 30, interval: str = 'daily') -> List[List]:
    """
    Fetch OHLCV data from CoinGecko API.

    Args:
        coin_id: CoinGecko coin ID (e.g., 'bitcoin')
        days: Number of days of historical data (max 365 for free tier)
        interval: 'daily' or leave default for automatic selection

    Returns:
        List of [timestamp_ms, open, high, low, close] data points
    """
    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/ohlc"
    params = {
        'vs_currency': 'usd',
        'days': days
    }

    print(f"Fetching {days} days of data for {coin_id}...")

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            print(f"  ✓ Received {len(data)} data points")
            return data
        else:
            print(f"  ✗ No data received for {coin_id}")
            return []

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error fetching data for {coin_id}: {e}")
        return []


def fetch_volume_data(coin_id: str, days: int = 30) -> Dict[int, float]:
    """
    Fetch volume data from CoinGecko market chart API.

    Returns:
        Dictionary mapping timestamp (day level) to volume
    """
    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {
        'vs_currency': 'usd',
        'days': days,
        'interval': 'daily' if days > 1 else 'hourly'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Extract volume data and create a mapping
        volume_map = {}
        if 'total_volumes' in data:
            for timestamp_ms, volume in data['total_volumes']:
                # Round to day level for matching
                day_timestamp = (timestamp_ms // 86400000) * 86400000
                volume_map[day_timestamp] = volume

        return volume_map

    except requests.exceptions.RequestException as e:
        print(f"  Warning: Could not fetch volume data: {e}")
        return {}


def insert_ohlcv_data(conn, symbol: str, ohlcv_data: List[List], volume_map: Dict[int, float]):
    """
    Insert OHLCV data into the crypto_prices table.

    Args:
        conn: Database connection
        symbol: Crypto symbol (e.g., 'BTC')
        ohlcv_data: List of [timestamp_ms, open, high, low, close] arrays
        volume_map: Dictionary mapping timestamps to volumes
    """
    if not ohlcv_data:
        print(f"No data to insert for {symbol}")
        return

    insert_query = """
        INSERT INTO crypto_prices (time, symbol, exchange, open, high, low, close, volume, quote_volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
    """

    # Prepare data for batch insert
    rows = []
    for record in ohlcv_data:
        timestamp_ms = record[0]
        open_price = record[1]
        high_price = record[2]
        low_price = record[3]
        close_price = record[4]

        # Convert timestamp to datetime
        dt = datetime.fromtimestamp(timestamp_ms / 1000)

        # Get volume from the volume map
        day_timestamp = (timestamp_ms // 86400000) * 86400000
        volume = volume_map.get(day_timestamp, 0.0)

        rows.append((
            dt,                      # time
            symbol.upper(),          # symbol
            'coingecko',            # exchange (source)
            open_price,             # open
            high_price,             # high
            low_price,              # low
            close_price,            # close
            volume,                 # volume
            volume * close_price    # quote_volume (approximate)
        ))

    # Batch insert
    with conn.cursor() as cur:
        execute_batch(cur, insert_query, rows, page_size=1000)
        conn.commit()
        print(f"  ✓ Inserted {len(rows)} rows for {symbol}")


def ingest_crypto_data(symbols: List[str], days: int = 30):
    """
    Main function to ingest crypto data for multiple symbols.

    Args:
        symbols: List of crypto symbols (e.g., ['BTC', 'ETH'])
        days: Number of days of historical data to fetch
    """
    print(f"\n{'='*60}")
    print(f"Starting crypto data ingestion")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Days: {days}")
    print(f"{'='*60}\n")

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
            coin_id = get_coingecko_id(symbol)

            # Fetch OHLCV data
            ohlcv_data = fetch_ohlcv_data(coin_id, days)

            # Fetch volume data separately
            volume_map = fetch_volume_data(coin_id, days)

            # Insert into database
            if ohlcv_data:
                insert_ohlcv_data(conn, symbol, ohlcv_data, volume_map)
                total_inserted += len(ohlcv_data)

            # Rate limiting - CoinGecko free tier has ~10-50 calls/minute
            # Sleep for 2 seconds between symbols to be safe
            if symbol != symbols[-1]:  # Don't sleep after last symbol
                time.sleep(2)

        print(f"\n{'='*60}")
        print(f"✓ Ingestion complete!")
        print(f"Total data points inserted: {total_inserted}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n✗ Error during ingestion: {e}")
        raise
    finally:
        conn.close()
        print("Database connection closed")


def main():
    parser = argparse.ArgumentParser(
        description='Ingest crypto price data into TimescaleDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch 30 days of BTC data
  python crypto_ingest.py --symbols BTC

  # Fetch 1 year of multiple coins
  python crypto_ingest.py --symbols BTC ETH SOL --days 365

  # Fetch 90 days of many coins
  python crypto_ingest.py --symbols BTC ETH SOL ADA DOT MATIC --days 90

Supported symbols: BTC, ETH, SOL, ADA, DOT, MATIC, LINK, UNI, AVAX, ATOM
        """
    )

    parser.add_argument(
        '--symbols',
        nargs='+',
        required=True,
        help='Crypto symbols to fetch (e.g., BTC ETH SOL)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days of historical data (default: 30, max: 365 for daily data)'
    )

    args = parser.parse_args()

    # Validate days parameter
    if args.days < 1 or args.days > 365:
        print("Error: --days must be between 1 and 365")
        sys.exit(1)

    # Run ingestion
    ingest_crypto_data(args.symbols, args.days)


if __name__ == '__main__':
    main()
