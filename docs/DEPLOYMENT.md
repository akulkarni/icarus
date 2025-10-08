# Deployment Guide

## Production Deployment

### Requirements

**System**:
- Ubuntu 20.04 LTS or later (recommended)
- 2+ CPU cores
- 4GB+ RAM
- 20GB+ disk space
- Stable internet connection

**Software**:
- Python 3.11+
- systemd (for service management)
- PostgreSQL client tools
- Git

**Services**:
- Tiger Cloud account with TimescaleDB database
- Binance account (for live trading)

### Installation Steps

#### 1. Create Deploy User

Create a dedicated user for running Icarus:

```bash
# Create user
sudo useradd -m -s /bin/bash icarus

# Add to necessary groups (optional)
sudo usermod -aG docker icarus  # If using Docker

# Switch to icarus user
sudo su - icarus
```

#### 2. Clone Repository

```bash
# Clone to /opt/icarus (or your preferred location)
cd /opt
sudo git clone <repo-url> icarus
sudo chown -R icarus:icarus icarus
cd icarus
```

#### 3. Setup Python Environment

```bash
# Install Python 3.11 if not available
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### 4. Configure Environment

```bash
# Create .env file from template
cp .env.example .env

# Edit .env with production credentials
nano .env
```

**Production .env**:
```bash
# Tiger Cloud Database
TIGER_HOST=your-service.tiger.cloud
TIGER_PORT=5432
TIGER_DATABASE=tsdb
TIGER_USER=tsdbadmin
TIGER_PASSWORD=your_secure_password
TIGER_SERVICE_ID=your_service_id

# Binance API (for live trading)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
```

**Important**: Set strict file permissions:
```bash
chmod 600 .env
chown icarus:icarus .env
```

#### 5. Configure Application

Edit `config/app.yaml` for production:

```yaml
# Production configuration
trading:
  mode: paper  # Start with paper, switch to live after testing
  initial_capital: 10000
  position_size_pct: 10  # Conservative for production

risk:
  max_position_size_pct: 10
  max_daily_loss_pct: 2  # Conservative
  max_exposure_pct: 60

logging:
  level: INFO  # Use WARNING or ERROR for less verbose logs
  format: json
  file: /var/log/icarus/icarus.log

# ... rest of config
```

#### 6. Deploy Database Schema

```bash
# Deploy schema to Tiger Cloud database
./sql/deploy_schema.sh

# Verify tables were created
psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "\dt"
```

#### 7. Test Run

Test the system before setting up as a service:

```bash
# Activate virtual environment
source venv/bin/activate

# Run the system
python src/main.py
```

Verify:
- All agents start successfully
- Database connections work
- Market data is received
- No errors in logs

Press `Ctrl+C` to stop after verification.

### Systemd Service Setup

Create a systemd service for automatic startup and management.

#### 1. Create Service File

```bash
sudo nano /etc/systemd/system/icarus.service
```

**Service Configuration**:
```ini
[Unit]
Description=Icarus Trading System
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=icarus
Group=icarus
WorkingDirectory=/opt/icarus
Environment="PATH=/opt/icarus/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/icarus/.env

# Start command
ExecStart=/opt/icarus/venv/bin/python src/main.py

# Restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Resource limits (optional)
MemoryLimit=4G
CPUQuota=200%

# Logging
StandardOutput=append:/var/log/icarus/output.log
StandardError=append:/var/log/icarus/error.log
SyslogIdentifier=icarus

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

#### 2. Setup Log Directory

```bash
# Create log directory
sudo mkdir -p /var/log/icarus

# Set ownership
sudo chown -R icarus:icarus /var/log/icarus

# Set permissions
sudo chmod 755 /var/log/icarus
```

#### 3. Enable and Start Service

```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable icarus

# Start service
sudo systemctl start icarus

# Check status
sudo systemctl status icarus
```

#### 4. Service Management Commands

```bash
# Start service
sudo systemctl start icarus

# Stop service
sudo systemctl stop icarus

# Restart service
sudo systemctl restart icarus

# Check status
sudo systemctl status icarus

# View logs (systemd journal)
sudo journalctl -u icarus -f

# View logs (application logs)
tail -f /var/log/icarus/output.log
tail -f /opt/icarus/logs/icarus.log
```

### Nginx Reverse Proxy (Optional)

If you want to expose the dashboard with a domain name and SSL:

#### 1. Install Nginx

```bash
sudo apt update
sudo apt install nginx
```

