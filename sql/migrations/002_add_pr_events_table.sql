-- PR Events Table for narrative generation
CREATE TABLE IF NOT EXISTS pr_events (
    time TIMESTAMPTZ NOT NULL,
    narrative TEXT NOT NULL,
    event_category VARCHAR(50) NOT NULL,  -- performance, risk, allocation, fork, trade
    importance_score INTEGER NOT NULL CHECK (importance_score BETWEEN 1 AND 10),
    related_strategy VARCHAR(50),
    metadata JSONB,
    PRIMARY KEY (time, event_category)
);

SELECT create_hypertable('pr_events', 'time', if_not_exists => TRUE);

CREATE INDEX idx_pr_events_category ON pr_events (event_category, time DESC);
CREATE INDEX idx_pr_events_importance ON pr_events (importance_score, time DESC);
CREATE INDEX idx_pr_events_strategy ON pr_events (related_strategy, time DESC) WHERE related_strategy IS NOT NULL;

COMMENT ON TABLE pr_events IS 'Public relations narratives generated from system events';
