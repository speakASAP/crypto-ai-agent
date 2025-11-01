#!/bin/bash
# Production Logs Diagnostic Script
# Run this on the production server to diagnose why logs are empty

echo "=== Production Logs Diagnostic ==="
echo ""

echo "1. Checking if backend container is running..."
if docker ps | grep -q crypto-ai-backend; then
    echo "✅ Backend container is running"
else
    echo "❌ Backend container is NOT running"
    exit 1
fi

echo ""
echo "2. Checking logs directory on host..."
ls -la ~/crypto-ai-agent/logs/

echo ""
echo "3. Checking logs directory inside container..."
docker exec crypto-ai-backend ls -la /app/logs/ 2>&1

echo ""
echo "4. Checking if log file exists inside container..."
docker exec crypto-ai-backend test -f /app/logs/crypto_agent.log && echo "✅ Log file exists" || echo "❌ Log file does NOT exist"

echo ""
echo "5. Checking log file content (last 20 lines)..."
docker exec crypto-ai-backend tail -20 /app/logs/crypto_agent.log 2>&1 || echo "No log file or unable to read"

echo ""
echo "6. Testing volume mount by creating test file..."
docker exec crypto-ai-backend touch /app/logs/test_mount.txt 2>&1
if [ -f ~/crypto-ai-agent/logs/test_mount.txt ]; then
    echo "✅ Volume mount is working"
    rm ~/crypto-ai-agent/logs/test_mount.txt
    docker exec crypto-ai-backend rm /app/logs/test_mount.txt
else
    echo "❌ Volume mount is NOT working"
fi

echo ""
echo "7. Checking container user and permissions..."
docker exec crypto-ai-backend whoami
docker exec crypto-ai-backend id
docker exec crypto-ai-backend ls -la /app/ | grep logs

echo ""
echo "8. Checking environment variables related to logging..."
docker exec crypto-ai-backend env | grep -i "LOG\|DEBUG"

echo ""
echo "9. Checking container logs (stdout/stderr)..."
docker logs crypto-ai-backend --tail 30

echo ""
echo "10. Checking for permission errors in container logs..."
docker logs crypto-ai-backend 2>&1 | grep -i "permission\|denied\|log" | tail -10

echo ""
echo "=== Diagnostic Complete ==="
echo ""
echo "Next steps:"
echo "- If volume mount is not working, check docker-compose.yml"
echo "- If permission errors, run: chmod 755 ~/crypto-ai-agent/logs"
echo "- If logs are in container but not on host, restart container: docker compose restart backend"

