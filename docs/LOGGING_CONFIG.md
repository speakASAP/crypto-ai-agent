# Logging Configuration for Crypto AI Agent

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [News Plan](NEWS_VISUALIZATION_PLAN.md) | [Price Alerts Plan](PRICE_ALERTS_PLAN.md)

## Overview

The Crypto AI Agent uses a centralized logging system that provides comprehensive logging across all project modules. Every step of the application is documented in detailed logs.

**Architecture**:

- **Backend**: Uses `backend/app/utils/logger.py` which provides `get_logger()` and standard Python logging methods
- **Frontend**: Uses `frontend/src/lib/logger.ts` which sends logs to the backend `/api/logging/log` endpoint
- **Centralized Logger**: `utils/logger.py` provides structured logging functions (available but not currently used in backend)
- **All logs**: Write to the same centralized log file (`logs/crypto_agent.log`)
- **External Logging Service**: Logs are also sent to external logging microservice at `http://logging-microservice:${PORT:-3367}` (configured in `logging-microservice/.env`, dual logging with local fallback)

## Configuration

### Environment Variables

Add these variables to your `.env` file to configure logging:

```bash
# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/crypto_agent.log    # Path to log file
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Log format

# External Logging Service (optional)
LOGGING_SERVICE_URL=http://logging-microservice:${PORT:-3367}  # URL of external logging microservice (port configured in logging-microservice/.env)
```

### External Logging Service

The application supports dual logging: logs are sent to both local files and an external logging microservice.

**Features**:

- **Dual Logging**: Logs are sent to external service AND written locally as fallback
- **Non-blocking**: HTTP requests don't block application execution (uses threading)
- **Fallback**: If logging service is unavailable, falls back to local files only
- **Metadata**: Includes context, stack traces, module/function/line information in log metadata
- **Service Identification**: All logs tagged with `crypto-ai-agent` service name
- **Backward Compatible**: No changes needed in services using the logger

**Configuration**:

- Set `LOGGING_SERVICE_URL` in `.env` to enable external logging
- If not configured, only local file logging is used
- External service URL format: `http://logging-microservice:${PORT:-3367}` (port configured in `logging-microservice/.env`)

**Metadata Structure**:
Logs sent to external service include rich metadata:

```json
{
  "level": "error",
  "message": "Error message",
  "service": "crypto-ai-agent",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "metadata": {
    "module": "backend.app.api.prices",
    "function": "get_prices",
    "line": 42,
    "context": "API call",
    "stack_trace": "...",
    "user_id": 123,
    "username": "user1",
    "url": "/api/prices",
    "user_agent": "Mozilla/5.0..."
  }
}
```

### Log Levels

- **DEBUG**: Detailed information for debugging (function entry/exit, parameter values)
- **INFO**: General information about application flow (startup, user actions, API calls)
- **WARNING**: Warning messages (API failures, connection issues)
- **ERROR**: Error conditions (database errors, API errors)
- **CRITICAL**: Critical errors requiring immediate attention (startup failures)

## Log Categories

### 1. System Events

- Application startup/shutdown
- Database initialization
- Configuration loading
- Error recovery

### 2. Database Operations

- Table creation
- Data insertion/updates
- Query execution
- Connection management

### 3. API Calls

- Binance API requests
- News API requests
- Telegram notifications
- Response status codes

### 4. User Actions

- Portfolio modifications
- Symbol management
- UI interactions
- Settings changes

### 5. Performance Metrics

- Function execution times
- Database query performance
- API response times
- Memory usage

### 6. Error Handling

- Exception details
- Stack traces
- Recovery attempts
- Fallback mechanisms

## Log File Structure

```text
logs/
├── crypto_agent.log          # Main application log
├── crypto_agent.log.1       # Rotated log (if rotation enabled)
└── crypto_agent.log.2       # Older rotated log
```

In Docker deployments, the backend writes logs to `/app/logs` which is bind-mounted to the host `./logs` directory via docker-compose.

## Log Format

Each log entry follows this format:

```text
2024-01-15 10:30:45,123 - crypto_ai_agent.agent - INFO - INFO in database_initialization - Database initialized successfully - database_url=postgresql://...
```

Components:

- **Timestamp**: When the event occurred
- **Logger Name**: Which module logged the event
- **Level**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Context**: What operation was being performed
- **Message**: Description of the event
- **Additional Data**: Key-value pairs with relevant information

## Usage Examples

### In Backend Code (Current Implementation)

The backend uses a simplified logger that provides `get_logger()` and standard Python logging methods:

