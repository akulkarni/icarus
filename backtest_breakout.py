#!/usr/bin/env python3
"""
Breakout Strategy Backtest
- Tracks 20-period high/low bands
- Buy on breakout above high with volume > 1.5x average
- Sell on breakdown below low
- Tests on SOL hourly data for last 90 days
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor


def calculate_rolling_high_low(df, period=20):
    """Calculate rolling high and low bands"""
    df['high_band'] = df['high'].rolling(window=period).max()
    df['low_band'] = df['low'].rolling(window=period).min()
    return df


def calculate_volume_avg(volumes, period=20):
    """Calculate rolling average volume"""
    return pd.Series(volumes).rolling(window=period).mean().values


def fetch_data(db_host, symbol='SOL', days=90):
    """Fetch hourly OHLCV data from database"""
    # Extract host and port from connection string
    if ':' in db_host:
        host_part, port_part = db_host.rsplit(':', 1)
        port = int(port_part)
    else:
        host_part = db_host
        port = 34170

    conn = psycopg2.connect(
        host=host_part,
        port=port,
        database="tsdb",
        user="tsdbadmin",
        password="SecurePass123!@#"
    )

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    query = """
        SELECT time, open, high, low, close, volume
        FROM crypto_prices
        WHERE symbol = %s
        AND time >= %s
        AND time <= %s
        ORDER BY time ASC
    """

    df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
    conn.close()

    return df


def backtest_breakout(df, initial_capital=10000, transaction_cost=0.001):
    """
    Backtest breakout strategy
    - Buy on breakout above 20-period high with volume > 1.5x average
    - Sell on breakdown below 20-period low
    """
    # Calculate indicators
    df = calculate_rolling_high_low(df, period=20)
    df['volume_avg'] = calculate_volume_avg(df['volume'].values, period=20)

    # Initialize tracking variables
    cash = initial_capital
    position = 0  # Number of units held
    portfolio_value = initial_capital

    for i in range(20, len(df)):  # Start after warmup period
        current_price = df.iloc[i]['close']
        current_high = df.iloc[i]['high']
        current_low = df.iloc[i]['low']
        current_volume = df.iloc[i]['volume']

        # Get previous period's bands (to detect breakout)
        prev_high_band = df.iloc[i-1]['high_band']
        prev_low_band = df.iloc[i-1]['low_band']
        volume_avg = df.iloc[i]['volume_avg']

        # Buy signal: breakout above high band with volume > 1.5x average
        if (current_high > prev_high_band and
            current_volume > 1.5 * volume_avg and
            position == 0 and
            cash > 0):
            # Buy with all available cash
            cost = cash * transaction_cost
            position = (cash - cost) / current_price
            cash = 0

        # Sell signal: breakdown below low band
        elif current_low < prev_low_band and position > 0:
            # Sell entire position
            proceeds = position * current_price
            cost = proceeds * transaction_cost
            cash = proceeds - cost
            position = 0

    # Calculate final portfolio value
    if position > 0:
        final_price = df.iloc[-1]['close']
        cash = position * final_price * (1 - transaction_cost)

    portfolio_value = cash
    roi = ((portfolio_value - initial_capital) / initial_capital) * 100

    return roi


def main():
    parser = argparse.ArgumentParser(description='Breakout Strategy Backtest')
    parser.add_argument('--db-host', required=True, help='Database host')
    args = parser.parse_args()

    # Fetch data
    df = fetch_data(args.db_host, symbol='SOL', days=90)

    # Run backtest
    roi = backtest_breakout(df)

    # Print result
    print(f"ROI: {roi:.2f}%")


if __name__ == '__main__':
    main()
