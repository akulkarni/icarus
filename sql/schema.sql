-- Icarus Trading System Database Schema
-- TimescaleDB-optimized schema for high-frequency trading data

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- Market Data Tables
-- ============================================================================

-- Real-time market tick data
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    bid NUMERIC(20, 8),
    ask NUMERIC(20, 8),
    spread NUMERIC(20, 8)
);

-- Convert to hypertable
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time
    ON market_data (symbol, time DESC);

-- OHLCV candle data (aggregated)
CREATE TABLE IF NOT EXISTS ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL, -- 1m, 5m, 15m, 1h, 4h, 1d
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    trades INTEGER
);

SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_interval_time
    ON ohlcv (symbol, interval, time DESC);

-- ============================================================================
-- Trading Tables
-- ============================================================================

-- Trading signals from strategies
CREATE TABLE IF NOT EXISTS trading_signals (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_id UUID DEFAULT gen_random_uuid(),
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    confidence NUMERIC(5, 4) CHECK (confidence >= 0 AND confidence <= 1),
    reason TEXT,
    metadata JSONB
);

SELECT create_hypertable('trading_signals', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_signals_strategy_time
    ON trading_signals (strategy_name, time DESC);

-- Executed trades
CREATE TABLE IF NOT EXISTS trades (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_id UUID DEFAULT gen_random_uuid(),
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    value NUMERIC(20, 8) GENERATED ALWAYS AS (quantity * price) STORED,
    fee NUMERIC(20, 8) NOT NULL DEFAULT 0,
    order_id TEXT,
    trade_mode TEXT NOT NULL CHECK (trade_mode IN ('paper', 'live')),
    metadata JSONB
);

SELECT create_hypertable('trades', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_trades_strategy_time
    ON trades (strategy_name, time DESC);

CREATE INDEX IF NOT EXISTS idx_trades_symbol_time
    ON trades (symbol, time DESC);

-- Positions (current holdings)
CREATE TABLE IF NOT EXISTS positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    current_price NUMERIC(20, 8),
    unrealized_pnl NUMERIC(20, 8),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(strategy_name, symbol)
);

CREATE INDEX IF NOT EXISTS idx_positions_strategy
    ON positions (strategy_name);

-- Position history (closed positions)
CREATE TABLE IF NOT EXISTS position_history (
    time TIMESTAMPTZ NOT NULL,
    position_id UUID NOT NULL,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8) NOT NULL,
    pnl NUMERIC(20, 8) NOT NULL,
    return_pct NUMERIC(10, 6) NOT NULL,
    hold_duration INTERVAL,
    metadata JSONB
);

SELECT create_hypertable('position_history', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_position_history_strategy_time
    ON position_history (strategy_name, time DESC);

-- ============================================================================
-- Portfolio & Performance Tables
-- ============================================================================

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy_name TEXT NOT NULL,
    total_value NUMERIC(20, 8) NOT NULL,
    cash NUMERIC(20, 8) NOT NULL,
    positions_value NUMERIC(20, 8) NOT NULL,
    unrealized_pnl NUMERIC(20, 8) NOT NULL,
    realized_pnl NUMERIC(20, 8) NOT NULL,
    total_return_pct NUMERIC(10, 6) NOT NULL,
    num_positions INTEGER NOT NULL,
    metadata JSONB
);

