# Production Logs Diagnostic Guide

## Issue

Logs directory exists but is empty: `~/crypto-ai-agent/logs/`

## Diagnostic Steps

### 1. Check if logs exist inside the container

```bash
# Check logs directory inside the backend container
docker exec crypto-ai-backend ls -la /app/logs

# Check if log file exists inside container
docker exec crypto-ai-backend ls -la /app/logs/crypto_agent.log

# Check log file content inside container
docker exec crypto-ai-backend cat /app/logs/crypto_agent.log | tail -50
```text

### 2. Check container logs (stdout/stderr)

```bash
# Check backend container logs
docker logs crypto-ai-backend --tail 100

# Check for any errors related to logging
docker logs crypto-ai-backend 2>&1 | grep -i "log\|error\|permission"
```text

### 3. Verify volume mount is working

```bash
# Check if the mount is actually working
docker exec crypto-ai-backend touch /app/logs/test_file.txt

# Check if file appears on host
ls -la ~/crypto-ai-agent/logs/test_file.txt

# Clean up test file
rm ~/crypto-ai-agent/logs/test_file.txt
docker exec crypto-ai-backend rm /app/logs/test_file.txt
```text

### 4. Check directory permissions

```bash
# Check permissions on host logs directory
ls -la ~/crypto-ai-agent/logs

# Check what user the container is running as
docker exec crypto-ai-backend whoami
docker exec crypto-ai-backend id

# Check ownership of /app/logs inside container
docker exec crypto-ai-backend ls -la /app/ | grep logs
```text

### 5. Check environment variables

```bash
# Check if LOG_FILE is set in container
docker exec crypto-ai-backend env | grep -i log

# Check if LOG_LEVEL is set
docker exec crypto-ai-backend env | grep LOG_LEVEL
```text

### 6. Test logger initialization

```bash
# Try to manually create a log file to test permissions
docker exec crypto-ai-backend bash -c "echo 'Test log entry' > /app/logs/test.log"

# Check if it worked
cat ~/crypto-ai-agent/logs/test.log
```text

## Common Issues and Solutions

### Issue 1: Logs are in container but not on host
**Symptom**: Logs exist inside container but not visible on host
**Solution**: Volume mount issue - check docker-compose.yml volume configuration

### Issue 2: Permission denied errors
**Symptom**: Container can't write to mounted directory
**Solution**: 
```bash
# Fix permissions on host
sudo chown -R $USER:$USER ~/crypto-ai-agent/logs
chmod -R 755 ~/crypto-ai-agent/logs
```text

### Issue 3: Logger not initializing
**Symptom**: No logs anywhere, even in container
**Solution**: Check if logger is being imported/initialized in main.py

### Issue 4: Wrong log path
**Symptom**: Logs written to different location
**Solution**: Check LOG_FILE environment variable

## Quick Fix Commands

```bash
# Ensure logs directory exists and has correct permissions
mkdir -p ~/crypto-ai-agent/logs
chmod 755 ~/crypto-ai-agent/logs

# Restart backend container to reinitialize logging
cd ~/crypto-ai-agent
docker compose restart backend

# Check logs after restart
docker logs crypto-ai-backend --tail 50
ls -la ~/crypto-ai-agent/logs
```text

