# Slack MCP Server

A Model Context Protocol (MCP) server that enables LLMs to interact with Slack workspaces through OAuth 2.0 authentication.

## Features

- 🔐 **OAuth 2.0 Authentication**: Secure Slack OAuth flow with automatic token management
- 👥 **Multi-user Support**: Each user maintains their own Slack authentication
- 🚀 **FastMCP v2**: Built with the ergonomic FastMCP framework
- 💾 **Token Persistence**: Tokens are saved locally for seamless reconnection
- 📱 **Slack Integration**: Post messages and list channels in Slack workspaces
- 🔄 **Session Management**: Automatic session handling with isolation
- ☁️ **Cloud-ready**: Supports deployment to AWS Fargate with CDK

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
   - Local: `https://localhost:8444/oauth/callback` (or your configured port)
   - Production: `https://your-domain.com/oauth/callback`
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

# Optional: Change OAuth callback port (default: 8443)
SLACK_OAUTH_PORT=8444
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

## Multi-User Support

### User Identification

Users are identified through HTTP headers (in priority order):
1. `Mcp-Session-Id`: MCP standard session header
2. `x-user-id`: Custom user identifier
3. `x-mcp-user-id`: MCP-specific user ID
4. `x-session-id`: Session identifier
5. `Authorization`: Bearer token (first 20 chars hashed)

### Token Management

- Each user's Slack token is stored separately: `{client_id}:{user_id}`
- Tokens are persisted locally in JSONL format
- Each user must complete their own OAuth flow
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
        "http://localhost:8001/mcp/",
        headers=headers,
        json={"jsonrpc": "2.0", "method": "tools/list", "id": "1"}
    )
```

## Port Configuration

The server uses multiple ports:
- **8001**: MCP server endpoint
- **8002**: Health check and OAuth endpoints  
- **8444**: OAuth callback server (configurable via `SLACK_OAUTH_PORT`)

### AWS Fargate Deployment

The project includes AWS CDK infrastructure for production deployment:

```bash
# Deploy to AWS
cd infrastructure
./deploy.sh

# Configure parameters in AWS Systems Manager:
aws ssm put-parameter --name "/slack-mcp/dev/client-id" --value "your-client-id" --type "String"
aws ssm put-parameter --name "/slack-mcp/dev/client-secret" --value "your-secret" --type "SecureString"
```

## Project Structure

```
slack-mcp-server/
├── server.py               # Main MCP server (FastMCP v2)
├── auth_server.py          # OAuth callback server
├── slack_auth_provider.py  # Slack OAuth implementation
├── token_verifier.py       # Token validation and session management
├── session_manager.py      # Session-to-token mapping
├── token_storage.py        # Token persistence layer
├── storage_interface.py    # Storage abstraction (local/cloud)
├── storage_dynamodb.py     # DynamoDB storage for AWS
├── http_endpoints.py       # Health check and OAuth endpoints
├── parameter_store.py      # AWS Systems Manager integration
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
curl http://localhost:8002/health

# View OAuth status
curl http://localhost:8002/oauth/status
```

### Debugging

Enable debug logging by checking `server.log`:
```bash
tail -f server.log
```

## Troubleshooting

### Port Already in Use

```bash
# Check what's using a port
lsof -i :8444

# Find available ports
for port in 8444 8445 8446; do 
  lsof -i :$port >/dev/null 2>&1 || echo "Port $port available"
done
```

### OAuth Errors

1. **bad_redirect_uri**: Ensure the redirect URL in Slack app matches exactly:
   - Must include the full path: `https://localhost:8444/oauth/callback`
   - Port number must match your configuration
   
2. **invalid_client_id**: Verify SLACK_CLIENT_ID in .env

3. **Token not found**: Complete OAuth by authorizing in browser

### SSL Certificate Warnings

The server auto-generates self-signed certificates. In your browser:
- Click "Advanced" → "Proceed to localhost"

## Security Considerations

- OAuth tokens are stored locally with user isolation
- Each user has separate authentication
- HTTPS required for OAuth callbacks
- Tokens validated before each use
- Self-signed certificates auto-generated for local dev

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the guidelines in CLAUDE.md
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## References

- [MCP Documentation](https://modelcontextprotocol.io)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Slack API Documentation](https://api.slack.com)
