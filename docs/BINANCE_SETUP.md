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

## Configuration

### Environment Variables

Set your API credentials in environment variables:

```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

Or add them to your `.env` file:

```bash
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### Configuration File

Update `config/app.yaml`:

```yaml
trading:
  mode: real  # Change from 'paper' to 'real'

binance:
  testnet: true  # ALWAYS START WITH TESTNET
  api_key: ${BINANCE_API_KEY:}
  api_secret: ${BINANCE_API_SECRET:}
```

## Safety Checklist

Before enabling real trading, run the safety validation script:

```bash
python scripts/validate_trading_safety.py
```

This will check:
- API credentials are configured
- Risk limits are reasonable
- Testnet is enabled (for first-time use)
- Trading mode is appropriate

## Testing Workflow

1. **Start with testnet**:
   ```yaml
   binance:
     testnet: true
   ```

2. **Enable paper trading first**:
   ```yaml
   trading:
     mode: paper
   ```

3. **Test thoroughly** - Run for at least a few hours

4. **Switch to real + testnet**:
   ```yaml
   trading:
     mode: real
   binance:
     testnet: true
   ```

5. **Verify testnet trades work**

6. **Finally, enable mainnet** (with extreme caution):
   ```yaml
   binance:
     testnet: false
   ```

## Emergency Procedures

If something goes wrong:

1. **Stop the system immediately**:
   ```bash
   pkill -f "python src/main.py"
   ```

2. **Cancel all open orders** via Binance web UI

3. **Review logs** in `logs/icarus.log`

4. **Check trades** in database:
   ```sql
   SELECT * FROM trades WHERE trade_mode = 'real' ORDER BY time DESC LIMIT 10;
   ```
