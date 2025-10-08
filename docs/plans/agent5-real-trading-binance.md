# Agent 5: Real Trading Mode with Binance API

**Branch**: `agent5-real-trading-binance`
**Estimated Time**: 2-3 hours
**Dependencies**: None (can start immediately)

---

## Overview

Implement real trading mode that executes orders on Binance exchange. Currently the system only does paper trading. This adds live trading capability with proper safety checks.

**CRITICAL**: This involves real money. Extra care required.

**What you're building**:
- Binance API integration
- Real order execution
- Safety checks and validation
- Slippage simulation for paper mode
- Configuration for testnet/mainnet

**References**:
- `src/agents/execution.py` - Existing paper trading
- Day 3 implementation plan (lines 23-127)

---

## Step 1: Setup & Safety First (20 min)

### 1.1 Create branch
```bash
git checkout -b agent5-real-trading-binance
```

### 1.2 Update dependencies
**File**: `requirements.txt` (verify python-binance is present)

```txt
python-binance>=1.0.19  # Should already be there
```

### 1.3 Add configuration
**File**: `config/app.yaml` (add Binance config)

```yaml
# Trading Configuration
trading:
  mode: paper  # paper or real - DEFAULT TO PAPER
  initial_capital: 10000
  position_size_pct: 20
  position_exit_pct: 50
  symbols:
    - BTCUSDT
    - ETHUSDT

# Binance API Configuration
binance:
  api_key: ${BINANCE_API_KEY:}  # Set via environment variable
  api_secret: ${BINANCE_API_SECRET:}  # Set via environment variable
  testnet: true  # ALWAYS START WITH TESTNET
  testnet_url: "https://testnet.binance.vision"

# Slippage simulation for paper trading
slippage:
  enabled: true
  percentage: 0.1  # 0.1% = 10 basis points
```

