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
