# Plan: Figure Out Deployment

## Overview
Document deployment options and provide a deployment guide for the Live Battlefield application. Recommended: Fly.io for simplicity with Docker support.

## References
- Original TODO: docs/TODO.md item 48

## Current State
- Application runs locally with Docker Compose
- No deployment documentation or configuration

## Deployment Options Comparison

| Platform | Difficulty | Cost | Docker Support | Database | Recommended For |
|----------|------------|------|----------------|----------|-----------------|
| Fly.io | Medium | Free tier | Native | Managed Postgres | **Recommended** |
| Render | Medium | Free tier | Docker | Managed Postgres | Good alternative |
| Railway | Medium | Paid | Docker | Managed Postgres | Good DX |
| AWS ECS | High | Pay | Native | RDS | Enterprise |
| DigitalOcean | Medium | Paid | Docker | Managed | Good alternative |
| Railway | Medium | Paid | Docker | Managed | Good alternative |

## Recommended: Fly.io Deployment

### Step 1: Install Fly CLI
```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

### Step 2: Login to Fly
```bash
fly auth login
```

### Step 3: Create Fly App
```bash
fly launch --name live-battlefield --org personal
```

This creates:
- `fly.toml` - Fly configuration
- `.fly/` - Fly directory

### Step 4: Configure fly.toml
Update `fly.toml`:
```toml
app = "live-battlefield"

[build]
  dockerfile = "Dockerfile"

[env]
  TELEGRAM_BOT_TOKEN = "your_bot_token"

[[services]]
  http_checks = []
  internal_port = 8000
  processes = ["app"]
  protocol = "tcp"
  script_check = []

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

[[mounts]]
  source = "data"
  destination = "/data"
```

### Step 5: Add PostgreSQL
```bash
fly postgres create --name battlefield-db
fly postgres attach battlefield-db
```

This sets `DATABASE_URL` automatically.

### Step 6: Add Secrets
```bash
# Set Telegram bot token
fly secrets set TELEGRAM_BOT_TOKEN=your_token_here

# Optional: Set admin credentials
fly secrets set ADMIN_USERNAME=admin
fly secrets set ADMIN_PASSWORD=your_secure_password
```

### Step 7: Deploy
```bash
fly deploy
```

### Step 8: Scale
```bash
# Check status
fly status

# Scale to 2 instances
fly scale count 2
```

## Alternative: Render.com Deployment

### Step 1: Create render.yaml
Create `render.yaml`:
```yaml
services:
  - type: web
    name: live-battlefield
    dockerCommand: tail -f /dev/null  # Keep container running
    dockerfilePath: Dockerfile
    envVars:
      - key: TELEGRAM_BOT_TOKEN
        value: your_token
      - key: DATABASE_URL
        fromDatabase:
          name: battlefield-db
          property: connectionString
    autoDeploy: true

databases:
  - name: battlefield-db
    databaseName: battleship
    plan: free
```

### Step 2: Connect GitHub
1. Go to render.com
2. Connect GitHub repository
3. Create new Web Service
4. Configure with the settings above

## Alternative: Docker Compose on VPS

### Step 1: Server Requirements
- Ubuntu 20.04+ VPS
- Docker & Docker Compose installed

### Step 2: Create production docker-compose.yml
Create `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/battleship
    depends_on:
      - postgres
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=battleship
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### Step 3: Run on VPS
```bash
# Copy files to server
scp -r . user@your-vps:/opt/live-battlefield

# SSH to server
ssh user@your-vps

# Set environment
export TELEGRAM_BOT_TOKEN=your_token
export POSTGRES_PASSWORD=secure_password

# Start
docker compose -f docker-compose.prod.yml up -d
```

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Your Telegram bot token |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ADMIN_USERNAME` | No | Admin panel username (if auth added) |
| `ADMIN_PASSWORD` | No | Admin panel password |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

## Telegram Webhook Configuration

For production, consider using webhooks instead of polling:
```python
# In app/main.py
from telegram.ext import Application

# Set webhook (done automatically by telegram bot API)
# Remove: app = ApplicationBuilder().token(TOKEN).build()
# Add webhook:
async def set_webhook():
    await application.bot.set_webhook(f"https://your-domain.com/webhook")
```

## Health Checks

Add health check endpoint:
```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

Configure in Fly.toml:
```toml
[[services]]
  [services.http_checks]
    interval = 15
    timeout = 5
    method = "get"
    path = "/health"
```

## Monitoring

### Option 1: Fly.io Metrics
```bash
fly metrics
```

### Option 2: Prometheus + Grafana
Add to docker-compose for self-hosted monitoring.

## Rollback

```bash
# Fly.io
fly deploy --rollback

# Docker Compose
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## Files to Create
1. `docker-compose.prod.yml` (for VPS)
2. `render.yaml` (for Render)

## Files to Modify
1. `.env` - Keep local only, don't commit tokens

## Testing Production Build Locally
```bash
# Build production image
docker build -t live-battlefield:latest .

# Run with production config
docker run -p 8000:8000 \
  -e TELEGRAM_BOT_TOKEN=test \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/battleship \
  live-battlefield:latest
```
