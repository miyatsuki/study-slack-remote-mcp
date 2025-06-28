# Docker Local Testing Guide

## Quick Start

1. **Set up environment variables**:
   ```bash
   # Copy the example env file if you don't have one
   cp .env.example .env
   
   # Edit .env and add your Slack OAuth credentials:
   # SLACK_CLIENT_ID=your_client_id
   # SLACK_CLIENT_SECRET=your_client_secret
   ```

2. **Build and run the container**:
   ```bash
   # Build and start the service
   docker-compose up --build
   
   # Or run in detached mode
   docker-compose up -d --build
   ```

3. **Test the endpoints**:
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # MCP endpoint (will return 400 without proper MCP client)
   curl http://localhost:8000/mcp/
   ```

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Stop the service
docker-compose down

# Rebuild without cache
docker-compose build --no-cache

# Shell into the container
docker-compose exec slack-mcp-server bash

# Check container status
docker-compose ps
```

## Testing OAuth Flow

1. The OAuth callback URL for local Docker testing should be:
   ```
   http://localhost:8000/oauth/callback
   ```

2. Make sure this URL is added to your Slack App's OAuth redirect URLs.

## Troubleshooting

### Port already in use
```bash
# Check what's using port 8000
lsof -i :8000

# Use a different port in docker-compose.yml
ports:
  - "8001:8000"  # Maps host port 8001 to container port 8000
```

### Permission issues with data volume
```bash
# Create the data directory with proper permissions
mkdir -p data
chmod 755 data
```

### View stored tokens
```bash
# Tokens are stored in the data volume
cat data/slack_tokens.jsonl
```