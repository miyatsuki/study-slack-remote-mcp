# Slack MCP Server

A Model Context Protocol (MCP) server that enables LLMs to interact with Slack workspaces through OAuth 2.0 authentication.

## Features

- 🔐 **OAuth 2.0 Authentication**: Secure Slack OAuth flow with automatic token management
- 🚀 **FastMCP Framework**: Built with the official MCP SDK's FastMCP framework
- 💾 **Token Persistence**: Tokens are saved locally or in DynamoDB for cloud deployments
- 📱 **Slack Integration**: Post messages and list channels in Slack workspaces
- 🔄 **Dynamic Client Registration**: Supports VSCode MCP extension and other clients
- ☁️ **GitHub + App Runner**: Deploy directly from GitHub with AWS App Runner

## Prerequisites

- Python 3.11+
- Slack App with OAuth 2.0 configured
- uv (Python package manager)

## Quick Start

### 1. Slack App Configuration

1. Create a new Slack App at https://api.slack.com/apps
2. Add OAuth Scopes in "OAuth & Permissions":
   - `chat:write` - Post messages
   - `channels:read` - List channels
3. Add Redirect URLs:
   - Local: `http://localhost:8080/slack/callback`
   - Production: `https://your-domain.com/slack/callback`
4. Copy the Client ID and Client Secret

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/miyatsuki/study-slack-remote-mcp.git
cd study-slack-remote-mcp

# Install dependencies using uv
uv sync
```

### 3. Configuration

Create a `.env` file:

```bash
# Required: Slack OAuth credentials
SLACK_CLIENT_ID=your_client_id
SLACK_CLIENT_SECRET=your_client_secret

# Optional: Service base URL (for production deployments)
# SERVICE_BASE_URL=https://your-apprunner-url.awsapprunner.com
```

### 4. Run the Server

```bash
# Start the server
uv run python server.py

# Or run in background
nohup uv run python server.py > server.log 2>&1 &
```

## Usage

### With VSCode MCP Extension

1. Install the MCP extension for VSCode
2. Connect to the server URL: `http://localhost:8080/mcp/`
3. The OAuth flow will start automatically when you first use a tool

### With Claude Desktop

Add to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "slack": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/slack-mcp-server",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

### Available Tools

1. **list_channels**: Get a list of Slack channels
   ```
   Returns: Dictionary mapping channel names to IDs
   ```

2. **post_message**: Post a message to a Slack channel
   ```
   Args:
   - channel_id: Channel ID (required)
   - text: Message text (required)
   
   Returns: Success/failure message
   ```

3. **get_auth_status**: Check authentication status
   ```
   Returns: Current authentication state and session info
   ```

## Authentication Flow

1. When a tool is first used, the OAuth flow automatically starts
2. A browser window opens for Slack authorization
3. After authorization, the token is saved for future use
4. Subsequent requests use the cached token

## Authentication

The server uses FastMCP's built-in OAuth 2.0 support with dynamic client registration. This allows compatibility with various MCP clients including VSCode's MCP extension.

### Token Management

- OAuth tokens are mapped between MCP tokens and Slack tokens internally
- Tokens are persisted locally in memory (or DynamoDB in cloud)
- OAuth flow starts automatically when tools are first used
- Dynamic client registration supported for VSCode and other clients

## Port Configuration

The server uses a single port:
- **8080**: MCP server endpoint (includes health check and OAuth callback routes)

### AWS App Runner Deployment

The project uses GitHub integration with AWS App Runner for production deployment:

```bash
# First, set up AWS Systems Manager parameters:
aws ssm put-parameter --name "/slack-mcp/dev/client-id" --value "your-client-id" --type "String"
aws ssm put-parameter --name "/slack-mcp/dev/client-secret" --value "your-secret" --type "SecureString"

# Deploy using CDK (creates App Runner service with GitHub integration)
cd infrastructure
cdk deploy SlackMcpStack-dev

# Manual deployment trigger (after pushing to GitHub)
aws apprunner start-deployment --service-arn <your-service-arn>
```

App Runner provides:
- Direct deployment from GitHub repository
- Built-in HTTPS with automatic certificates
- Manual deployment control (auto-deploy disabled by default)
- Auto-scaling and simplified management

## Project Structure

```
study-slack-remote-mcp/
├── server.py               # Main MCP server using FastMCP framework
├── slack_oauth_provider.py # Slack OAuth provider implementation
├── storage_interface.py    # Storage abstraction (local/cloud)
├── storage_dynamodb.py     # DynamoDB storage for AWS
├── token_storage.py        # Local file-based token storage
├── apprunner.yaml         # AWS App Runner configuration
├── pyproject.toml         # Project dependencies
├── uv.lock               # Locked dependencies
├── infrastructure/        # AWS CDK deployment code
├── CLAUDE.md             # Development guidelines
└── .env                  # Environment variables (create from .env.example)
```

## Development

### Testing

```bash
# Check server health
curl http://localhost:8080/health

# Test with MCP client
mcp run uv --directory /path/to/study-slack-remote-mcp run python server.py
```

### Debugging

Enable debug logging by checking `server.log`:
```bash
tail -f server.log
```

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8080
lsof -i :8080

# Kill process using port 8080 if needed
kill -9 $(lsof -ti:8080)
```

### OAuth Errors

1. **bad_redirect_uri**: Ensure the redirect URL in Slack app matches exactly:
   - Must include the full path: `http://localhost:8080/slack/callback`
   - Port must be 8080 (MCP server port)
   
2. **invalid_client_id**: Verify SLACK_CLIENT_ID in .env

3. **Token not found**: Complete OAuth by authorizing in browser

## Security Considerations

- OAuth tokens are mapped between MCP tokens and Slack tokens
- Tokens stored in memory locally, DynamoDB in production
- Dynamic client registration supports various MCP clients
- OAuth callbacks use HTTPS in production (App Runner)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the guidelines in CLAUDE.md
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## References

- [MCP Documentation](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Slack API Documentation](https://api.slack.com)
