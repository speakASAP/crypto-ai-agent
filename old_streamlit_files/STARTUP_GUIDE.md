# 🚀 Crypto AI Agent - Quick Start Guide

## Quick Start

### Start the Application

```bash
./start.sh
```

### Stop the Application

```bash
./stop.sh
```

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
- **🖥️ UI Logs**: `logs/ui.log`

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

For production, use Docker Compose:

```bash
docker compose up --build
```

---

**Happy Trading! 📈**
