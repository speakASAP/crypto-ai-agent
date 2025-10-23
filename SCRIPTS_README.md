# Crypto AI Agent - Management Scripts

This directory contains scripts to easily manage the Crypto AI Agent application.

## Available Scripts

### 🚀 `./start.sh`

Starts the entire application stack:

- **Backend (FastAPI)** on port 8000
- **Frontend (Next.js)** on port 3000
- **Database (SQLite)** initialization
- **Dependencies** installation

**Usage:**

```bash
./start.sh
```

**What it does:**

- Checks prerequisites (Python 3, Node.js, npm)
- Verifies .env configuration
- Creates Python virtual environment (if not exists)
- Installs all dependencies in virtual environment
- Starts backend using virtual environment
- Starts frontend services
- Provides status and access URLs

### 🛑 `./stop.sh`

Stops all running services and cleans up processes.

**Usage:**

```bash
./stop.sh
```

**What it does:**

- Stops backend (FastAPI) service
- Stops frontend (Next.js) service
- Kills any processes on ports 3000 and 8000
- Cleans up process files
- Optionally cleans up log files

### 📊 `./status.sh`

Checks the status of all services and provides detailed information.

**Usage:**

```bash
./status.sh
```

**What it shows:**

- Service status (running/stopped)
- Process information (PID, CPU, Memory)
- Health checks for each service
- Database status
- Log file information
- Environment configuration
- Virtual environment status
- Dependencies status

## Quick Start

1. **Start the application:**

   ```bash
   ./start.sh
   ```

2. **Check status:**

   ```bash
   ./status.sh
   ```

3. **Stop the application:**

   ```bash
   ./stop.sh
   ```

## Access URLs

Once started, you can access:

- **Frontend**: <http://localhost:3000>
- **Backend API**: <http://localhost:8000>
- **API Documentation**: <http://localhost:8000/docs>

## Logs

All logs are stored in the `logs/` directory:

- `logs/backend.log` - Backend server logs
- `logs/frontend.log` - Frontend server logs
- `logs/backend_install.log` - Backend dependency installation logs
- `logs/frontend_install.log` - Frontend dependency installation logs
- `logs/status.txt` - Current service status

## Troubleshooting

### Port Already in Use

If you get "port already in use" errors:

```bash
./stop.sh  # Stop all services
./start.sh # Start fresh
```

### Services Not Starting

1. Check logs in the `logs/` directory
2. Verify .env file exists and is properly configured
3. Ensure Python 3.12+ and Node.js 18+ are installed
4. Run `./status.sh` to see detailed status

### Dependencies Issues

The scripts automatically install dependencies, but if you encounter issues:

```bash
# Backend dependencies (virtual environment)
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
```

## Requirements

- **Python 3.12+**
- **Node.js 18+**
- **npm**
- **macOS/Linux** (scripts use bash)

## Security Notes

- Make sure to configure `JWT_SECRET` in your `.env` file
- The scripts will warn you if JWT_SECRET is not properly configured
- Never commit your `.env` file to version control

## Script Features

- **Color-coded output** for easy reading
- **Automatic dependency installation**
- **Port conflict resolution**
- **Process management**
- **Health checks**
- **Comprehensive status reporting**
- **Log management**
- **Error handling**
