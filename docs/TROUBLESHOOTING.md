# Troubleshooting Guide

## Installation Issues

### "ModuleNotFoundError: No module named 'X'"
**Cause**: Missing Python dependency

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall all dependencies
pip install -r requirements.txt

# If still failing, try upgrading pip
pip install --upgrade pip
pip install -r requirements.txt
```

### "Permission denied" on scripts
**Cause**: Script files not executable

**Solution**:
```bash
chmod +x scripts/*.py
chmod +x sql/*.sh

# Or run with python explicitly
python scripts/health_check.py
```

### "Python version mismatch"
**Cause**: Python 3.11+ required

**Solution**:
```bash
# Check Python version
python --version

# If < 3.11, install Python 3.11+
# macOS with Homebrew
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11

# Create venv with correct Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "SSL certificate verification failed"
**Cause**: Certificate issues with pip or network

**Solution**:
```bash
# Upgrade certifi
pip install --upgrade certifi

# Or temporarily disable SSL verification (not recommended for production)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

## Database Issues

### "Connection refused" to database
**Causes**:
1. Tiger Cloud credentials incorrect
2. Network/firewall blocking connection
3. Service not running
4. Wrong host/port

**Solutions**:
```bash
# 1. Verify credentials in .env
cat .env | grep TIGER

# 2. Test connection manually
psql -h $TIGER_HOST -p $TIGER_PORT -U $TIGER_USER -d $TIGER_DATABASE

# 3. Check Tiger Cloud console
# https://console.tigerdata.cloud/
# Verify service is running

# 4. Test network connectivity
ping $TIGER_HOST
telnet $TIGER_HOST $TIGER_PORT

# 5. Check firewall rules
# Ensure outbound connections to Tiger Cloud are allowed
```

### "Table does not exist"
**Cause**: Database schema not deployed

**Solution**:
```bash
# Deploy schema
./sql/deploy_schema.sh

# Or manually
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -f sql/schema.sql

# Verify tables exist
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "\dt"

# Check hypertables specifically
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "SELECT * FROM timescaledb_information.hypertables;"
```

### "Hypertable already exists"
**Cause**: Trying to recreate existing hypertable

**Solution**:
```sql
-- Option 1: Check if exists before creating
SELECT create_hypertable('table_name', 'time', if_not_exists => TRUE);

-- Option 2: Drop and recreate (⚠️ deletes data)
DROP TABLE IF EXISTS table_name CASCADE;
-- Then recreate table and hypertable
```

### "Too many connections"
**Cause**: Connection pool exhausted or not closed properly

**Solutions**:
```bash
# 1. Check current connections
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "SELECT count(*) FROM pg_stat_activity;"

# 2. Adjust pool settings in config/app.yaml
database:
  pool_min_size: 5
  pool_max_size: 20  # Increase if needed

# 3. Ensure agents are stopped properly
# Use Ctrl+C for graceful shutdown

# 4. Manually close connections (if needed)
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'your_database' AND pid <> pg_backend_pid();
"
```

### "asyncpg timeout"
**Cause**: Query taking too long or database overloaded

**Solution**:
```yaml
# Increase timeout in config/app.yaml
database:
  timeout: 60  # Increase from 30 to 60 seconds
```

## Agent Issues

### Agent crashes on startup
**Symptoms**: Agent starts then immediately stops

**Diagnosis**:
```bash
# 1. Check logs for errors
tail -f logs/icarus.log

# 2. Run with DEBUG logging
# Edit config/app.yaml
logging:
  level: DEBUG

# 3. Verify config syntax
python -c "import yaml; print(yaml.safe_load(open('config/app.yaml')))"

# 4. Test imports
python -c "from src.agents.market_data import MarketDataAgent"
python -c "from src.agents.meta_strategy import MetaStrategyAgent"

# 5. Check for port conflicts
lsof -i :8000  # Web server port
```

**Common Solutions**:
- Fix YAML syntax errors in config
- Ensure all required config fields present
- Verify database connection works
- Check file permissions on logs directory

### No market data received
**Causes**:
1. Binance WebSocket connection failed
2. Symbol not configured or invalid
3. Network connectivity issues
4. API rate limiting

**Solutions**:
```bash
# 1. Check configuration
grep -A5 "symbols:" config/app.yaml

# 2. Test Binance connectivity
curl https://api.binance.com/api/v3/ping
python -c "from binance.client import Client; c = Client(); print(c.get_server_time())"

# 3. Check logs for WebSocket errors
grep "market_data\|WebSocket" logs/icarus.log

# 4. Verify symbol is valid
curl "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"

# 5. Check if data is being stored
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT COUNT(*), MAX(time)
FROM crypto_prices
WHERE symbol='BTCUSDT' AND time > NOW() - INTERVAL '10 minutes';
"
```

### Strategy not generating signals
**Causes**:
1. Not enough historical data (warmup period)
2. Strategy disabled in config
3. No trading condition met
4. Market data not flowing

**Solutions**:
```bash
# 1. Check if strategy is enabled
grep -A10 "strategies:" config/app.yaml

# 2. Verify warmup period requirements
# Strategies need N data points before generating signals
# Check strategy config for warmup_period

# 3. Check for signals in database
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT strategy_name, COUNT(*), MAX(time)
FROM trading_signals
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY strategy_name;
"

# 4. Check market data available
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT symbol, COUNT(*), MAX(time)
FROM crypto_prices
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY symbol;
"

# 5. Enable DEBUG logging to see signal generation logic
```

### Meta-strategy not allocating capital
**Causes**:
1. All strategies performing poorly
2. No signals from strategies
3. Risk limits preventing allocation
4. Initial warmup period

**Solutions**:
```bash
# 1. Check current allocations
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM current_allocations;
"

# 2. Check strategy performance
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM strategy_performance
ORDER BY time DESC
LIMIT 10;
"

# 3. Check for risk alerts
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM risk_alerts
ORDER BY time DESC
LIMIT 10;
"

# 4. Verify evaluation interval
grep "evaluation_interval" config/app.yaml

# 5. Check logs for allocation decisions
grep "meta_strategy" logs/icarus.log | tail -20
```

## Trading Issues

### Orders not executing
**Causes**:
1. Risk limits exceeded
2. Insufficient balance (live mode)
3. Strategy not allocated capital
4. Binance API errors

**Solutions**:
```bash
# 1. Check risk alerts
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM risk_alerts
ORDER BY time DESC
LIMIT 5;
"

# 2. Check allocations
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM current_allocations
WHERE is_active = true;
"

# 3. Check execution logs
grep "execution\|trade" logs/icarus.log | tail -30

# 4. Verify trading mode
grep "mode:" config/app.yaml

# 5. Check portfolio state
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM strategy_performance
ORDER BY time DESC
LIMIT 5;
"
```

### Binance API errors

**Error: "Invalid API key"**
```bash
# Solution: Verify credentials
echo $BINANCE_API_KEY
echo $BINANCE_API_SECRET

# Check .env file
grep BINANCE .env

# Test API key
python -c "
from binance.client import Client
import os
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
print(client.get_account())
"
```

**Error: "Insufficient balance"**
```bash
# Solution: Check Binance account balance
python -c "
from binance.client import Client
import os
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
print(client.get_account()['balances'])
"

# Reduce position sizes in config
trading:
  position_size_pct: 10  # Reduce from 20 to 10%
```

**Error: "Timestamp outside allowed window"**
```bash
# Solution: Sync system clock
sudo ntpdate -s time.nist.gov

# Or on modern systems
sudo timedatectl set-ntp true

# Verify time sync
timedatectl status
```

**Error: "Rate limit exceeded"**
```bash
# Solution: Reduce request frequency
# Add delays between requests
# Check meta_strategy evaluation_interval in config

# Binance limits:
# - 1200 requests per minute
# - 10 orders per second
```

### Paper trading not simulating correctly
**Issues**: Unrealistic P&L, no slippage

**Solution**:
```python
# Check execution agent configuration
# Ensure slippage simulation is enabled
# Default: 0.1% slippage in paper mode

# Verify in logs
grep "slippage" logs/icarus.log
```

## Dashboard Issues

### Dashboard won't load
**Causes**:
1. Web server not started
2. Port 8000 in use
3. CORS issues
4. Static files missing

**Solutions**:
```bash
# 1. Check if web server is running
lsof -i :8000
ps aux | grep "uvicorn\|fastapi"

# 2. Check logs for web server errors
grep "FastAPI\|uvicorn" logs/icarus.log

# 3. Test if port is accessible
curl http://localhost:8000/
curl http://localhost:8000/api/health

# 4. Try different port (edit src/web/server.py)
# Change: uvicorn.run(app, host="0.0.0.0", port=8001)

# 5. Check static files exist
ls -la src/web/static/

# 6. Restart system
Ctrl+C
python src/main.py
```

### WebSocket not connecting
**Symptoms**: Connection status shows "Disconnected" on dashboard

**Solutions**:
```bash
# 1. Check browser console for errors
# Open browser dev tools (F12) → Console tab

# 2. Verify WebSocket endpoint
# Should be: ws://localhost:8000/ws

# 3. Test WebSocket with wscat
npm install -g wscat
wscat -c ws://localhost:8000/ws

# 4. Check CORS settings in src/web/api.py
# Ensure WebSocket origin is allowed

# 5. Check for proxy/firewall issues
# WebSocket requires HTTP upgrade support
```

### No data showing on dashboard
**Causes**:
1. No data in database
2. API endpoints failing
3. Database connection issue
4. Time range filters

**Solutions**:
```bash
# 1. Test API endpoints directly
curl http://localhost:8000/api/portfolio
curl http://localhost:8000/api/trades/recent
curl http://localhost:8000/api/forks/active

# 2. Check database for data
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT COUNT(*) FROM trades;
SELECT COUNT(*) FROM positions;
SELECT COUNT(*) FROM current_allocations;
"

# 3. Check API logs for errors
grep "api\|endpoint" logs/icarus.log

# 4. Verify database connection from web server
# Should see connection info in startup logs
```

### Dashboard shows stale data
**Cause**: WebSocket not updating, caching issues

**Solution**:
```bash
# 1. Hard refresh browser
# Chrome/Firefox: Ctrl+Shift+R
# Safari: Cmd+Shift+R

# 2. Clear browser cache

# 3. Check WebSocket is connected
# Browser console should show "WebSocket connected"

# 4. Restart web server
Ctrl+C
python src/main.py
```

## Performance Issues

### High CPU usage
**Causes**:
1. Too many strategies running
2. Calculation-heavy indicators
3. Tight evaluation loops
4. Memory leaks

**Diagnosis**:
```bash
# Monitor CPU usage
top -p $(pgrep -f "python src/main.py")

# Profile with py-spy
pip install py-spy
sudo py-spy top --pid $(pgrep -f "python src/main.py")

# Check event bus stats
grep "event_bus.*stats" logs/icarus.log
```

**Solutions**:
```yaml
# 1. Disable unused strategies
strategies:
  momentum:
    enabled: false

# 2. Increase evaluation intervals
meta_strategy:
  evaluation_interval_minutes: 15  # Increase from 5

# 3. Reduce warmup periods
strategies:
  momentum:
    warmup_period: 30  # Reduce from 50

# 4. Limit price history
# Implement max_history in strategy configs
```

### High memory usage
**Causes**:
1. Price history growing unbounded
2. Too many event subscriptions
3. Connection pool leaks
4. Large query results

**Diagnosis**:
```bash
# Monitor memory usage
ps aux | grep python
top -p $(pgrep -f "python src/main.py")

# Python memory profiler
pip install memory_profiler
python -m memory_profiler src/main.py
```

**Solutions**:
```python
# 1. Implement max_history in strategies
# Limit price buffer to recent N points

# 2. Reduce event queue sizes
# In src/core/event_bus.py
EventBus(max_queue_size=500)  # Reduce from 1000

# 3. Check for connection leaks
# Ensure async with get_db_connection() is used

# 4. Restart system periodically
# Set up cron job for nightly restarts
```

### Slow database queries
**Cause**: Missing indexes, large tables

**Diagnosis**:
```sql
-- Check query performance
EXPLAIN ANALYZE SELECT * FROM trades WHERE time > NOW() - INTERVAL '1 day';

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check missing indexes
SELECT * FROM pg_stat_user_tables WHERE idx_scan = 0;
```

**Solutions**:
```sql
-- Add indexes for common queries
CREATE INDEX idx_trades_strategy ON trades(strategy_name, time DESC);
CREATE INDEX idx_signals_strategy ON trading_signals(strategy_name, time DESC);

-- Enable TimescaleDB compression
ALTER TABLE crypto_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('crypto_prices', INTERVAL '7 days');

-- Set retention policies
SELECT add_retention_policy('crypto_prices', INTERVAL '90 days');
```

## Fork Issues

### Forks not being created
**Causes**:
1. Tiger Cloud quota exceeded
2. Fork Manager agent not running
3. API credentials wrong
4. Network issues

**Solutions**:
```bash
# 1. Check Tiger Cloud console for quota
# https://console.tigerdata.cloud/

# 2. Check Fork Manager logs
grep "fork_manager" logs/icarus.log

# 3. Verify TIGER_SERVICE_ID in .env
cat .env | grep TIGER_SERVICE_ID

# 4. Check fork tracking table
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT * FROM fork_tracking
ORDER BY created_at DESC
LIMIT 10;
"

# 5. Test Tiger Cloud API access
# (requires tiger-cli if installed)
```

### Forks not being destroyed
**Cause**: TTL not expiring or cleanup failed

**Solutions**:
```bash
# 1. Check fork status
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
SELECT fork_id, purpose, created_at, ttl_seconds, status
FROM fork_tracking
WHERE status = 'active';
"

# 2. Check Fork Manager cleanup logs
grep "cleanup\|destroy" logs/icarus.log

# 3. Manually mark fork as expired
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "
UPDATE fork_tracking
SET status = 'expired'
WHERE fork_id = 'fork_xyz123';
"

# 4. Manually destroy via Tiger Cloud console
# https://console.tigerdata.cloud/ → Forks → Delete

# 5. Adjust cleanup interval
# In config/app.yaml
fork_usage:
  cleanup_check_interval_seconds: 30  # More frequent
```

### Too many concurrent forks
**Cause**: Fork limit exceeded

**Solution**:
```yaml
# Adjust max concurrent forks in config/app.yaml
tiger:
  max_concurrent_forks: 20  # Increase if quota allows

# Or reduce fork creation frequency
fork_usage:
  validation_interval_minutes: 10  # Increase interval
```

## Logging Issues

### No logs being written
**Cause**: Log directory doesn't exist or permission issues

**Solution**:
```bash
# Create logs directory
mkdir -p logs

# Check permissions
ls -la logs/

# Fix permissions if needed
chmod 755 logs/
chmod 644 logs/icarus.log

# Verify logging config
grep -A5 "logging:" config/app.yaml
```

### Logs too verbose
**Solution**:
```yaml
# Reduce log level in config/app.yaml
logging:
  level: INFO  # or WARNING, ERROR
```

### Logs not in JSON format
**Solution**:
```yaml
# Enable JSON logging in config/app.yaml
logging:
  format: json
```

## Getting Help

### Self-Diagnosis Checklist
1. ✅ Check logs: `tail -f logs/icarus.log`
2. ✅ Run health check: `python scripts/health_check.py`
3. ✅ Check database connectivity: `psql -h $TIGER_HOST ...`
4. ✅ Verify config: `python -c "import yaml; print(yaml.safe_load(open('config/app.yaml')))"`
5. ✅ Review recent changes: `git log -5`
6. ✅ Check system resources: `top`, `df -h`

### Debug Mode

Enable detailed debug logging:

```yaml
# config/app.yaml
logging:
  level: DEBUG  # Change from INFO
```

Restart system:
```bash
Ctrl+C
python src/main.py
```

Review debug logs:
```bash
tail -f logs/icarus.log | grep DEBUG
```

### Common Error Patterns

**Pattern**: Repeated connection errors
→ **Solution**: Check database credentials and network

**Pattern**: Memory growing continuously
→ **Solution**: Check for resource leaks, add cleanup

**Pattern**: No signals generated
→ **Solution**: Wait for warmup period, check market data

**Pattern**: Trades not executing
→ **Solution**: Check risk limits, allocations, balance

### Community Support

1. **GitHub Issues**: Report bugs with logs and config
2. **Documentation**: Check other docs in `docs/` directory
3. **Stack Overflow**: Search for similar issues
4. **Tiger Cloud Support**: For database/fork issues

### Filing a Bug Report

Include:
1. Icarus version: `git rev-parse HEAD`
2. Python version: `python --version`
3. Operating system: `uname -a`
4. Error logs: Last 50 lines of `logs/icarus.log`
5. Configuration: `config/app.yaml` (remove secrets)
6. Steps to reproduce
7. Expected vs actual behavior
