# Fork Frequency Configuration

## Overview

The system has been configured for **frequent fork usage** to maximize visibility and demonstration value of Tiger Cloud's forkable database capabilities.

## Current Configuration

### Meta-Strategy Evaluation
- **Interval**: Every 5 minutes (changed from 6 hours)
- **Fork Usage**: Creates fork for scenario analysis before each reallocation
- **Expected Forks**: ~12 forks/hour from meta-strategy alone

### Strategy Validation
- **Interval**: Every 5 minutes per strategy
- **Strategies**: 2 currently (momentum, MACD), up to 6 total
- **Fork Usage**: Each strategy validates performance on recent data
- **Expected Forks**:
  - 2 strategies: ~24 forks/hour
  - 6 strategies: ~72 forks/hour

### Parameter Optimization
- **Interval**: Every 15 minutes per strategy
- **Fork Usage**: Tests multiple parameter sets in parallel
- **Expected Forks**: 4-6 forks per optimization run
- **Total**: 8-12 forks/hour per strategy

### Fork Lifecycle
- **Default TTL**: 10 minutes (600 seconds)
- **Validation TTL**: 5 minutes (300 seconds) for quick validations
- **Cleanup Check**: Every 60 seconds
- **Max Concurrent**: 10 forks

## Expected Fork Activity

### With 2 Strategies (Current)
```
Meta-Strategy:        12 forks/hour
Strategy Validations: 24 forks/hour
Parameter Optimization: 16-24 forks/hour
─────────────────────────────────────
Total:               52-60 forks/hour
```

### With 6 Strategies (Full System)
```
Meta-Strategy:        12 forks/hour
Strategy Validations: 72 forks/hour
Parameter Optimization: 48-72 forks/hour
─────────────────────────────────────
Total:               132-156 forks/hour
                     ~2-3 forks/minute!
```

## Configuration Files

### `config/app.yaml`
```yaml
meta_strategy:
  evaluation_interval_minutes: 5  # Every 5 minutes

fork_usage:
  validation_interval_minutes: 5  # Each strategy validates every 5 min
  optimization_interval_minutes: 15  # Parameter testing every 15 min
  scenario_analysis_enabled: true  # Meta-strategy uses forks
  default_fork_ttl_seconds: 600  # 10 minute lifetime
  validation_fork_ttl_seconds: 300  # 5 minute for quick tests
  cleanup_check_interval_seconds: 60  # Check every minute
```

### Code Changes
- `src/agents/meta_strategy.py`: Changed from hours to minutes
- `src/agents/fork_manager.py`: Cleanup every 60s (was 1800s)

## Dashboard Impact

With this configuration, the dashboard will show:
- **Active Forks Panel**: Constantly updating with new forks
- **Fork Timeline**: Dense activity showing continuous validation
- **PR Narratives**: Frequent updates about fork-based decisions

Example narratives:
- "Meta-strategy created fork for scenario analysis, testing 4 allocations"
- "Momentum strategy validated on 7-day fork, confirmed 8.5% ROI"
- "MACD strategy optimizing parameters across 5 parallel forks"
- "Fork cleanup: destroyed 3 expired validation forks"

## Demo Mode

This configuration IS demo mode. For production:

### Recommended Production Settings
```yaml
meta_strategy:
  evaluation_interval_minutes: 360  # 6 hours

fork_usage:
  validation_interval_minutes: 360  # 6 hours
  optimization_interval_minutes: 1440  # Daily
  default_fork_ttl_seconds: 3600  # 1 hour
  cleanup_check_interval_seconds: 300  # 5 minutes
```

This would reduce to ~6-8 forks/hour in production.

## Resource Considerations

### Tiger Cloud Costs
- Fork creation: Small metadata overhead
- Fork storage: Depends on data size
- At 2-3 forks/minute, monitor costs closely

### Database Load
- Each fork copies current state
- Queries run on forks don't affect main DB
- Cleanup is automated

### Monitoring
Check fork_tracking table:
```sql
-- Active forks count
SELECT COUNT(*) FROM fork_tracking WHERE status = 'active';

-- Forks created in last hour
SELECT COUNT(*) FROM fork_tracking
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Average fork lifetime
SELECT AVG(EXTRACT(EPOCH FROM (destroyed_at - created_at)))
FROM fork_tracking
WHERE destroyed_at IS NOT NULL;
```

## Adjusting Frequency

To change fork frequency, edit `config/app.yaml`:

### More Frequent (for intense demos)
```yaml
meta_strategy:
  evaluation_interval_minutes: 2  # Every 2 minutes!

fork_usage:
  validation_interval_minutes: 2
```

### Less Frequent (for cost management)
```yaml
meta_strategy:
  evaluation_interval_minutes: 30  # Every 30 minutes

fork_usage:
  validation_interval_minutes: 30
```

## Notes

- Fork frequency is **independent** of trading frequency
- Strategies still generate signals based on market data
- Forks are for **validation and analysis**, not signal generation
- All forks are **read-only** - they don't affect main database
- Cleanup is **automatic** - no manual intervention needed

## Benefits of High Frequency

1. **Visibility**: Constantly demonstrates fork capabilities
2. **Validation**: Frequent performance checks catch issues quickly
3. **Optimization**: Rapid parameter tuning
4. **Demo Value**: Dashboard always shows active forks
5. **Showcase**: Clear evidence of fork-centric architecture

The system is now configured to create **~2-3 forks per minute** when fully operational!
