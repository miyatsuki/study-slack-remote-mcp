# Slack MCP Server

A Model Context Protocol (MCP) server that enables LLMs to interact with Slack workspaces through OAuth 2.0 authentication.

## Features

- 🔐 **OAuth 2.0 Authentication**: Secure Slack OAuth flow with automatic token management
- 🚀 **MCP SDK**: Built with the official MCP SDK
- 💾 **Token Persistence**: Tokens are saved locally for seamless reconnection
- 📱 **Slack Integration**: Post messages and list channels in Slack workspaces
- 🔄 **Session Management**: Automatic session handling with isolation
- ☁️ **Cloud-ready**: Supports deployment to AWS App Runner with CDK

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
git clone https://github.com/yourusername/slack-mcp-server.git
cd slack-mcp-server

# Install dependencies using uv
uv venv
uv pip install -e .
```

### 3. Configuration

Create a `.env` file:

```bash
# Required: Slack OAuth credentials
SLACK_CLIENT_ID=your_client_id
SLACK_CLIENT_SECRET=your_client_secret

# OAuth callbacks now use MCP server port (8000)
```

### 4. Run the Server

```bash
# Start the server
uv run python server.py

# Or run in background
nohup uv run python server.py > server.log 2>&1 &
```

## Usage

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

The server operates in single-user mode due to MCP SDK limitations. The official MCP SDK's FastMCP doesn't provide access to HTTP headers, preventing multi-user identification.

### Token Management

- Tokens are stored with the format: `{client_id}:default_user`
- Tokens are persisted locally in JSONL format (or DynamoDB in cloud)
- OAuth flow required on first use
- Tokens are validated before use

### Custom Client Example

```python
import httpx

headers = {
    "x-user-id": "alice@example.com",
    "Content-Type": "application/json"
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/mcp/",
        headers=headers,
        json={"jsonrpc": "2.0", "method": "tools/list", "id": "1"}
    )
```

## Port Configuration

The server uses a single port:
- **8000**: MCP server endpoint (includes health check and OAuth callback routes)

### AWS App Runner Deployment

The project includes AWS CDK infrastructure for production deployment using App Runner for faster, simpler deployments:

```bash
# Deploy to AWS
cd infrastructure
./deploy.sh

# Configure parameters in AWS Systems Manager:
aws ssm put-parameter --name "/slack-mcp/dev/client-id" --value "your-client-id" --type "String"
aws ssm put-parameter --name "/slack-mcp/dev/client-secret" --value "your-secret" --type "SecureString"
```

App Runner provides:
- Built-in HTTPS with automatic certificates
- Fast deployment without long consistency checks
- Auto-scaling and simplified management

## Project Structure

```
slack-mcp-server/
├── server.py               # Main MCP server with OAuth (MCP SDK)
├── slack_auth_provider.py  # Slack OAuth implementation
├── token_verifier.py       # Token validation and session management
├── session_manager.py      # Session-to-token mapping
├── token_storage.py        # Token persistence layer
├── storage_interface.py    # Storage abstraction (local/cloud)
├── storage_dynamodb.py     # DynamoDB storage for AWS
├── infrastructure/         # AWS CDK deployment code
├── test_fastmcp_client.py  # Test client for development
└── .env                    # Environment variables
```

## Development

### Testing

```bash
# Run the test client
uv run python test_fastmcp_client.py

# Check server health
curl http://localhost:8000/health

# View OAuth status
curl http://localhost:8000/oauth/status
```

### Debugging

Enable debug logging by checking `server.log`:
```bash
tail -f server.log
```

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000

# Kill process using port 8000 if needed
kill -9 $(lsof -ti:8000)
```

### OAuth Errors

1. **bad_redirect_uri**: Ensure the redirect URL in Slack app matches exactly:
   - Must include the full path: `http://localhost:8000/oauth/callback`
   - Port must be 8000 (MCP server port)
   
2. **invalid_client_id**: Verify SLACK_CLIENT_ID in .env

3. **Token not found**: Complete OAuth by authorizing in browser

### SSL Certificate Warnings

The server auto-generates self-signed certificates. In your browser:
- Click "Advanced" → "Proceed to localhost"

## Security Considerations

- OAuth tokens are stored locally with user isolation
- Each user has separate authentication
- Tokens validated before each use
- OAuth callbacks use HTTP locally (browser-based flow)

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
