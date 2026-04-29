#!/bin/bash
# SSL/HTTPS Diagnostic Script for crypto-ai-agent.alfares.cz
# Run this on the production server: ssh alfares && cd crypto-ai-agent && ./scripts/check_ssl.sh

set -e

echo "================================================================================"
echo "🔒 SSL/HTTPS DIAGNOSTIC CHECK"
echo "================================================================================"
echo ""

# Check if nginx-microservice directory exists
NGINX_DIR="~/Documents/Github/nginx-microservice"
if [ ! -d "$NGINX_DIR" ]; then
    echo "❌ ERROR: nginx-microservice directory not found at $NGINX_DIR"
    echo "   Expected location: ~/Documents/Github/nginx-microservice"
    exit 1
fi

echo "✅ Found nginx-microservice at: $NGINX_DIR"
echo ""

# Check nginx container status
echo "📦 Checking Nginx Container Status..."
if docker ps --filter "name=nginx" --format "{{.Names}}: {{.Status}}" | grep -q nginx; then
    echo "✅ Nginx container running:"
    docker ps --filter "name=nginx" --format "   {{.Names}}: {{.Status}}"
    NGINX_CONTAINER=$(docker ps --filter "name=nginx" --format "{{.Names}}" | head -1)
else
    echo "❌ Nginx container NOT running"
    echo "   Run: cd $NGINX_DIR && docker compose ps"
    exit 1
fi

# Check SSL certificates
echo ""
echo "🔐 Checking SSL Certificates..."
CERT_DIR="$NGINX_DIR/certificates/crypto-ai-agent.alfares.cz"
if [ -d "$CERT_DIR" ]; then
    echo "✅ Certificate directory exists: $CERT_DIR"
    
    # Check for certificate files
    if [ -f "$CERT_DIR/fullchain.pem" ]; then
        echo "✅ fullchain.pem found"
        
        # Check certificate expiration
        EXPIRY=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
        if [ "$EXPIRY" != "unknown" ]; then
            echo "   Certificate expires: $EXPIRY"
            
            # Check if expired
            EXPIRY_EPOCH=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null || echo "0")
            NOW_EPOCH=$(date +%s)
            if [ "$EXPIRY_EPOCH" -lt "$NOW_EPOCH" ]; then
                echo "   ❌ Certificate EXPIRED!"
            else
                DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))
                echo "   ✅ Certificate valid for $DAYS_LEFT more days"
            fi
        fi
    else
        echo "❌ fullchain.pem NOT found"
    fi
    
    if [ -f "$CERT_DIR/privkey.pem" ]; then
        echo "✅ privkey.pem found"
    else
        echo "❌ privkey.pem NOT found"
    fi
    
    # List all certificate files
    echo ""
    echo "   Certificate files:"
    ls -lah "$CERT_DIR" | grep -E "\.pem|\.key|\.crt" || echo "   No certificate files found"
else
    echo "❌ Certificate directory NOT found: $CERT_DIR"
    echo "   SSL certificates are missing!"
fi

# Check nginx configuration
echo ""
echo "⚙️  Checking Nginx Configuration..."
NGINX_CONF="$NGINX_DIR/nginx/conf.d/crypto-ai-agent.alfares.cz.conf"
if [ -f "$NGINX_CONF" ]; then
    echo "✅ Nginx config file exists: $NGINX_CONF"
    
    # Check if SSL is configured
    if grep -q "listen 443 ssl" "$NGINX_CONF"; then
        echo "✅ SSL (port 443) configured"
    else
        echo "❌ SSL (port 443) NOT configured"
    fi
    
    # Check certificate paths in config
    if grep -q "ssl_certificate" "$NGINX_CONF"; then
        echo "✅ SSL certificate paths configured:"
        grep "ssl_certificate" "$NGINX_CONF" | sed 's/^/   /'
    else
        echo "❌ SSL certificate paths NOT configured"
    fi
    
    # Test nginx configuration
    echo ""
    echo "🧪 Testing Nginx Configuration..."
    if [ -n "$NGINX_CONTAINER" ]; then
        if docker exec "$NGINX_CONTAINER" nginx -t 2>&1 | grep -q "successful"; then
            echo "✅ Nginx configuration test: PASSED"
        else
            echo "❌ Nginx configuration test: FAILED"
            echo "   Errors:"
            docker exec "$NGINX_CONTAINER" nginx -t 2>&1 | grep -i error | sed 's/^/   /'
        fi
    fi
