#!/usr/bin/env python3
"""
Trading Safety Validation Script

Validates configuration before enabling real trading.
"""
import sys
import yaml
import os
from pathlib import Path


def load_config():
    """Load configuration"""
    config_path = Path(__file__).parent.parent / 'config' / 'app.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    def expand_env(value):
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            parts = value[2:-1].split(':')
            var_name = parts[0]
            default_value = parts[1] if len(parts) > 1 else ''
            return os.getenv(var_name, default_value)
        return value

    # Recursively expand env vars
    def process_dict(d):
        for k, v in d.items():
            if isinstance(v, dict):
                process_dict(v)
            else:
                d[k] = expand_env(v)

    process_dict(config)
    return config


def validate_safety(config):
    """Run safety checks"""
    errors = []
    warnings = []

    # Check 1: Trading mode
    mode = config['trading']['mode']
    if mode == 'real':
        warnings.append("⚠️  Trading mode is set to REAL")
    else:
        print("✅ Trading mode: paper")

    # Check 2: Binance testnet
    if mode == 'real':
        binance_config = config.get('binance', {})
        testnet = binance_config.get('testnet', True)
        if not testnet:
            warnings.append("⚠️  Binance testnet is DISABLED - using LIVE trading!")
        else:
            print("✅ Binance testnet enabled")

    # Check 3: API credentials
    if mode == 'real':
        binance_config = config.get('binance', {})
        api_key = binance_config.get('api_key', '')
        api_secret = binance_config.get('api_secret', '')

        if not api_key or not api_secret:
            errors.append("❌ Binance API credentials not configured")
        else:
            print(f"✅ API key configured: {api_key[:10]}...")

    # Check 4: Risk limits
    risk = config['risk']
    if risk['max_daily_loss_pct'] > 10:
        warnings.append(f"⚠️  Daily loss limit high: {risk['max_daily_loss_pct']}%")
    else:
        print(f"✅ Daily loss limit: {risk['max_daily_loss_pct']}%")

    if risk['max_position_size_pct'] > 30:
        warnings.append(f"⚠️  Position size limit high: {risk['max_position_size_pct']}%")
    else:
        print(f"✅ Position size limit: {risk['max_position_size_pct']}%")

    # Check 5: Initial capital (should be reasonable for testing)
    capital = config['trading']['initial_capital']
    if mode == 'real' and capital > 10000:
        warnings.append(f"⚠️  Initial capital high for testing: ${capital}")
    else:
        print(f"✅ Initial capital: ${capital}")

    # Check 6: Slippage enabled for paper mode
    if mode == 'paper':
        slippage_enabled = config.get('slippage', {}).get('enabled', False)
        if slippage_enabled:
            print(f"✅ Slippage simulation enabled: {config['slippage']['percentage']}%")
        else:
            warnings.append("⚠️  Slippage simulation disabled for paper trading")

    # Print results
    print("\n" + "="*60)

    if errors:
        print("ERRORS FOUND:")
        for error in errors:
            print(f"  {error}")
        print("\n❌ SAFETY VALIDATION FAILED")
        return False

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n⚠️  PROCEED WITH CAUTION")

    print("="*60)

    if mode == 'real':
        print("\n🚨 REAL TRADING MODE ENABLED 🚨")
        print("Have you:")
        print("  1. Tested thoroughly on testnet?")
        print("  2. Verified API key permissions (spot only, no withdrawals)?")
        print("  3. Set conservative position sizes?")
        print("  4. Ready to monitor actively?")
        print("\nType 'I UNDERSTAND THE RISKS' to continue: ")

        confirmation = input()
        if confirmation != "I UNDERSTAND THE RISKS":
            print("\n❌ Confirmation not received. Exiting.")
            return False

    return True


if __name__ == '__main__':
    try:
        config = load_config()
        if validate_safety(config):
            print("\n✅ Safety validation passed")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        sys.exit(1)
