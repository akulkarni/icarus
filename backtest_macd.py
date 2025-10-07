#!/usr/bin/env python3
"""
MACD Strategy Backtest
- Uses MACD (12, 26, 9) indicator
- Buy when MACD crosses above signal line
- Sell when MACD crosses below signal line
- Tests on ETH hourly data for last 90 days
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2


def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().values


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD and signal line"""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = pd.Series(macd_line).ewm(span=signal, adjust=False).mean().values

    return macd_line, signal_line


def fetch_data(db_host, symbol='ETH', days=90):
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


def backtest_macd(df, initial_capital=10000, transaction_cost=0.001):
    """
    Backtest MACD strategy
    - Buy when MACD crosses above signal line (bullish crossover)
    - Sell when MACD crosses below signal line (bearish crossover)
    """
    # Calculate MACD
    macd_line, signal_line = calculate_macd(df['close'].values)
    df['macd'] = macd_line
    df['signal'] = signal_line

    # Initialize tracking variables
    cash = initial_capital
    position = 0  # Number of units held
    portfolio_value = initial_capital
    prev_macd = None
    prev_signal = None

    for i in range(26, len(df)):  # Start after MACD warmup period (slow EMA = 26)
        current_price = df.iloc[i]['close']
        macd = df.iloc[i]['macd']
        signal = df.iloc[i]['signal']

        if prev_macd is not None and not np.isnan(macd) and not np.isnan(signal):
            # Buy signal: MACD crosses above signal line
            if prev_macd <= prev_signal and macd > signal and position == 0:
                units_to_buy = cash / (current_price * (1 + transaction_cost))
                position = units_to_buy
                cash = 0
                # print(f"BUY at {current_price:.2f} (MACD: {macd:.2f}, Signal: {signal:.2f})")

            # Sell signal: MACD crosses below signal line
            elif prev_macd >= prev_signal and macd < signal and position > 0:
                cash = position * current_price * (1 - transaction_cost)
                position = 0
                # print(f"SELL at {current_price:.2f} (MACD: {macd:.2f}, Signal: {signal:.2f})")

        prev_macd = macd
        prev_signal = signal

    # Final portfolio value
    if position > 0:
        cash = position * df.iloc[-1]['close'] * (1 - transaction_cost)

    portfolio_value = cash
    roi = ((portfolio_value - initial_capital) / initial_capital) * 100

    return roi


def main():
    parser = argparse.ArgumentParser(description='Backtest MACD strategy')
    parser.add_argument('--db-host', required=True, help='Database host')
    args = parser.parse_args()

    # Fetch data
    df = fetch_data(args.db_host, symbol='ETH', days=90)

    # Run backtest
    roi = backtest_macd(df)

    # Print result
    print(f"ROI: {roi:.2f}%")


if __name__ == '__main__':
    main()
