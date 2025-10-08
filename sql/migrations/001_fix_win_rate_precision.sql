-- Migration: Fix win_rate column precision
-- Date: 2025-10-08
-- Issue: win_rate is stored as percentage (0-100) but column is NUMERIC(5,4) which maxes at 9.9999
-- Fix: Change to NUMERIC(5,2) to allow 0.00-100.00%

BEGIN;

-- Alter the column type
ALTER TABLE strategy_performance
ALTER COLUMN win_rate TYPE NUMERIC(5, 2);

COMMIT;

-- Verify the change
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name = 'strategy_performance' AND column_name = 'win_rate';
