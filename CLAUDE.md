# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python MCP (Model Context Protocol) server that provides Slack integration with OAuth 2.0 authentication support for multiple users. Built with FastMCP v2 framework, the server allows MCP clients to interact with Slack workspaces through authenticated API calls.

## Development Commands

### Setup and Installation
```bash
# Using uv (recommended)
uv venv
uv pip install -e .

# Alternative using pip
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### Running the Server

**Local Development:**
```bash
# Main server with session support and automatic OAuth (recommended)
uv run python server.py

# Or with MCP client
uv run mcp run uv --directory /path/to/study-slack-remote-mcp run python server.py

# Test OAuth flow independently
python main.py
```

**AWS Fargate Deployment:**
```bash
# One-command deployment with CDK
cd infrastructure && ./deploy.sh

# Manual CDK deployment
cd infrastructure && cdk deploy SlackMcpStack-dev
```

### Testing
```bash
# Run the FastMCP test client
uv run python test_fastmcp_client.py
```

## Architecture

### Core Components

1. **MCP Server**
   - `server.py`: FastMCP v2 server (port 8001) with automatic OAuth flow
   - Uses streamable-http transport for MCP communication
   - Multi-user support via HTTP headers

2. **Authentication System**
   - `slack_auth_provider.py`: Implements Slack OAuth 2.0 flow
   - `auth_server.py`: Local HTTPS server for OAuth callbacks (fixed port 8443)
   - `token_verifier.py`: Token validation and Slack API interaction
   - `session_manager.py`: Session and token caching with cleanup

3. **MCP Tools Available**
   - `list_channels`: Get Slack channels (requires channels:read scope)
   - `post_message`: Post to Slack channels (requires chat:write scope)
   - `get_auth_status`: Debug authentication status

### Authentication Flow

1. Client connects to MCP server → creates unique session
2. Server checks for existing valid token in session
3. If no token: initiates OAuth flow with local HTTPS callback server
4. User authorizes in browser → token stored in session
5. Subsequent requests use cached token until expiry

### Key Design Decisions

- **FastMCP v2 Framework**: Uses the ergonomic FastMCP v2 for cleaner implementation
- **Multi-user support**: Each user identified by HTTP headers gets isolated authentication
- **Configurable OAuth port**: OAuth callback port configurable via SLACK_OAUTH_PORT (default: 8443)
- **Self-signed SSL**: Automatic certificate generation for HTTPS callbacks
- **Token persistence**: User-specific tokens saved with key format `{client_id}:{user_id}`
- **OAuth-only authentication**: Uses only OAuth 2.0 flow for secure authentication

## Configuration

### Local Development

Required environment variables in `.env`:
```
SLACK_CLIENT_ID=<your-slack-app-client-id>
SLACK_CLIENT_SECRET=<your-slack-app-client-secret>

# Optional: Change OAuth callback port if 8443 is in use
SLACK_OAUTH_PORT=8444
```

### AWS Fargate Deployment

Configuration is managed via AWS Parameter Store:
```bash
# Set Slack app credentials
aws ssm put-parameter --name "/slack-mcp/dev/client-id" --value "your-client-id" --type "String"
aws ssm put-parameter --name "/slack-mcp/dev/client-secret" --value "your-client-secret" --type "SecureString"
```

### Slack App Configuration

- OAuth scopes: `chat:write`, `channels:read`
- Redirect URL (Local): `https://localhost:8444/oauth/callback` (or your configured port)
- Redirect URL (Cloud): `http://your-alb-domain.com/oauth/callback`

## Important Development Guidelines

1. **OAuth Callback Port Configuration**: 
   - Default: Port 8443 for OAuth callbacks
   - Configurable: Use `SLACK_OAUTH_PORT` environment variable if port is occupied
   - Cloud: Uses ALB domain with `/oauth/callback` path
   
2. **Port Availability**: If the OAuth port is occupied, either:
   - Stop the conflicting process: `lsof -i :8443` to check, then stop it
   - Or configure a different port: `export SLACK_OAUTH_PORT=8444`

3. **Infrastructure as Code**: Use CDK for all AWS deployments. Manual resource creation is discouraged. The `infrastructure/` directory contains all AWS resources defined as code.

4. **Environment Management**: Use environment-specific configurations (dev/staging/prod) through CDK context parameters and Parameter Store paths.

5. **Framework References**: 
   - FastMCP v2 documentation: https://github.com/jlowin/fastmcp
   - MCP Python SDK reference: https://github.com/modelcontextprotocol/python-sdk/tree/main
   - Always check these references before making significant code changes

6. **Multi-User Support**: 
   - Users identified by HTTP headers (Mcp-Session-Id, x-user-id, etc.)
   - Each user's tokens stored separately with format `{client_id}:{user_id}`
   - User IDs are hashed for privacy