```python
from ..utils.logger import get_logger

logger = get_logger("backend.app.api.prices")

# Standard logging methods
logger.info("Fetching prices for symbols")
logger.error("Error fetching prices", exc_info=True)
logger.warning("Price not found for symbol")
logger.debug("Debug information")
```

**Note**: The backend logger (`backend/app/utils/logger.py`) automatically:

- Writes to the centralized log file (`logs/crypto_agent.log`)
- Respects `LOG_LEVEL` and `DEBUG` environment variables
- Uses the same log format as the centralized logger
- Sends logs to external logging service if `LOGGING_SERVICE_URL` is configured (non-blocking)

### In Backend Code (Alternative: Structured Logging)

If you want to use structured logging functions from the centralized logger (`utils/logger.py`):

```python
from utils.logger import get_logger, log_function_entry, log_database_operation, log_api_call

logger = get_logger("agent")

# Function logging
log_function_entry("process_price", "agent", symbol="BTC", price=45000)

# Database operation logging
log_database_operation("insert", "portfolio", "agent", symbol="BTC", amount=1.5)

# API call logging
log_api_call("Binance", "/api/v3/ticker/price", "agent", status_code=200)

# Performance logging
from utils.logger import log_performance
log_performance("price_prediction", 0.123, "agent", symbol="BTC")
```

### In Frontend Code

The frontend uses a TypeScript logger that sends logs to the backend:

```typescript
import { logger } from '@/lib/logger'

// Standard logging (batched and throttled in production)
logger.info("User action")
logger.error("Error occurred")
logger.warn("Warning message")
logger.debug("Debug info")

// Production optimization:
// - Errors are sent immediately
// - Non-critical logs are batched (max 1 request per 5 seconds)
// - In production, non-critical logs are filtered out
```

## Monitoring and Alerts

### Log Monitoring

- Monitor log files for ERROR and CRITICAL messages
- Set up alerts for repeated failures
- Track performance metrics over time

### Key Metrics to Monitor

- Database connection failures
- API rate limit hits
- User action frequency
- Error rates by module
- Performance degradation

## Log Rotation

For production environments, consider setting up log rotation:

```bash
# Using logrotate
/path/to/logs/crypto_agent.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 user group
}
```

## Troubleshooting

### Common Log Patterns

1. **Database Connection Issues**

   ```text
   ERROR in database_initialization - Connection failed - attempt=1, max_retries=3
   ```

2. **API Rate Limiting**

   ```text
   WARNING in api_call - HTTP 429 from Binance API - status_code=429
   ```

3. **User Actions**

   ```text
   INFO in user_action - USER ACTION add_coin - symbol=BTC, amount=0.5
   ```

4. **Performance Issues**

   ```text
   INFO in performance - PERFORMANCE price_prediction took 2.456s - symbol=BTC
   ```

### Debug Mode

To enable detailed debugging, set:

```bash
LOG_LEVEL=DEBUG
```

This will log:

- Function entry/exit with parameters
- Database query details
- API request/response details
- Internal state changes

## Best Practices

1. **Use Appropriate Log Levels**
   - DEBUG: Development and troubleshooting
   - INFO: Normal operation flow
   - WARNING: Recoverable issues
   - ERROR: Unrecoverable issues
   - CRITICAL: System failures

2. **Include Context**
   - Always include relevant parameters
   - Add timestamps for time-sensitive operations
   - Include user/session information when available

3. **Avoid Logging Sensitive Data**
   - Never log API keys or passwords
   - Be careful with user personal information
   - Use placeholders for sensitive values

4. **Performance Considerations**
   - Use appropriate log levels in production
   - Consider log file size and rotation
   - Monitor logging performance impact

## Integration with Monitoring Tools

### ELK Stack (Elasticsearch, Logstash, Kibana)

- Ship logs to Elasticsearch
- Create dashboards in Kibana
- Set up alerts for critical events

### Cloud Logging (AWS CloudWatch, Google Cloud Logging)

- Stream logs to cloud services
- Use cloud-native alerting
- Leverage cloud analytics tools

## 📋 Related Documentation

- **[Main README](README.md)** - Complete project overview and setup instructions
- **[CURRENT_PLAN.md](CURRENT_PLAN.md)** - Current implementation status and completed features
- **[NEWS_VISUALIZATION_PLAN.md](NEWS_VISUALIZATION_PLAN.md)** - News sentiment visualization implementation
- **[PRICE_ALERTS_PLAN.md](PRICE_ALERTS_PLAN.md)** - Price alerts system implementation
