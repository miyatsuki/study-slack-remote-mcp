# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python MCP (Model Context Protocol) server that provides Slack integration with OAuth 2.0 authentication support. Built with the official MCP SDK's FastMCP framework using the built-in auth_server_provider, the server allows MCP clients to interact with Slack workspaces through authenticated API calls.

## Development Commands

### Setup and Installation
```bash
# Using uv (recommended)
uv sync

# Alternative using pip
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install .
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
# Deploy infrastructure with CDK (creates App Runner with GitHub integration)
cd infrastructure && cdk deploy SlackMcpStack-dev

# Manual deployment after pushing changes to GitHub
aws apprunner start-deployment --service-arn <service-arn> --region ap-northeast-1
```

### Testing
```bash
# Test with MCP CLI client
mcp run uv --directory /path/to/study-slack-remote-mcp run python server.py

# Health check
curl http://localhost:8080/health
```

## Architecture

### Core Components

1. **MCP Server**
   - `server.py`: MCP SDK's FastMCP server (port 8080) with built-in OAuth support
   - Uses streamable-http transport for MCP communication
   - Implements auth_server_provider for standard MCP authentication

2. **Authentication System**
   - `slack_oauth_provider.py`: Implements OAuthAuthorizationServerProvider protocol for Slack OAuth 2.0
   - OAuth callbacks handled directly by MCP server on port 8080
   - In-memory token storage for local development, DynamoDB for cloud deployment
   - `storage_interface.py`: Abstract interface for token storage
   - `token_storage.py`: Local file-based token storage implementation
   - `storage_dynamodb.py`: AWS DynamoDB token storage implementation

3. **MCP Tools Available**
   - `list_channels`: Get Slack channels (requires channels:read scope)
   - `post_message`: Post to Slack channels (requires chat:write scope)
   - `get_auth_status`: Debug authentication status

### Authentication Flow

1. Client connects to MCP server → dynamic client registration
2. Server checks for existing valid token
3. If no token: initiates OAuth flow with browser redirect
4. User authorizes in Slack → redirected to `/slack/callback`
5. Token exchange: Slack token ↔ MCP token mapping
6. Subsequent requests use cached token until expiry

### Key Design Decisions

- **MCP SDK with auth_server_provider**: Uses official MCP SDK's built-in OAuth support
- **Standard MCP authentication**: Implements OAuthAuthorizationServerProvider protocol
- **Unified server**: All endpoints (MCP, health, OAuth) on single port 8080
- **Token mapping**: Maps between MCP tokens and Slack tokens internally
- **Storage abstraction**: In-memory storage locally, DynamoDB in cloud
- **Dynamic client registration**: Supports VSCode MCP extension and other clients
- **GitHub + App Runner**: Direct deployment from GitHub repository
- **uv package manager**: Fast, reliable dependency management

## Configuration

### Local Development

Required environment variables in `.env`:
```
SLACK_CLIENT_ID=<your-slack-app-client-id>
SLACK_CLIENT_SECRET=<your-slack-app-client-secret>

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
- Redirect URL (Local): `http://localhost:8080/slack/callback`
- Redirect URL (Cloud): `https://your-app-runner-url.awsapprunner.com/slack/callback`

## Important Development Guidelines

1. **Single Port Architecture**: 
   - All endpoints run on port 8080 (MCP, health check, OAuth callback)
   - OAuth callbacks handled by custom route on MCP server
   - Simplifies deployment and configuration

2. **VSCode Compatibility**: 
   - Middleware removes unsupported `device_code` grant type from VSCode requests
   - Dynamic client registration accepts any client ID
   - Ensures compatibility with VSCode MCP extension

3. **Infrastructure as Code**: 
   - Use CDK for all AWS deployments
   - GitHub integration with App Runner (no Docker/ECR needed)
   - Manual deployment control (auto-deploy disabled by default)

4. **Environment Management**: 
   - Use environment-specific configurations (dev/staging/prod)
   - SSM Parameter Store for secrets
   - `apprunner.yaml` for runtime configuration

5. **Framework References**: 
   - MCP Python SDK reference: https://github.com/modelcontextprotocol/python-sdk/tree/main
   - Uses FastMCP from the official MCP SDK with auth_server_provider
   - OAuth implementation follows MCP's OAuthAuthorizationServerProvider protocol

6. **OAuth Provider Implementation**: 
   - SlackOAuthProvider implements OAuthAuthorizationServerProvider protocol
   - Handles Slack OAuth flow and token exchange
   - Maps between MCP access tokens and Slack tokens for API calls

7. **Git Commit Convention**:
   - Use gitmoji + conventional commit format
   - Write commit messages in Japanese
   - Format: `<emoji> <type>: <description>`
   - Example: `✨ feat: VSCode互換性のための登録ミドルウェアを追加`