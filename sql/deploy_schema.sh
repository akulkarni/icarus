#!/bin/bash
# Deploy database schema to Tiger Cloud

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    echo "Please copy .env.template to .env and fill in your Tiger Cloud credentials"
    exit 1
fi

# Check required variables
if [ -z "$TIGER_HOST" ] || [ -z "$TIGER_PASSWORD" ]; then
    echo "Error: TIGER_HOST and TIGER_PASSWORD must be set in .env"
    exit 1
fi

# Build connection string
PGPASSWORD=$TIGER_PASSWORD

echo "Deploying schema to Tiger Cloud..."
echo "Host: $TIGER_HOST"
echo "Database: ${TIGER_DATABASE:-tsdb}"
echo ""

# Deploy schema
psql "postgresql://${TIGER_USER:-tsdbadmin}:${TIGER_PASSWORD}@${TIGER_HOST}:${TIGER_PORT:-5432}/${TIGER_DATABASE:-tsdb}?sslmode=require" \
    -f sql/schema.sql

echo ""
echo "✓ Schema deployed successfully!"
echo ""
echo "Verifying hypertables..."
psql "postgresql://${TIGER_USER:-tsdbadmin}:${TIGER_PASSWORD}@${TIGER_HOST}:${TIGER_PORT:-5432}/${TIGER_DATABASE:-tsdb}?sslmode=require" \
    -c "SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY hypertable_name;"

echo ""
echo "✓ Deployment complete!"
