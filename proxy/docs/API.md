# API Documentation

The TaoHash proxy provides a REST API for accessing mining statistics and worker information.

## Authentication

All API endpoints (except `/health`) require Bearer token authentication.

Include the token in your request headers:
```
Authorization: Bearer YOUR_API_TOKEN
```

Generate tokens using:
```bash
python scripts/generate_token.py
```

## Base URL

```
http://localhost:8888
```

## Endpoints

### Health Check

Check if the API service is running.

```
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

No authentication required.

### Pool Statistics

Get current pool connection statistics.

```
GET /api/pool/stats
```

**Headers:**
- `Authorization: Bearer YOUR_TOKEN` (required)

**Response:**
```json
{
  "pool_host": "your-pool.com",
  "pool_port": 3333,
  "connected": true,
  "uptime_seconds": 3600,
  "total_shares_submitted": 150,
  "total_shares_accepted": 148,
  "total_shares_rejected": 2,
  "rejection_rate": 0.0133,
  "last_share_time": "2024-01-15T10:30:45Z"
}
```

### Worker Statistics

Get statistics for all connected workers.

```
GET /api/workers/stats
```

**Headers:**
- `Authorization: Bearer YOUR_TOKEN` (required)

**Response:**
```json
{
  "active_workers": 5,
  "total_workers": 8,
  "workers": [
    {
      "worker_id": "worker1",
      "connected": true,
      "hashrate_5m": 14250000000000,
      "hashrate_1h": 14180000000000,
      "shares_submitted": 45,
      "shares_accepted": 44,
      "shares_rejected": 1,
      "last_share_time": "2024-01-15T10:29:15Z",
      "connection_time": "2024-01-15T08:00:00Z"
    }
  ]
}
```

## Error Responses

### 401 Unauthorized

Missing or invalid API token.

```json
{
  "detail": "Unauthorized"
}
```

### 500 Internal Server Error

Server error, check logs for details.

```json
{
  "detail": "Internal server error"
}
```

## Rate Limiting

Currently no rate limiting is implemented. In production, consider adding rate limiting to prevent abuse.

## Example Usage

### Using curl

```bash
# Get pool stats
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8888/api/pool/stats

# Get worker stats
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8888/api/workers/stats

# Pretty print with jq
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8888/api/workers/stats | jq
```

### Using Python

```python
import requests

token = "YOUR_API_TOKEN"
headers = {"Authorization": f"Bearer {token}"}

# Get pool stats
response = requests.get("http://localhost:8888/api/pool/stats", headers=headers)
pool_stats = response.json()

# Get worker stats
response = requests.get("http://localhost:8888/api/workers/stats", headers=headers)
worker_stats = response.json()
```

## Notes

- All timestamps are in UTC ISO 8601 format
- Hashrates are in hashes per second
- Statistics are aggregated from ClickHouse time-series data
- Worker IDs are derived from the stratum username format