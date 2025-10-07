#!/usr/bin/env python3
"""
Bollinger Bands Strategy Backtest
- Uses 20-period moving average with 2 standard deviations
- Buy when price touches lower band
- Sell when price touches upper band
- Tests on ETH hourly data for last 90 days
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2


def calculate_bollinger_bands(prices, period=20, num_std=2):
    """Calculate Bollinger Bands"""
    sma = pd.Series(prices).rolling(window=period).mean().values
    std = pd.Series(prices).rolling(window=period).std().values

    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)

    return sma, upper_band, lower_band


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


def backtest_bollinger_bands(df, initial_capital=10000, transaction_cost=0.001):
    """
    Backtest Bollinger Bands strategy
    - Buy when price touches or goes below lower band
    - Sell when price touches or goes above upper band
    """
    # Calculate Bollinger Bands
    sma, upper_band, lower_band = calculate_bollinger_bands(df['close'].values, period=20, num_std=2)
    df['sma'] = sma
    df['upper_band'] = upper_band
    df['lower_band'] = lower_band

    # Initialize tracking variables
    cash = initial_capital
    position = 0  # Number of units held
    portfolio_value = initial_capital

    for i in range(20, len(df)):  # Start after Bollinger warmup period
        current_price = df.iloc[i]['close']
        lower = df.iloc[i]['lower_band']
        upper = df.iloc[i]['upper_band']

        # Buy signal: Price at or below lower band and no position
        if current_price <= lower and position == 0 and not np.isnan(lower):
            units_to_buy = cash / (current_price * (1 + transaction_cost))
            position = units_to_buy
            cash = 0
            # print(f"BUY at {current_price:.2f} (lower band: {lower:.2f})")

        # Sell signal: Price at or above upper band and have position
        elif current_price >= upper and position > 0 and not np.isnan(upper):
            cash = position * current_price * (1 - transaction_cost)
            position = 0
            # print(f"SELL at {current_price:.2f} (upper band: {upper:.2f})")

    # Final portfolio value
    if position > 0:
        cash = position * df.iloc[-1]['close'] * (1 - transaction_cost)

    portfolio_value = cash
    roi = ((portfolio_value - initial_capital) / initial_capital) * 100

    return roi


def main():
    parser = argparse.ArgumentParser(description='Backtest Bollinger Bands strategy')
    parser.add_argument('--db-host', required=True, help='Database host')
    args = parser.parse_args()

    # Fetch data
    df = fetch_data(args.db_host, symbol='ETH', days=90)

    # Run backtest
    roi = backtest_bollinger_bands(df)

    # Print result
    print(f"ROI: {roi:.2f}%")


if __name__ == '__main__':
    main()
