# Setup Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for local development)
- ClickHouse database

## Quick Start with Docker

1. Clone the repository and navigate to the project directory

2. Copy the example configuration:
   ```bash
   cp config/config.toml.example config/config.toml
   ```

3. Configure your pool settings in `config/config.toml`:
   ```toml
   [pool]
   host = "your-pool-host"
   port = 3333
   username = "your-username"
   password = "your-password"
   ```

4. Generate API tokens for authentication:
   ```bash
   python scripts/generate_token.py
   ```
   Save the generated token - you'll need it for API access.

5. Start the services:
   ```bash
   cd docker
   docker-compose up -d
   ```

## Public Ports

The following ports need to be exposed for external access:

| Port | Service | Purpose |
|------|---------|---------|
| **3331** | Mining proxy (normal difficulty) | Connect miners here for standard mining |
| **3332** | Mining proxy (high difficulty) | Connect miners here for high difficulty |
| **8888** | REST API | Statistics and worker data (requires auth token) |

### Internal Ports (Docker network only)

These ports are used internally by Docker services and don't need public exposure:

- **5000**: Monitoring dashboard (access via reverse proxy if needed)
- **5001**: Reload API endpoint
- **8123**: ClickHouse HTTP interface
- **9000**: ClickHouse native protocol

## Configuration

### Mining Proxy Settings

Edit `config/config.toml` to configure:

- Pool connection details
- Difficulty settings for each port
- Worker credentials
- Database connection

### Environment Variables

Set these in your `.env` file or docker-compose.yml:

- `API_TOKENS`: Comma-separated list of bearer tokens for API authentication
- `DATABASE_URL`: ClickHouse connection string (default: clickhouse://default:@clickhouse:9000/mining)

## Connecting Miners

Point your mining software to:

- `stratum+tcp://your-server:3331` for normal difficulty
- `stratum+tcp://your-server:3332` for high difficulty

Use your pool username and password when connecting.

## Verify Installation

1. Check service health:
   ```bash
   curl http://localhost:8888/health
   ```

2. View monitoring dashboard:
   Open http://localhost:5000 in your browser

3. Check API access (requires token):
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8888/api/pool/stats
   ```

## Manual Installation

For development without Docker:

1. Install dependencies:
   ```bash
   pip install -r docker/requirements.txt
   ```

2. Run ClickHouse locally or configure remote connection

3. Start the proxy:
   ```bash
   python -m taohash_proxy
   ```

## Troubleshooting

- **Connection refused on ports**: Ensure Docker containers are running with `docker-compose ps`
- **API authentication errors**: Verify your bearer token is correctly set in API_TOKENS

## Next Steps

- [API Documentation](./API.md) - REST API endpoints and usage
- [Monitoring Guide](./MONITORING.md) - Dashboard and metrics information