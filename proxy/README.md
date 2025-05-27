# TaoHash Mining Proxy

A Bitcoin mining proxy for TaoHash validators.

## Quick Start

```bash
# Using Docker (recommended)
cd docker
docker-compose up -d

# Miners cna connect to:
# stratum+tcp://your-server:3331 (normal difficulty)
# stratum+tcp://your-server:3332 (high difficulty)
```

## Features

- **Dual Difficulty Support**: Two ports for different difficulty levels
- **Real-time Monitoring**: Web dashboard on port 5000
- **REST API**: Statistics API on port 8888 with bearer token auth
- **ClickHouse Storage**: To serve real-time and historical data
- **Worker Tracking**: Individual worker performance metrics

## Configuration

1. Copy and edit the configuration:
   ```bash
   cp config/config.toml.example config/config.toml
   ```

2. Set pool details in `config/config.toml`:
   ```toml
   [pool]
   host = "your-pool-host"
   port = 3333
   username = "your-username"
   password = "your-password"
   ```

3. Generate API tokens:
   ```bash
   python scripts/generate_token.py
   ```

## Ports

- **3331**: Mining proxy (normal difficulty)
- **3332**: Mining proxy (high difficulty)  
- **8888**: REST API (requires authentication)
- **5000**: Monitoring dashboard (internal - not necessary to expose publically)

## API Usage

```bash
# Pool stats
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8888/api/pool/stats

# Worker stats
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8888/api/workers/stats
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [API Reference](docs/API.md) - REST API endpoints
- [Monitoring Guide](docs/MONITORING.md) - Dashboard and metrics

## Requirements

- Docker and Docker Compose
- Python 3.8+ (for local development)
- ClickHouse (included in Docker setup)
