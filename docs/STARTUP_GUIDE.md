# 🚀 Crypto AI Agent - Quick Start Guide

## Quick Start

### Start the Application (development scripts)

```bash
./start.sh
```

### Start the Application (production via Docker)

```bash
# Ensure .env contains ENVIRONMENT=production
./start.sh --env production
```

### Stop the Application

```bash
./stop.sh                 # development
./stop.sh --env production # production (docker compose down)
```text
 
### Restart

```bash
# Development
./start.sh restart
./start.sh restart --service backend

# Production
./start.sh --env production restart
./start.sh --env production restart --service backend
```

### Per-service operations

```bash
# Start a single service
./start.sh --service backend                    # development
./start.sh --env production --service backend   # production (docker compose up backend)
```

### Environment selection

- Set `NODE_ENV=development|production` in `.env` (default: development).
- Override per command with `--env production`.

## What the Scripts Do

### `start.sh`

- ✅ Checks Python 3.12 is available
- ✅ Verifies .env file exists
- ✅ Cleans up any existing processes
- ✅ Starts the AI agent in background
- ✅ Starts the UI dashboard on port 8501
- ✅ Monitors both processes
- ✅ Provides status information

### `stop.sh`

- ✅ Stops all agent processes
- ✅ Stops the UI dashboard
- ✅ Cleans up port 8501
- ✅ Provides cleanup confirmation

## Access Points

- **🌐 UI Dashboard**: <http://localhost:8501>
- **📊 Agent Logs**: `logs/agent.log`

## Features Available

- **Portfolio Management**: Multi-currency support (USD, EUR, CZK)
- **Symbol Management**: Add/remove cryptocurrency symbols
- **News Analysis**: Real-time sentiment monitoring
- **Price Alerts**: Customizable notifications
- **Data Visualization**: Comprehensive analytics

## Troubleshooting

### If the script fails to start

1. Check Python 3.12 is installed: `python3.12 --version`
2. Verify .env file exists and has valid API keys
3. Check logs for specific error messages

### If ports are in use

- The script automatically cleans up ports
- If issues persist, run `./stop.sh` first

### SSL Certificate Issues

- The application will work with fallback currency rates
- WebSocket connections may be limited due to SSL issues
- Consider using Docker Compose for production deployment

## Manual Start (Alternative)

If you prefer to start components manually:

```bash
# Terminal 1 - Start Agent
cd crypto-ai-agent
python3.12 agent_advanced.py

# Terminal 2 - Start UI
cd crypto-ai-agent
python3.12 -m streamlit run ui_dashboard/app.py --server.port 8501
```

## Production Deployment

For production, use the scripts (docker compose under the hood):

```bash
./start.sh --env production
./status.sh --env production --logs 100
```text