**File**: `.env.example` (create if doesn't exist)

```bash
# Binance API credentials
# NEVER commit actual keys to git
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Tiger Cloud
TIGER_HOST=your_tiger_host
TIGER_PORT=5432
TIGER_DATABASE=tsdb
TIGER_USER=tsdbadmin
TIGER_PASSWORD=your_password
TIGER_SERVICE_ID=your_service_id
```

### 1.4 Create safety checklist document
**File**: `docs/REAL_TRADING_SAFETY.md`

```markdown
# Real Trading Safety Checklist

## BEFORE ENABLING REAL TRADING

### 1. Binance Setup
- [ ] Created Binance account
- [ ] Enabled 2FA
- [ ] Created API key
- [ ] **Restricted API key permissions to SPOT TRADING ONLY**
- [ ] **DISABLED withdrawal permissions**
- [ ] Tested on Binance testnet first

### 2. Configuration
- [ ] Set `trading.mode: real` in config
- [ ] Set `binance.testnet: true` for initial testing
- [ ] Verified API keys in environment variables
- [ ] Set conservative position sizes

### 3. Risk Limits
- [ ] Daily loss limit set (default: 5%)
- [ ] Position size limit set (default: 20%)
- [ ] Max exposure limit set (default: 80%)
- [ ] Emergency halt configured

### 4. Testing
- [ ] Tested on testnet extensively
- [ ] Verified all strategies work
- [ ] Tested emergency stop
- [ ] Verified slippage calculations

### 5. Monitoring
- [ ] Dashboard accessible
- [ ] Logs configured
- [ ] Alerts set up (if applicable)
- [ ] Ready to monitor actively

### 6. First Live Trade
- [ ] Start with MINIMUM position size
- [ ] Use only ONE strategy initially
- [ ] Monitor CONSTANTLY for first hour
- [ ] Verify trades appear in Binance UI
- [ ] Check balances match

## EMERGENCY PROCEDURES

### Stop Trading Immediately
```bash
# Option 1: Set halt in database
UPDATE system_state SET emergency_halt = true;

# Option 2: Kill process
pkill -f "python src/main.py"

# Option 3: Cancel all orders via Binance UI
# Log into Binance → Orders → Cancel All
```

### Contact
- Binance Support: support@binance.com
- Emergency contact: [Your contact]

## WARNINGS

⚠️ **YOU CAN LOSE REAL MONEY**
⚠️ **START WITH TESTNET**
⚠️ **START WITH SMALL AMOUNTS**
⚠️ **MONITOR ACTIVELY**
⚠️ **NEVER leave running unattended initially**
```

---

## Step 2: Slippage Simulation for Paper Trading (30 min)

### 2.1 Write tests for slippage
**File**: `tests/test_agents/test_execution_slippage.py`

```python
"""Tests for slippage simulation"""
import pytest
from decimal import Decimal
from src.agents.execution import calculate_slippage_price


def test_buy_slippage():
    """Test slippage increases buy price"""
    market_price = Decimal('100.00')
    slippage_pct = Decimal('0.001')  # 0.1%

    fill_price = calculate_slippage_price(market_price, 'buy', slippage_pct)

    # Buy price should be higher
    assert fill_price > market_price
    assert fill_price == Decimal('100.10')


def test_sell_slippage():
    """Test slippage decreases sell price"""
    market_price = Decimal('100.00')
    slippage_pct = Decimal('0.001')  # 0.1%

    fill_price = calculate_slippage_price(market_price, 'sell', slippage_pct)

    # Sell price should be lower
    assert fill_price < market_price
    assert fill_price == Decimal('99.90')


def test_zero_slippage():
    """Test zero slippage returns market price"""
    market_price = Decimal('100.00')
    slippage_pct = Decimal('0.0')

    for side in ['buy', 'sell']:
        fill_price = calculate_slippage_price(market_price, side, slippage_pct)
        assert fill_price == market_price
```

### 2.2 Implement slippage calculation
**File**: `src/agents/execution.py` (add function)

Read the existing file first to understand structure:

```python
# Add this helper function near the top after imports
def calculate_slippage_price(market_price: Decimal, side: str, slippage_pct: Decimal) -> Decimal:
    """
    Calculate fill price with slippage

    Args:
        market_price: Current market price
        side: 'buy' or 'sell'
        slippage_pct: Slippage as decimal (0.001 = 0.1%)

    Returns:
        Price after slippage
    """
    if side == 'buy':
        # Buying costs more (unfavorable slippage)
        return market_price * (Decimal('1') + slippage_pct)
    else:  # sell
        # Selling gets less (unfavorable slippage)
        return market_price * (Decimal('1') - slippage_pct)
```

### 2.3 Update paper trading to use slippage
**File**: `src/agents/execution.py` (modify `_execute_order_paper`)

Find the `_execute_order_paper` method and update to use slippage:

```python
async def _execute_order_paper(self, order):
    """Execute order in paper trading mode with slippage"""
    # ... existing code ...

    # Get slippage config
    slippage_enabled = self.config.get('slippage', {}).get('enabled', False)
    slippage_pct = Decimal(str(self.config.get('slippage', {}).get('percentage', 0.1))) / Decimal('100')

    # Calculate fill price with slippage
    if slippage_enabled:
        fill_price = calculate_slippage_price(market_price, order.side, slippage_pct)
    else:
        fill_price = market_price

    # ... rest of execution ...
```

Run tests:
```bash
pytest tests/test_agents/test_execution_slippage.py -v
```

### ✅ CHECKPOINT 1: Commit
```bash
git add src/agents/execution.py tests/test_agents/test_execution_slippage.py config/app.yaml
git commit -m "feat(execution): add slippage simulation for paper trading"
```

---

## Step 3: Binance API Integration (60 min)

### 3.1 Write tests for Binance integration
**File**: `tests/test_agents/test_execution_binance.py`

```python
"""Tests for Binance API integration"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
from binance.exceptions import BinanceAPIException


@pytest.fixture
def mock_binance_client():
    """Mock Binance client"""
    client = MagicMock()

    # Mock successful order response
    client.order_market_buy = MagicMock(return_value={
        'orderId': 12345,
        'symbol': 'BTCUSDT',
        'executedQty': '0.5',
        'fills': [{
            'price': '50000.00',
            'qty': '0.5',
            'commission': '25.00',
            'commissionAsset': 'USDT'
        }]
    })

    client.order_market_sell = MagicMock(return_value={
        'orderId': 12346,
        'symbol': 'BTCUSDT',
        'executedQty': '0.5',
        'fills': [{
            'price': '50100.00',
            'qty': '0.5',
            'commission': '25.05',
            'commissionAsset': 'USDT'
        }]
    })

    return client


def test_binance_client_initialization():
    """Test Binance client can be initialized"""
    from binance.client import Client

    # Should not raise with testnet
    client = Client(api_key='test', api_secret='test', testnet=True)
    assert client is not None


@pytest.mark.asyncio
async def test_real_order_execution_buy(mock_binance_client):
    """Test real buy order execution"""
    from src.agents.execution import TradeExecutionAgent
    from src.models.events import TradeOrderEvent

    event_bus = MagicMock()
    event_bus.publish = AsyncMock()

    config = {
        'trading': {'mode': 'real'},
        'binance': {'api_key': 'test', 'api_secret': 'test', 'testnet': True}
    }

    agent = TradeExecutionAgent(event_bus, MagicMock(), config)
    agent.binance = mock_binance_client

    order = TradeOrderEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('0.5')
    )

    await agent._execute_order_real(order)

    # Verify Binance API was called
    mock_binance_client.order_market_buy.assert_called_once()

    # Verify trade event published
    event_bus.publish.assert_called()


@pytest.mark.asyncio
async def test_binance_api_error_handling(mock_binance_client):
    """Test handling of Binance API errors"""
    from src.agents.execution import TradeExecutionAgent
    from src.models.events import TradeOrderEvent

    event_bus = MagicMock()
    event_bus.publish = AsyncMock()

    config = {'trading': {'mode': 'real'}, 'binance': {}}

    agent = TradeExecutionAgent(event_bus, MagicMock(), config)
    agent.binance = mock_binance_client

    # Mock API error
    mock_binance_client.order_market_buy.side_effect = BinanceAPIException(
        None, 'Insufficient balance'
    )

    order = TradeOrderEvent(
        strategy_name='momentum',
        symbol='BTCUSDT',
        side='buy',
        quantity=Decimal('0.5')
    )

    # Should not raise, but handle gracefully
    await agent._execute_order_real(order)

    # Should publish error event
    assert event_bus.publish.called
```

### 3.2 Implement Binance integration
**File**: `src/agents/execution.py` (major update)

Update the TradeExecutionAgent class:

```python
# Add imports at top
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException

class TradeExecutionAgent(EventDrivenAgent):
    """Trade Execution Agent with Binance support"""

    def __init__(self, event_bus, db_manager, config):
        super().__init__('execution', event_bus)
        self.db = db_manager
        self.config = config
        self.mode = config['trading']['mode']

        # Initialize Binance client for real mode
        if self.mode == 'real':
            binance_config = config.get('binance', {})
            api_key = binance_config.get('api_key')
            api_secret = binance_config.get('api_secret')
            testnet = binance_config.get('testnet', True)

            if not api_key or not api_secret:
                self.logger.error("Binance API credentials not configured")
                raise ValueError("Missing Binance API credentials")

            self.logger.info(f"Initializing Binance client (testnet={testnet})")
            self.binance = BinanceClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )

            # Verify connection
            try:
                account = self.binance.get_account()
                self.logger.info(f"Binance connection verified. Account type: {account['accountType']}")
            except Exception as e:
                self.logger.error(f"Failed to verify Binance connection: {e}")
                raise

        else:
            self.binance = None
            self.logger.info("Running in paper trading mode")

        # Subscribe to order events
        self.add_subscription(TradeOrderEvent)

    async def _execute_order_real(self, order: TradeOrderEvent):
        """
        Execute real order on Binance

        SAFETY: This uses real money. All checks must pass.
        """
        try:
            self.logger.info(f"Executing REAL order: {order.side} {order.quantity} {order.symbol}")

            # Safety checks
            if not self.binance:
                raise ValueError("Binance client not initialized")

            # Execute order on Binance
            if order.side == 'buy':
                result = self.binance.order_market_buy(
                    symbol=order.symbol,
                    quantity=float(order.quantity)
                )
            else:  # sell
                result = self.binance.order_market_sell(
                    symbol=order.symbol,
                    quantity=float(order.quantity)
                )

            self.logger.info(f"Binance order result: {result}")

            # Parse fill information
            fill_price = Decimal(result['fills'][0]['price'])
            fill_qty = Decimal(result['executedQty'])
            fee = Decimal(result['fills'][0]['commission'])

            # Publish trade executed event
            await self.publish(TradeExecutedEvent(
                trade_id=None,
                order_id=str(result['orderId']),
                strategy_name=order.strategy_name,
                symbol=order.symbol,
                side=order.side,
                quantity=fill_qty,
                price=fill_price,
                fee=fee,
                trade_mode='real'
            ))

            self.logger.info(
                f"✅ REAL TRADE: {order.side} {fill_qty} {order.symbol} @ ${fill_price} "
                f"(fee: ${fee})"
            )

        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {e.message} (code: {e.code})")

            # Publish error event
            await self.publish(TradeErrorEvent(
                order_id=None,
                strategy_name=order.strategy_name,
                symbol=order.symbol,
                error_type='binance_api_error',
                error_message=f"{e.code}: {e.message}"
            ))

        except Exception as e:
            self.logger.error(f"Unexpected error executing real order: {e}", exc_info=True)

            await self.publish(TradeErrorEvent(
                order_id=None,
                strategy_name=order.strategy_name,
                symbol=order.symbol,
                error_type='execution_error',
                error_message=str(e)
            ))

    async def handle_event(self, event: Event):
        """Route order to paper or real execution"""
        if isinstance(event, TradeOrderEvent):
            if self.mode == 'paper':
                await self._execute_order_paper(event)
            else:  # real
                await self._execute_order_real(event)
```

Run tests:
```bash
pytest tests/test_agents/test_execution_binance.py -v
```

### ✅ CHECKPOINT 2: Commit & Review
```bash
git add src/agents/execution.py tests/test_agents/test_execution_binance.py
git commit -m "feat(execution): implement Binance API integration for real trading"
git push -u origin agent5-real-trading-binance
```

**🛑 REQUEST REVIEW**: "Agent 5 - Checkpoint 2. Binance integration complete. NEEDS CAREFUL REVIEW."

---

## Step 4: Safety Validation & Testing (20 min)

### 4.1 Create safety validation script
**File**: `scripts/validate_trading_safety.py`

```python
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
            var_name = value[2:-1].split(':')[0]
            return os.getenv(var_name, '')
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
        testnet = config['binance'].get('testnet', True)
        if not testnet:
            warnings.append("⚠️  Binance testnet is DISABLED - using LIVE trading!")
        else:
            print("✅ Binance testnet enabled")

    # Check 3: API credentials
    if mode == 'real':
        api_key = config['binance'].get('api_key', '')
        api_secret = config['binance'].get('api_secret', '')

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
```

Make executable:
```bash
chmod +x scripts/validate_trading_safety.py
```

Test it:
```bash
python scripts/validate_trading_safety.py
```

### ✅ CHECKPOINT 3: Commit & Review
```bash
git add scripts/validate_trading_safety.py docs/REAL_TRADING_SAFETY.md .env.example
git commit -m "feat(safety): add trading safety validation and documentation"
git push
```

**🛑 REQUEST REVIEW**: "Agent 5 - Checkpoint 3. Safety validation complete."

---

## Step 5: Documentation & Final Testing (20 min)

### 5.1 Update main README
**File**: `README.md` (add trading mode section)

```markdown
## Trading Modes

### Paper Trading (Default)
Simulates trading without real money:
- No actual orders placed
- Includes slippage simulation (0.1%)
- Safe for testing

### Real Trading ⚠️
**USE WITH EXTREME CAUTION**

1. **Test on Binance Testnet first**:
```yaml
trading:
  mode: real
binance:
  testnet: true  # Start here!
```

2. **Validate safety**:
```bash
python scripts/validate_trading_safety.py
```

3. **Set API credentials**:
```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
```

4. **Monitor actively**:
- Watch dashboard
- Check Binance UI
- Verify balances

See `docs/REAL_TRADING_SAFETY.md` for complete checklist.
```

### 5.2 Create quick reference
**File**: `docs/BINANCE_SETUP.md`

```markdown
# Binance API Setup

## Creating API Keys

1. Log into Binance
2. Account → API Management
3. Create New Key
4. Label: "Icarus Trading Bot"
5. **Restrictions**:
   - ✅ Enable Spot Trading
   - ❌ DISABLE Withdrawals
   - ❌ DISABLE Margin Trading
   - ❌ DISABLE Futures Trading
6. Save API key and secret securely

## Testnet Setup

1. Visit: https://testnet.binance.vision/
2. Log in with GitHub
3. Generate test API key
4. Use testnet for all initial testing
5. Testnet has fake funds (no real money)

## API Permissions

Required:
- Spot trading: YES
- Read account info: YES

Prohibited:
- Withdrawals: NO
- Transfers: NO
- Margin: NO
- Futures: NO

## Rate Limits

- Order placement: 10/second
- Account info: 5/second
- Market data: 20/second

System respects these limits automatically.

## Troubleshooting

### "Invalid API key"
- Check key is copied correctly
- Verify no extra spaces
- Check key not expired

### "Insufficient balance"
- Check account has funds
- Verify correct trading pair

### "Timestamp for this request is outside allowed"
- System clock out of sync
- Run: `sudo ntpdate -s time.nist.gov`
```

### 5.3 Final tests
```bash
# Run all execution tests
pytest tests/test_agents/test_execution*.py -v --cov=src.agents.execution

# Verify coverage > 80%
```

### ✅ FINAL: Commit & Review
```bash
git add README.md docs/BINANCE_SETUP.md
git commit -m "docs(trading): add Binance setup and real trading documentation"
git push
```

**🛑 FINAL REVIEW**: "Agent 5 - Complete. Real trading capability added. CRITICAL REVIEW NEEDED."

---

## Testing Checklist

- [ ] All tests pass
- [ ] Slippage working in paper mode
- [ ] Binance client initializes correctly
- [ ] API credentials validated
- [ ] Safety script works
- [ ] Testnet mode works
- [ ] Error handling robust
- [ ] Documentation complete

## Success Criteria

✅ Slippage simulation implemented
✅ Binance API integration complete
✅ Real trading mode functional
✅ Safety checks in place
✅ Testnet support working
✅ Comprehensive documentation
✅ Error handling robust
✅ Tests pass

## CRITICAL REMINDERS

1. **ALWAYS** start with testnet
2. **NEVER** commit API keys
3. **ALWAYS** use small amounts initially
4. **MONITOR** actively during first trades
5. **RESTRICT** API key permissions
6. You can **LOSE REAL MONEY**
