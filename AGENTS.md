# Agents: crypto-ai-agent

## Coordinator Config

```yaml
model_tier: cheap
cycle_interval_minutes: 30
max_tasks_per_cycle: 10
```

## Worker Pool Config

```yaml
max_concurrent_workers: 3
default_model_tier: free
allowed_mcp_servers: [filesystem, postgres]
```

## Typical Task Types

- analyze_market_trend
- generate_price_alert_report
- write_portfolio_summary

## Active Agents
<!-- Coordinator-maintained -->
