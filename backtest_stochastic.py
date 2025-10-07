#!/usr/bin/env python3
"""
Stochastic Oscillator Strategy Backtest
- Uses Stochastic Oscillator (14, 3, 3)
- Buy when %K crosses above %D below 20 (oversold)
- Sell when %K crosses below %D above 80 (overbought)
- Tests on ETH hourly data for last 90 days
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2


def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator %K and %D"""
    # Calculate %K
    lowest_low = pd.Series(low).rolling(window=k_period).min().values
    highest_high = pd.Series(high).rolling(window=k_period).max().values

    k_values = np.zeros(len(close))
    for i in range(len(close)):
        if not np.isnan(lowest_low[i]) and not np.isnan(highest_high[i]):
            denom = highest_high[i] - lowest_low[i]
            if denom != 0:
                k_values[i] = ((close[i] - lowest_low[i]) / denom) * 100
            else:
                k_values[i] = 50  # Default to middle

    # Calculate %D (simple moving average of %K)
    d_values = pd.Series(k_values).rolling(window=d_period).mean().values

    return k_values, d_values


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


def backtest_stochastic(df, initial_capital=10000, transaction_cost=0.001):
    """
    Backtest Stochastic Oscillator strategy
    - Buy when %K crosses above %D in oversold zone (below 20)
    - Sell when %K crosses below %D in overbought zone (above 80)
    """
    # Calculate Stochastic
    k_values, d_values = calculate_stochastic(
        df['high'].values,
        df['low'].values,
        df['close'].values
    )
    df['%K'] = k_values
    df['%D'] = d_values

    # Initialize tracking variables
    cash = initial_capital
    position = 0  # Number of units held
    portfolio_value = initial_capital
    prev_k = None
    prev_d = None

    for i in range(17, len(df)):  # Start after warmup period (14 + 3)
        current_price = df.iloc[i]['close']
        k = df.iloc[i]['%K']
        d = df.iloc[i]['%D']

        if prev_k is not None and not np.isnan(k) and not np.isnan(d):
            # Buy signal: %K crosses above %D in oversold zone
            if prev_k <= prev_d and k > d and k < 20 and position == 0:
                units_to_buy = cash / (current_price * (1 + transaction_cost))
                position = units_to_buy
                cash = 0
                # print(f"BUY at {current_price:.2f} (%K: {k:.2f}, %D: {d:.2f})")

            # Sell signal: %K crosses below %D in overbought zone
            elif prev_k >= prev_d and k < d and k > 80 and position > 0:
                cash = position * current_price * (1 - transaction_cost)
                position = 0
                # print(f"SELL at {current_price:.2f} (%K: {k:.2f}, %D: {d:.2f})")

        prev_k = k
        prev_d = d

    # Final portfolio value
    if position > 0:
        cash = position * df.iloc[-1]['close'] * (1 - transaction_cost)

    portfolio_value = cash
    roi = ((portfolio_value - initial_capital) / initial_capital) * 100

    return roi


def main():
    parser = argparse.ArgumentParser(description='Backtest Stochastic Oscillator strategy')
    parser.add_argument('--db-host', required=True, help='Database host')
    args = parser.parse_args()

    # Fetch data
    df = fetch_data(args.db_host, symbol='ETH', days=90)

    # Run backtest
    roi = backtest_stochastic(df)

    # Print result
    print(f"ROI: {roi:.2f}%")


if __name__ == '__main__':
    main()