SELECT create_hypertable('portfolio_snapshots', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_portfolio_strategy_time
    ON portfolio_snapshots (strategy_name, time DESC);

-- Strategy performance metrics
CREATE TABLE IF NOT EXISTS strategy_performance (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy_name TEXT NOT NULL,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate NUMERIC(5, 4),
    total_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,
    sharpe_ratio NUMERIC(10, 6),
    max_drawdown NUMERIC(10, 6),
    current_drawdown NUMERIC(10, 6),
    volatility NUMERIC(10, 6),
    metadata JSONB
);

SELECT create_hypertable('strategy_performance', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_name_time
    ON strategy_performance (strategy_name, time DESC);

-- ============================================================================
-- Meta-Strategy & Allocation Tables
-- ============================================================================

-- Capital allocation events
CREATE TABLE IF NOT EXISTS allocation_events (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_id UUID DEFAULT gen_random_uuid(),
    allocations JSONB NOT NULL, -- {strategy_name: allocation_pct}
    reason TEXT,
    metadata JSONB
);

SELECT create_hypertable('allocation_events', 'time', if_not_exists => TRUE);

-- Current allocations (latest state)
CREATE TABLE IF NOT EXISTS current_allocations (
    strategy_name TEXT PRIMARY KEY,
    allocation_pct NUMERIC(5, 2) NOT NULL CHECK (allocation_pct >= 0 AND allocation_pct <= 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Fork Management Tables
-- ============================================================================

-- Database fork tracking
CREATE TABLE IF NOT EXISTS fork_tracking (
    fork_id TEXT PRIMARY KEY,
    parent_service_id TEXT NOT NULL,
    requesting_agent TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('creating', 'active', 'destroying', 'destroyed')),
    connection_params JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    destroyed_at TIMESTAMPTZ,
    ttl_seconds INTEGER NOT NULL,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_fork_tracking_status
    ON fork_tracking (status, created_at);

-- Fork simulation results
CREATE TABLE IF NOT EXISTS fork_results (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    result_id UUID DEFAULT gen_random_uuid(),
    fork_id TEXT NOT NULL REFERENCES fork_tracking(fork_id),
    experiment_type TEXT NOT NULL, -- backtest, parameter_optimization, etc.
    result_data JSONB NOT NULL,
    metrics JSONB,
    metadata JSONB
);

SELECT create_hypertable('fork_results', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_fork_results_fork_id
    ON fork_results (fork_id, time DESC);

-- ============================================================================
-- Risk Management Tables
-- ============================================================================

-- Risk alerts
CREATE TABLE IF NOT EXISTS risk_alerts (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_id UUID DEFAULT gen_random_uuid(),
    alert_type TEXT NOT NULL, -- position_size, daily_loss, drawdown, exposure
    severity TEXT NOT NULL CHECK (severity IN ('warning', 'critical', 'emergency')),
    strategy_name TEXT,
    symbol TEXT,
    message TEXT NOT NULL,
    current_value NUMERIC(20, 8),
    threshold_value NUMERIC(20, 8),
    metadata JSONB
);

SELECT create_hypertable('risk_alerts', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_risk_alerts_severity_time
    ON risk_alerts (severity, time DESC);

-- Emergency halt events
CREATE TABLE IF NOT EXISTS halt_events (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    halt_id UUID DEFAULT gen_random_uuid(),
    reason TEXT NOT NULL,
    triggered_by TEXT NOT NULL, -- agent or manual
    resumed_at TIMESTAMPTZ,
    metadata JSONB
);

SELECT create_hypertable('halt_events', 'time', if_not_exists => TRUE);

-- ============================================================================
-- Event Log (All System Events)
-- ============================================================================

-- Unified event log for debugging and replay
CREATE TABLE IF NOT EXISTS event_log (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_id UUID DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    event_data JSONB NOT NULL,
    metadata JSONB
);

SELECT create_hypertable('event_log', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_event_log_type_time
    ON event_log (event_type, time DESC);

CREATE INDEX IF NOT EXISTS idx_event_log_agent_time
    ON event_log (agent_name, time DESC);

-- GIN index for JSON queries
CREATE INDEX IF NOT EXISTS idx_event_log_data
    ON event_log USING GIN (event_data);

-- ============================================================================
-- Agent Metadata Tables
-- ============================================================================

-- Agent status tracking
CREATE TABLE IF NOT EXISTS agent_status (
    agent_name TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('starting', 'running', 'stopping', 'stopped', 'error')),
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_message TEXT,
    metadata JSONB
);

-- Agent metrics
CREATE TABLE IF NOT EXISTS agent_metrics (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC(20, 8) NOT NULL,
    metadata JSONB
);

SELECT create_hypertable('agent_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_name_time
    ON agent_metrics (agent_name, metric_name, time DESC);

-- ============================================================================
-- Continuous Aggregates (Performance Optimization)
-- ============================================================================

-- 1-minute OHLCV aggregate from tick data
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS time,
    symbol,
    first(price, time) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, time) AS close,
    sum(volume) AS volume
FROM market_data
GROUP BY time_bucket('1 minute', time), symbol;

-- Add refresh policy for 1-minute aggregates
SELECT add_continuous_aggregate_policy('ohlcv_1m',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

-- Daily strategy performance summary
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_strategy_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    strategy_name,
    count(*) AS total_trades,
    sum(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
    sum(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
    sum(pnl) AS total_pnl,
    avg(pnl) AS avg_pnl,
    stddev(pnl) AS pnl_stddev,
    max(pnl) AS max_win,
    min(pnl) AS max_loss
FROM position_history
GROUP BY time_bucket('1 day', time), strategy_name;

SELECT add_continuous_aggregate_policy('daily_strategy_performance',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- ============================================================================
-- Data Retention Policies
-- ============================================================================

-- Keep raw tick data for 30 days
SELECT add_retention_policy('market_data', INTERVAL '30 days', if_not_exists => TRUE);

-- Keep event log for 90 days
SELECT add_retention_policy('event_log', INTERVAL '90 days', if_not_exists => TRUE);

-- Keep agent metrics for 60 days
SELECT add_retention_policy('agent_metrics', INTERVAL '60 days', if_not_exists => TRUE);

-- Keep fork results for 180 days
SELECT add_retention_policy('fork_results', INTERVAL '180 days', if_not_exists => TRUE);

-- ============================================================================
-- Compression Policies
-- ============================================================================

-- Compress market data older than 7 days
SELECT add_compression_policy('market_data', INTERVAL '7 days', if_not_exists => TRUE);

-- Compress trades older than 30 days
SELECT add_compression_policy('trades', INTERVAL '30 days', if_not_exists => TRUE);

-- Compress event log older than 30 days
SELECT add_compression_policy('event_log', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to calculate strategy win rate
CREATE OR REPLACE FUNCTION calculate_win_rate(p_strategy_name TEXT, p_lookback INTERVAL DEFAULT '7 days')
RETURNS NUMERIC AS $$
DECLARE
    total_trades INTEGER;
    winning_trades INTEGER;
BEGIN
    SELECT
        COUNT(*),
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)
    INTO total_trades, winning_trades
    FROM position_history
    WHERE strategy_name = p_strategy_name
        AND time >= NOW() - p_lookback;

    IF total_trades = 0 THEN
        RETURN 0;
    END IF;

    RETURN winning_trades::NUMERIC / total_trades::NUMERIC;
END;
$$ LANGUAGE plpgsql;

-- Function to get current portfolio value
CREATE OR REPLACE FUNCTION get_portfolio_value(p_strategy_name TEXT)
RETURNS NUMERIC AS $$
DECLARE
    portfolio_value NUMERIC;
BEGIN
    SELECT total_value INTO portfolio_value
    FROM portfolio_snapshots
    WHERE strategy_name = p_strategy_name
    ORDER BY time DESC
    LIMIT 1;

    RETURN COALESCE(portfolio_value, 0);
END;
$$ LANGUAGE plpgsql;

-- Function to check if trading is halted
CREATE OR REPLACE FUNCTION is_trading_halted()
RETURNS BOOLEAN AS $$
DECLARE
    active_halt BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM halt_events
        WHERE resumed_at IS NULL
        ORDER BY time DESC
        LIMIT 1
    ) INTO active_halt;

    RETURN active_halt;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Initialize agent status table
INSERT INTO agent_status (agent_name, status, last_heartbeat)
VALUES
    ('market_data', 'stopped', NOW()),
    ('momentum', 'stopped', NOW()),
    ('macd', 'stopped', NOW()),
    ('execution', 'stopped', NOW()),
    ('meta_strategy', 'stopped', NOW()),
    ('fork_manager', 'stopped', NOW()),
    ('risk_monitor', 'stopped', NOW())
ON CONFLICT (agent_name) DO NOTHING;

-- Initialize allocations (equal weighting)
INSERT INTO current_allocations (strategy_name, allocation_pct, updated_at)
VALUES
    ('momentum', 50.00, NOW()),
    ('macd', 50.00, NOW())
ON CONFLICT (strategy_name) DO NOTHING;

-- ============================================================================
-- Grants (if needed for specific users)
-- ============================================================================

-- Grant permissions to tsdbadmin (already has full access, but explicit grants can be added here)

-- ============================================================================
-- Schema Complete
-- ============================================================================

-- Verify hypertables created
SELECT hypertable_name, hypertable_schema
FROM timescaledb_information.hypertables
ORDER BY hypertable_name;
