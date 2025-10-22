# Logging Configuration for Crypto AI Agent

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [News Plan](NEWS_VISUALIZATION_PLAN.md) | [Price Alerts Plan](PRICE_ALERTS_PLAN.md)

## Overview

The Crypto AI Agent uses a centralized logging system that provides comprehensive logging across all project modules. Every step of the application is documented in detailed logs.

## Configuration

### Environment Variables

Add these variables to your `.env` file to configure logging:

```bash
# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/crypto_agent.log    # Path to log file
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Log format
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

## Log Format

Each log entry follows this format:

```text
2024-01-15 10:30:45,123 - crypto_ai_agent.agent - INFO - INFO in database_initialization - Database initialized successfully - db_path=data/crypto_history.db
```

Components:

- **Timestamp**: When the event occurred
- **Logger Name**: Which module logged the event
- **Level**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Context**: What operation was being performed
- **Message**: Description of the event
- **Additional Data**: Key-value pairs with relevant information

## Usage Examples

### In Agent Code

```python
from utils.logger import get_logger, log_function_entry, log_database_operation

logger = get_logger("agent")

# Function logging
log_function_entry("process_price", "agent", symbol="BTC", price=45000)

# Database operation logging
log_database_operation("insert", "portfolio", "agent", symbol="BTC", amount=1.5)

# Performance logging
log_performance("price_prediction", 0.123, "agent", symbol="BTC")
```

### In UI Dashboard

```python
from utils.logger import get_logger, log_user_action

logger = get_logger("ui_dashboard")

# User action logging
log_user_action("add_coin", {"symbol": "BTC", "amount": 0.5}, "ui_dashboard")
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

### Prometheus + Grafana

- Export log metrics to Prometheus
- Create monitoring dashboards
- Set up alerting rules

### Cloud Logging (AWS CloudWatch, Google Cloud Logging)

- Stream logs to cloud services
- Use cloud-native alerting
- Leverage cloud analytics tools

## 📋 Related Documentation

- **[Main README](README.md)** - Complete project overview and setup instructions
- **[CURRENT_PLAN.md](CURRENT_PLAN.md)** - Current implementation status and completed features
- **[NEWS_VISUALIZATION_PLAN.md](NEWS_VISUALIZATION_PLAN.md)** - News sentiment visualization implementation
- **[PRICE_ALERTS_PLAN.md](PRICE_ALERTS_PLAN.md)** - Price alerts system implementation
