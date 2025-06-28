# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python MCP (Model Context Protocol) server that provides Slack integration with OAuth 2.0 authentication support. Built with the official MCP SDK, the server allows MCP clients to interact with Slack workspaces through authenticated API calls.

Note: Due to MCP SDK limitations, multi-user support via HTTP headers is not available. The server currently operates in single-user mode.

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
# Main server with automatic OAuth (recommended)
uv run python server.py

# Or with MCP client
uv run mcp run uv --directory /path/to/study-slack-remote-mcp run python server.py
```

**AWS App Runner Deployment:**
```bash
# One-command deployment with CDK
cd infrastructure && ./deploy.sh

# Manual CDK deployment
cd infrastructure && cdk deploy SlackMcpStack-dev
```

### Testing
```bash
# Run the MCP SDK test client
uv run python test_mcp_client.py

# Test basic MCP server
uv run python server_test.py
```

## Architecture

### Core Components

1. **MCP Server**
   - `server.py`: MCP SDK server (port 8000) with automatic OAuth flow
   - Uses streamable-http transport for MCP communication
   - Single-user mode (MCP SDK limitation - no HTTP header access)
   - Includes custom routes for health check and OAuth callback

2. **Authentication System**
   - `slack_auth_provider.py`: Implements Slack OAuth 2.0 flow with browser-based auth
   - `token_verifier.py`: Token validation and Slack API interaction
   - `session_manager.py`: Session and token caching with cleanup
   - OAuth callback handled by custom route on MCP server (port 8000)

3. **MCP Tools Available**
   - `list_channels`: Get Slack channels (requires channels:read scope)
   - `post_message`: Post to Slack channels (requires chat:write scope)
   - `get_auth_status`: Debug authentication status

### Authentication Flow

1. Client connects to MCP server → creates unique session
2. Server checks for existing valid token in storage
3. If no token: opens browser for OAuth flow
4. User authorizes in browser → callback to MCP server
5. Token stored and subsequent requests use cached token

### Key Design Decisions

- **MCP SDK**: Uses the official MCP SDK's FastMCP implementation
- **Single-user mode**: Due to MCP SDK limitations, HTTP headers are not accessible, limiting multi-user support
- **Unified server**: All endpoints (MCP, health, OAuth) on single port 8000
- **Token persistence**: Tokens saved with key format `{client_id}:default_user`
- **OAuth-only authentication**: Uses only OAuth 2.0 flow for secure authentication
- **Custom routes**: Uses MCP SDK's custom_route for HTTP endpoints

## Configuration

### Local Development

Required environment variables in `.env`:
```
SLACK_CLIENT_ID=<your-slack-app-client-id>
SLACK_CLIENT_SECRET=<your-slack-app-client-secret>

# OAuth callbacks now use MCP server port (8000)
```

### AWS App Runner Deployment

Configuration is managed via AWS Parameter Store:
```bash
# Set Slack app credentials
aws ssm put-parameter --name "/slack-mcp/dev/client-id" --value "your-client-id" --type "String"
aws ssm put-parameter --name "/slack-mcp/dev/client-secret" --value "your-client-secret" --type "SecureString"
```

### Slack App Configuration

- OAuth scopes: `chat:write`, `channels:read`
- Redirect URL (Local): `http://localhost:8000/oauth/callback`
- Redirect URL (Cloud): `https://your-app-runner-url.awsapprunner.com/oauth/callback`

## Important Development Guidelines

1. **Single Port Architecture**: 
   - All endpoints run on port 8000 (MCP, health check, OAuth callback)
   - No separate OAuth server needed
   - Simplifies deployment and configuration
   
2. **OAuth Callback**: 
   - Local: `http://localhost:8000/oauth/callback`
   - Cloud: Uses App Runner domain with `/oauth/callback` path

3. **Infrastructure as Code**: Use CDK for all AWS deployments. Manual resource creation is discouraged. The `infrastructure/` directory contains all AWS resources defined as code. Now using AWS App Runner for simplified deployment without long consistency checks.

4. **Environment Management**: Use environment-specific configurations (dev/staging/prod) through CDK context parameters and Parameter Store paths.

5. **Framework References**: 
   - MCP Python SDK reference: https://github.com/modelcontextprotocol/python-sdk/tree/main
   - The server now uses the official MCP SDK instead of third-party FastMCP
   - Note: MCP SDK's FastMCP has limited HTTP header access compared to third-party alternatives

6. **Single-User Limitation**: 
   - MCP SDK's FastMCP doesn't provide access to HTTP headers
   - Server operates in single-user mode with `default_user` identifier
   - For true multi-user support, consider using third-party fastmcp package