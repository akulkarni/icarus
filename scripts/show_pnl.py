#!/usr/bin/env python3
"""
Show Profit & Loss Summary

Displays current P&L, positions, and trading activity.
"""
import asyncio
import asyncpg
import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_config


async def show_pnl():
    """Show P&L summary"""
    config = get_config()

    conn = await asyncpg.connect(
        host=config.get('database.host'),
        port=config.get('database.port'),
        database=config.get('database.database'),
        user=config.get('database.user'),
        password=config.get('database.password'),
        ssl='require'
    )

    print("=" * 80)
    print("ICARUS TRADING SYSTEM - P&L SUMMARY")
    print("=" * 80)
    print()

    # Get initial capital from config
    initial_capital = Decimal(str(config.get('trading.initial_capital', 10000)))
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print()

    # Total trades
    total_trades = await conn.fetchval("SELECT COUNT(*) FROM trades")
    print(f"Total Trades: {total_trades}")
    print()

    # Trades by strategy
    print("TRADES BY STRATEGY:")
    print("-" * 80)
    strategy_trades = await conn.fetch("""
        SELECT
            strategy_name,
            COUNT(*) as num_trades,
            SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
            SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
            SUM(fee) as total_fees
        FROM trades
        GROUP BY strategy_name
        ORDER BY strategy_name
    """)

    for row in strategy_trades:
        print(f"  {row['strategy_name']:15} | Trades: {row['num_trades']:3} | "
              f"Buys: {row['buys']:3} | Sells: {row['sells']:3} | "
              f"Fees: ${float(row['total_fees']):,.2f}")
    print()

    # Current positions
    print("CURRENT POSITIONS:")
    print("-" * 80)
    positions = await conn.fetch("""
        SELECT
            strategy_name,
            symbol,
            quantity,
            entry_price,
            current_price,
            unrealized_pnl
        FROM positions
        WHERE quantity > 0
        ORDER BY strategy_name, symbol
    """)

    if positions:
        for pos in positions:
            pnl = float(pos['unrealized_pnl']) if pos['unrealized_pnl'] else 0
            pnl_pct = (pnl / (float(pos['quantity']) * float(pos['entry_price'])) * 100) if pos['entry_price'] else 0
            print(f"  {pos['strategy_name']:15} | {pos['symbol']:10} | "
                  f"Qty: {float(pos['quantity']):.8f} | "
                  f"Entry: ${float(pos['entry_price']):,.2f} | "
                  f"Current: ${float(pos['current_price']) if pos['current_price'] else 0:,.2f} | "
                  f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
    else:
        print("  No open positions")
    print()

    # Calculate realized P&L from closed trades
    print("REALIZED P&L (from completed buy/sell pairs):")
    print("-" * 80)

    # Get cash flow per strategy
    cash_flows = await conn.fetch("""
        SELECT
            strategy_name,
            SUM(CASE
                WHEN side = 'buy' THEN -(value + fee)
                WHEN side = 'sell' THEN (value - fee)
            END) as net_cash_flow
        FROM trades
        GROUP BY strategy_name
        ORDER BY strategy_name
    """)

    total_realized_pnl = Decimal('0')
    for row in cash_flows:
        cash_flow = Decimal(str(row['net_cash_flow']))
        total_realized_pnl += cash_flow
        print(f"  {row['strategy_name']:15} | Net Cash Flow: ${float(cash_flow):+,.2f}")

    print()
    print(f"  Total Realized P&L: ${float(total_realized_pnl):+,.2f}")
    print()

    # Recent trades
    print("RECENT TRADES (last 10):")
    print("-" * 80)
    recent = await conn.fetch("""
        SELECT
            time,
            strategy_name,
            side,
            quantity,
            price,
            value,
            fee
        FROM trades
        ORDER BY time DESC
        LIMIT 10
    """)

    for trade in recent:
        print(f"  {trade['time'].strftime('%Y-%m-%d %H:%M:%S')} | "
              f"{trade['strategy_name']:10} | "
              f"{trade['side'].upper():4} | "
              f"{float(trade['quantity']):.8f} @ ${float(trade['price']):,.2f} | "
              f"Value: ${float(trade['value']):,.2f} | "
              f"Fee: ${float(trade['fee']):,.2f}")

    print()
    print("=" * 80)

    await conn.close()


if __name__ == '__main__':
    asyncio.run(show_pnl())