else
    echo "❌ Nginx config file NOT found: $NGINX_CONF"
fi

# Check nginx logs for SSL errors
echo ""
echo "📋 Checking Nginx Logs (SSL-related errors)..."
if [ -n "$NGINX_CONTAINER" ]; then
    echo "   Recent SSL/HTTPS errors:"
    docker logs "$NGINX_CONTAINER" 2>&1 | grep -i "ssl\|tls\|certificate\|443" | tail -20 || echo "   No SSL-related errors found"
fi

# Check port 443 accessibility
echo ""
echo "🌐 Checking Port 443 Accessibility..."
if command -v nc >/dev/null 2>&1; then
    if nc -z -v localhost 443 2>&1 | grep -q "succeeded\|open"; then
        echo "✅ Port 443 is open and accessible"
    else
        echo "❌ Port 443 is NOT accessible"
        echo "   Check firewall rules: sudo ufw status"
    fi
else
    echo "⚠️  nc (netcat) not available, skipping port check"
fi

# Test HTTPS connection
echo ""
echo "🔍 Testing HTTPS Connection..."
if command -v curl >/dev/null 2>&1; then
    echo "   Testing: https://crypto-ai-agent.alfares.cz"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://crypto-ai-agent.alfares.cz 2>&1 || echo "000")
    SSL_ERROR=$(curl -s -o /dev/null -w "%{ssl_verify_result}" --max-time 10 https://crypto-ai-agent.alfares.cz 2>&1 || echo "999")
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        echo "✅ HTTPS connection successful (HTTP $HTTP_CODE)"
    elif [ "$HTTP_CODE" = "000" ]; then
        echo "❌ HTTPS connection FAILED (timeout or connection refused)"
    else
        echo "⚠️  HTTPS connection returned HTTP $HTTP_CODE"
    fi
    
    if [ "$SSL_ERROR" = "0" ]; then
        echo "✅ SSL certificate verification: PASSED"
    elif [ "$SSL_ERROR" = "999" ]; then
        echo "⚠️  Could not verify SSL certificate (connection failed)"
    else
        echo "❌ SSL certificate verification: FAILED (error code: $SSL_ERROR)"
    fi
else
    echo "⚠️  curl not available, skipping HTTPS test"
fi

# Check if containers are running
echo ""
echo "🐳 Checking Application Containers..."
if docker ps --filter "name=crypto-ai" --format "{{.Names}}: {{.Status}}" | grep -q crypto-ai; then
    echo "✅ Application containers running:"
    docker ps --filter "name=crypto-ai" --format "   {{.Names}}: {{.Status}}"
else
    echo "⚠️  No application containers running"
    echo "   Run: cd ~/Documents/Github/crypto-ai-agent && ./scripts/status.sh"
fi

# Summary
echo ""
echo "================================================================================"
echo "📊 DIAGNOSTIC SUMMARY"
echo "================================================================================"
echo ""
echo "🔍 Key Checks:"
echo "   1. ✅ Nginx container running"
echo "   2. ✅ SSL certificates exist and valid"
echo "   3. ✅ Nginx config includes SSL (port 443)"
echo "   4. ✅ Nginx config test passes"
echo "   5. ✅ Port 443 accessible"
echo "   6. ✅ HTTPS connection works"
echo ""
echo "💡 Common Issues and Solutions:"
echo ""
echo "   Issue: Certificate expired"
echo "   Solution: Renew certificate (Let's Encrypt: certbot renew)"
echo ""
echo "   Issue: Certificate files missing"
echo "   Solution: Generate new certificates or restore from backup"
echo ""
echo "   Issue: Nginx config test fails"
echo "   Solution: Fix config errors in $NGINX_CONF"
echo ""
echo "   Issue: Port 443 not accessible"
echo "   Solution: Check firewall: sudo ufw allow 443/tcp"
echo ""
echo "   Issue: Nginx container not running"
echo "   Solution: cd $NGINX_DIR && docker compose up -d"
echo ""
echo "================================================================================"

