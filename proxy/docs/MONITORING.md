# Monitoring Guide

The TaoHash proxy includes a web-based monitoring dashboard for real-time statistics and analytics.

## Dashboard Access

The monitoring dashboard is available at:
```
http://localhost:5000
```

No authentication is required for the dashboard.

## Dashboard Features

### Real-time Statistics
- Active worker count
- Total hashrate across all workers
- Pool connection status
- Share submission rates

### Worker Details
- Individual worker hashrates
- Share acceptance/rejection rates
- Connection timestamps
- Last share submission times

### Historical Data
- Hashrate charts over time
- Share submission trends
- Worker performance history

## Analytics API

The dashboard also exposes an analytics API for custom integrations.

### Analytics Endpoints

```
GET /api/analytics/hashrate
```
Returns hashrate data over time.

```
GET /api/analytics/shares
```
Returns share submission statistics.

```
GET /api/analytics/workers
```
Returns worker performance metrics.

## Database Queries

The monitoring system uses ClickHouse for time-series data storage. You can access the ClickHouse web interface at:
```
http://localhost:8123
```

### Common Queries

**Get recent shares:**
```sql
SELECT * FROM shares
WHERE timestamp > now() - INTERVAL 1 HOUR
ORDER BY timestamp DESC
LIMIT 100
```

**Calculate hashrate by worker:**
```sql
SELECT 
    worker_id,
    sum(difficulty) * pow(2, 32) / 300 as hashrate_5m
FROM shares
WHERE timestamp > now() - INTERVAL 5 MINUTE
    AND accepted = 1
GROUP BY worker_id
```

**Worker uptime:**
```sql
SELECT 
    worker_id,
    min(timestamp) as first_seen,
    max(timestamp) as last_seen,
    dateDiff('second', min(timestamp), max(timestamp)) as uptime_seconds
FROM shares
GROUP BY worker_id
```
