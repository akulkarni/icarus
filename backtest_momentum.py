#!/usr/bin/env python3
"""
Momentum Strategy Backtest
- Uses 20-period and 50-period moving averages
- Buy when 20MA crosses above 50MA
- Sell when 20MA crosses below 50MA
- Tests on ETH hourly data for last 90 days
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor


def calculate_ma(prices, period):
    """Calculate simple moving average"""
    return pd.Series(prices).rolling(window=period).mean().values


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


def backtest_momentum(df, initial_capital=10000, transaction_cost=0.001):
    """
    Backtest momentum strategy
    - Buy when 20MA crosses above 50MA
    - Sell when 20MA crosses below 50MA
    """
    # Calculate moving averages
    df['ma20'] = calculate_ma(df['close'].values, 20)
    df['ma50'] = calculate_ma(df['close'].values, 50)

    # Initialize tracking variables
    cash = initial_capital
    position = 0  # Number of units held
    portfolio_value = initial_capital
    previous_signal = None

    for i in range(50, len(df)):  # Start after MA warmup period
        current_price = df.iloc[i]['close']
        ma20 = df.iloc[i]['ma20']
        ma50 = df.iloc[i]['ma50']

        # Determine current signal
        if ma20 > ma50:
            current_signal = 'buy'
        else:
            current_signal = 'sell'

        # Buy signal: 20MA crosses above 50MA
        if current_signal == 'buy' and previous_signal == 'sell' and position == 0 and cash > 0:
            # Buy with all available cash
            cost = cash * transaction_cost
            position = (cash - cost) / current_price
            cash = 0

        # Sell signal: 20MA crosses below 50MA
        elif current_signal == 'sell' and previous_signal == 'buy' and position > 0:
            # Sell entire position
            proceeds = position * current_price
            cost = proceeds * transaction_cost
            cash = proceeds - cost
            position = 0

        previous_signal = current_signal

    # Calculate final portfolio value
    if position > 0:
        final_price = df.iloc[-1]['close']
        cash = position * final_price * (1 - transaction_cost)

    portfolio_value = cash
    roi = ((portfolio_value - initial_capital) / initial_capital) * 100

    return roi


def main():
    parser = argparse.ArgumentParser(description='Momentum Strategy Backtest')
    parser.add_argument('--db-host', required=True, help='Database host')
    args = parser.parse_args()

    # Fetch data
    df = fetch_data(args.db_host, symbol='ETH', days=90)

    # Run backtest
    roi = backtest_momentum(df)

    # Print result
    print(f"ROI: {roi:.2f}%")


if __name__ == '__main__':
    main()
