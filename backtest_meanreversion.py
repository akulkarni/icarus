#!/usr/bin/env python3
"""
Mean Reversion Strategy Backtest
- Uses RSI indicator (14-period)
- Buy when RSI < 30 (oversold)
- Sell when RSI > 70 (overbought)
- Tests on BTC hourly data for last 90 days
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor


def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period

    if down == 0:
        return np.full(len(prices), 100.0)

    rs = up / down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)

    for i in range(period, len(prices)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period

        if down == 0:
            rsi[i] = 100.
        else:
            rs = up / down
            rsi[i] = 100. - 100. / (1. + rs)

    return rsi


def fetch_data(db_host, symbol='BTC', days=90):
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


def backtest_mean_reversion(df, initial_capital=10000, transaction_cost=0.001):
    """
    Backtest mean reversion strategy
    - Buy when RSI < 30
    - Sell when RSI > 70
    """
    # Calculate RSI
    df['rsi'] = calculate_rsi(df['close'].values, period=14)

    # Initialize tracking variables
    cash = initial_capital
    position = 0  # Number of units held
    portfolio_value = initial_capital

    for i in range(14, len(df)):  # Start after RSI warmup period
        current_price = df.iloc[i]['close']
        rsi = df.iloc[i]['rsi']

        # Buy signal: RSI < 30 and no position
        if rsi < 30 and position == 0 and cash > 0:
            # Buy with all available cash
            cost = cash * transaction_cost
            position = (cash - cost) / current_price
            cash = 0

        # Sell signal: RSI > 70 and have position
        elif rsi > 70 and position > 0:
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
    parser = argparse.ArgumentParser(description='Mean Reversion Strategy Backtest')
    parser.add_argument('--db-host', required=True, help='Database host')
    args = parser.parse_args()

    # Fetch data
    df = fetch_data(args.db_host, symbol='BTC', days=90)

    # Run backtest
    roi = backtest_mean_reversion(df)

    # Print result
    print(f"ROI: {roi:.2f}%")


if __name__ == '__main__':
    main()