#### 2. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/icarus
```

**Nginx Configuration**:
```nginx
# HTTP server (redirects to HTTPS)
server {
    listen 80;
    listen [::]:80;
    server_name icarus.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name icarus.example.com;

    # SSL certificates (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/icarus.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/icarus.example.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logging
    access_log /var/log/nginx/icarus_access.log;
    error_log /var/log/nginx/icarus_error.log;

    # Proxy to FastAPI
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

#### 3. Enable Site

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/icarus /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

#### 4. Setup SSL with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d icarus.example.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### Monitoring

#### 1. System Monitoring

**Check Service Status**:
```bash
# Service status
sudo systemctl status icarus

# Recent logs
sudo journalctl -u icarus -n 50

# Follow logs in real-time
sudo journalctl -u icarus -f
```

**Application Logs**:
```bash
# Application log
tail -f /opt/icarus/logs/icarus.log

# JSON formatted (if using jq)
tail -f /opt/icarus/logs/icarus.log | jq .

# Filter by log level
tail -f /opt/icarus/logs/icarus.log | grep ERROR
```

**System Resources**:
```bash
# CPU and memory usage
top -p $(pgrep -f "python src/main.py")

# Detailed process info
ps aux | grep "python src/main.py"

# Memory usage
free -h

# Disk usage
df -h
```

#### 2. Health Check Script

Create a monitoring script:

```bash
nano /opt/icarus/scripts/monitor.sh
```

```bash
#!/bin/bash

# Icarus Health Monitor
echo "=== Icarus Health Check ==="
echo "Timestamp: $(date)"
echo ""

# Check if service is running
if systemctl is-active --quiet icarus; then
    echo "✅ Service: Running"
else
    echo "❌ Service: Stopped"
    exit 1
fi

# Check API health
if curl -f -s http://localhost:8000/api/health > /dev/null; then
    echo "✅ API: Responding"
else
    echo "❌ API: Not responding"
fi

# Check database connectivity
if PGPASSWORD=$TIGER_PASSWORD psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -c "SELECT 1" > /dev/null 2>&1; then
    echo "✅ Database: Connected"
else
    echo "❌ Database: Connection failed"
fi

# Check recent activity (last 5 minutes)
RECENT_TRADES=$(PGPASSWORD=$TIGER_PASSWORD psql -h $TIGER_HOST -U $TIGER_USER -d $TIGER_DATABASE -t -c "SELECT COUNT(*) FROM trades WHERE time > NOW() - INTERVAL '5 minutes'" 2>/dev/null | xargs)
echo "📊 Recent trades (5min): $RECENT_TRADES"

echo ""
echo "=== Resource Usage ==="
ps aux | grep "python src/main.py" | grep -v grep | awk '{printf "CPU: %s%%  Memory: %s%%\n", $3, $4}'
```

Make executable:
```bash
chmod +x /opt/icarus/scripts/monitor.sh
```

Run periodically:
```bash
# Add to crontab
crontab -e

# Run every 5 minutes
*/5 * * * * /opt/icarus/scripts/monitor.sh >> /var/log/icarus/monitor.log 2>&1
```

#### 3. Alerting (Optional)

Setup email alerts for critical issues:

```bash
# Install mailutils
sudo apt install mailutils

# Create alert script
nano /opt/icarus/scripts/alert.sh
```

```bash
#!/bin/bash

SERVICE="icarus"
EMAIL="admin@example.com"

if ! systemctl is-active --quiet $SERVICE; then
    echo "ALERT: Icarus service is down!" | mail -s "Icarus Down" $EMAIL
fi
```

Add to crontab:
```bash
*/5 * * * * /opt/icarus/scripts/alert.sh
```

### Backup

#### 1. Database Backup

Create backup script:

```bash
nano /opt/icarus/scripts/backup_db.sh
```

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/opt/icarus/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/icarus_backup_$DATE.sql"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Perform backup
PGPASSWORD=$TIGER_PASSWORD pg_dump \
    -h $TIGER_HOST \
    -U $TIGER_USER \
    -d $TIGER_DATABASE \
    -F c \
    -f $BACKUP_FILE

# Compress
gzip $BACKUP_FILE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

Make executable and schedule:
```bash
chmod +x /opt/icarus/scripts/backup_db.sh

# Add to crontab (daily at 2 AM)
crontab -e
0 2 * * * /opt/icarus/scripts/backup_db.sh >> /var/log/icarus/backup.log 2>&1
```

#### 2. Configuration Backup

```bash
# Backup config and environment
tar -czf /opt/icarus/backups/config_$(date +%Y%m%d).tar.gz \
    /opt/icarus/config/ \
    /opt/icarus/.env

# Keep last 30 days
find /opt/icarus/backups -name "config_*.tar.gz" -mtime +30 -delete
```

#### 3. Restore from Backup

```bash
# Restore database
gunzip -c /opt/icarus/backups/icarus_backup_20251008_020000.sql.gz | \
PGPASSWORD=$TIGER_PASSWORD pg_restore \
    -h $TIGER_HOST \
    -U $TIGER_USER \
    -d $TIGER_DATABASE \
    --clean --if-exists
```

### Updates and Deployment

#### 1. Update Script

Create deployment script:

```bash
nano /opt/icarus/scripts/deploy.sh
```

```bash
#!/bin/bash
set -e

echo "=== Icarus Deployment Script ==="
echo "Timestamp: $(date)"
echo ""

# Change to project directory
cd /opt/icarus

# Stash any local changes
echo "Stashing local changes..."
git stash

# Pull latest code
echo "Pulling latest code from main..."
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "Running migrations..."
python scripts/run_migration.py

# Run tests (optional)
echo "Running tests..."
pytest tests/ -v || echo "⚠️  Tests failed, but continuing..."

# Restart service
echo "Restarting service..."
sudo systemctl restart icarus

# Wait for service to start
sleep 5

# Check service status
if systemctl is-active --quiet icarus; then
    echo "✅ Deployment successful!"
    echo "Service status: Running"
else
    echo "❌ Deployment failed!"
    echo "Service did not start properly"
    sudo systemctl status icarus
    exit 1
fi

# Check API health
sleep 5
if curl -f -s http://localhost:8000/api/health > /dev/null; then
    echo "✅ API health check passed"
else
    echo "⚠️  API health check failed"
fi

echo ""
echo "=== Deployment Complete ==="
```

Make executable:
```bash
chmod +x /opt/icarus/scripts/deploy.sh
sudo chown icarus:icarus /opt/icarus/scripts/deploy.sh
```

#### 2. Zero-Downtime Deployment (Advanced)

For zero-downtime deployments, run multiple instances behind a load balancer:

1. Deploy new version to instance 2
2. Test instance 2 is healthy
3. Switch load balancer to instance 2
4. Deploy new version to instance 1
5. Switch load balancer to both instances

### Security

#### 1. Firewall Configuration

```bash
# Install UFW
sudo apt install ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (if using Nginx)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

#### 2. API Key Security

**Best Practices**:
- Store API keys only in `.env` file
- Set restrictive file permissions (600)
- Never commit `.env` to Git
- Rotate keys regularly
- Use Binance API restrictions:
  - Enable withdrawal whitelist
  - Restrict to specific IPs
  - Limit permissions to trading only

**Binance API Security Settings**:
- Enable "Enable Spot & Margin Trading" only
- Disable "Enable Withdrawals"
- Add your server IP to IP whitelist
- Use separate API keys for testnet and mainnet

#### 3. Database Security

- Use strong passwords (minimum 16 characters)
- Enable SSL/TLS connections
- Restrict IP access in Tiger Cloud console
- Regularly review access logs
- Enable audit logging

#### 4. System Security

```bash
# Keep system updated
sudo apt update && sudo apt upgrade -y

# Enable automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Disable root SSH login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart sshd

# Setup fail2ban (brute force protection)
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Troubleshooting Deployment

#### Service won't start

```bash
# Check service status
sudo systemctl status icarus

# View logs
sudo journalctl -u icarus -n 100

# Check for syntax errors
python -m py_compile src/main.py

# Test configuration
python -c "import yaml; print(yaml.safe_load(open('config/app.yaml')))"

# Check file permissions
ls -la /opt/icarus/.env
ls -la /var/log/icarus/
```

#### High memory usage

```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Restart service
sudo systemctl restart icarus

# Consider increasing swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### Database connection issues

```bash
# Test database connection
PGPASSWORD=$TIGER_PASSWORD psql \
    -h $TIGER_HOST \
    -U $TIGER_USER \
    -d $TIGER_DATABASE \
    -c "SELECT version();"

# Check network connectivity
ping $TIGER_HOST
telnet $TIGER_HOST 5432

# Verify credentials
cat /opt/icarus/.env | grep TIGER
```

## Docker Deployment (Alternative)

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Run as non-root user
RUN useradd -m icarus && chown -R icarus:icarus /app
USER icarus

# Command
CMD ["python", "src/main.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  icarus:
    build: .
    container_name: icarus-trading
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Docker Commands

```bash
# Build image
docker-compose build

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down

# Restart service
docker-compose restart

# Update and restart
git pull
docker-compose build
docker-compose up -d
```

## Conclusion

Your Icarus trading system is now deployed and running in production!

**Next steps**:
- Monitor logs and performance
- Start with paper trading and test thoroughly
- Gradually transition to live trading with small positions
- Set up alerting and monitoring
- Regular backups and updates
- Review security settings regularly

For issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
