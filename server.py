"""Slack MCP Server - Using MCP SDK"""

import json
import logging
import os
import time

import httpx
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from slack_oauth_provider import SlackOAuthProvider
from storage_interface import is_cloud_environment
from starlette.middleware.base import BaseHTTPMiddleware


# Custom logging filter to exclude health check requests
class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Exclude health check endpoint logs
        return '/health' not in record.getMessage()


# Middleware to fix VSCode registration requests
class VSCodeRegistrationFixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/register" and request.method == "POST":
            # Clone the request body
            body = await request.body()
            
            try:
                # Parse the JSON body
                data = json.loads(body.decode('utf-8'))
                
                # Check if this is a VSCode request with device_code grant type
                if "grant_types" in data and "urn:ietf:params:oauth:grant-type:device_code" in data["grant_types"]:
                    print(f"Fixing VSCode registration request by removing device_code grant type")
                    
                    # Remove the unsupported device_code grant type
                    data["grant_types"] = [gt for gt in data["grant_types"] if gt in ["authorization_code", "refresh_token"]]
                    
                    # Convert back to JSON
                    fixed_body = json.dumps(data).encode('utf-8')
                    
                    # Update the request with the fixed body
                    request._body = fixed_body
                    
                    # Update Content-Length header
                    headers = dict(request.headers)
                    headers['content-length'] = str(len(fixed_body))
                    request._headers = [(k.encode('latin-1'), v.encode('latin-1')) for k, v in headers.items()]
                else:
                    # Not a VSCode request, use original body
                    request._body = body
            except Exception as e:
                print(f"Error processing registration request: {e}")
                # On error, use original body
                request._body = body
        
        response = await call_next(request)
        return response

# Load environment variables
load_dotenv()

# Initialize Slack OAuth provider
slack_oauth_provider = SlackOAuthProvider()

# Configure auth settings for MCP
auth_settings = AuthSettings(
    required_scopes=["chat:write", "channels:read"],
    issuer_url=os.getenv("SERVICE_BASE_URL", "http://localhost:8080"),
    service_documentation_url="https://github.com/miyatsuki/study-slack-remote-mcp",
    client_registration_options=ClientRegistrationOptions(
        enabled=True,
        valid_scopes=["chat:write", "channels:read"],
        default_scopes=["chat:write", "channels:read"]
    )
)

# Create MCP server instance using official MCP SDK's FastMCP
# Bind to 0.0.0.0:8080 to allow external access
mcp = FastMCP(
    "slack-mcp-server",
    auth_server_provider=slack_oauth_provider,
    host="0.0.0.0",
    port=8080,
    auth=auth_settings,
)

# Patch the streamable_http_app method to add VSCode fix middleware
original_streamable_http_app = mcp.streamable_http_app

def patched_streamable_http_app():
    app = original_streamable_http_app()
    # Add VSCode fix middleware as the first middleware (processes requests first)
    app.add_middleware(VSCodeRegistrationFixMiddleware)
    return app

mcp.streamable_http_app = patched_streamable_http_app


@mcp.tool()
async def list_channels() -> dict:
    """Slackワークスペース内のチャンネル一覧を取得

    Returns:
        チャンネル名とIDのディクショナリ、またはエラー情報
    """
    # Get context and auth info
    context = mcp.get_context()

    # Check if user is authenticated
    if not hasattr(context, "auth") or not context.auth:
        return {"error": "認証が必要です。まずOAuth認証を完了してください。"}

    # Get Slack token from MCP token
    mcp_token = context.auth.access_token
    slack_token = await slack_oauth_provider.get_slack_token_for_mcp_token(mcp_token)

    if not slack_token:
        return {"error": "Slackトークンが見つかりません。再度認証してください。"}

    headers = {"Authorization": f"Bearer {slack_token}"}
    url = "https://slack.com/api/conversations.list"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            data = resp.json()
        except Exception as e:
            return {"error": f"リクエスト失敗: {e}"}

    if not data.get("ok"):
        return {"error": data.get("error", "unknown_error")}

    channels = data.get("channels", [])
    return {
        ch.get("name"): ch.get("id")
        for ch in channels
        if ch.get("id") and ch.get("name")
    }


@mcp.tool()
async def post_message(channel_id: str, text: str) -> str:
    """指定したチャンネルにメッセージを投稿

    Args:
        channel_id: チャンネルID
        text: メッセージテキスト

    Returns:
        成功/失敗のメッセージ
    """
    if not channel_id or not text:
        return "❌ channel_idとtextが必要です"

    # Get context and auth info
    context = mcp.get_context()

    # Check if user is authenticated
    if not hasattr(context, "auth") or not context.auth:
        return "❌ 認証が必要です。まずOAuth認証を完了してください。"

    # Get Slack token from MCP token
    mcp_token = context.auth.access_token
    slack_token = await slack_oauth_provider.get_slack_token_for_mcp_token(mcp_token)

    if not slack_token:
        return "❌ Slackトークンが見つかりません。再度認証してください。"

    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/json",
    }
    payload = {"channel": channel_id, "text": text}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage", headers=headers, json=payload
            )
            result = resp.json()
        except Exception as e:
            return f"❌ メッセージ送信APIエラー: {e}"

    if result.get("ok"):
        return f"✅ メッセージ送信成功 (チャンネルID: {channel_id})"
    else:
        return f"❌ メッセージ送信失敗: {result.get('error', 'unknown_error')}"


@mcp.tool()
async def get_auth_status() -> dict:
    """認証状態とセッション情報を取得

    Returns:
        認証状態とセッション情報のディクショナリ
    """
    # Get context and auth info
    context = mcp.get_context()

    # Check if user is authenticated
    is_authenticated = hasattr(context, "auth") and context.auth is not None

    result = {
        "authenticated": is_authenticated,
        "environment": "cloud" if is_cloud_environment() else "local",
    }

    if is_authenticated and context.auth:
        # Get Slack token info
        mcp_token = context.auth.access_token
        slack_token = await slack_oauth_provider.get_slack_token_for_mcp_token(
            mcp_token
        )

        result.update(
            {
                "has_slack_token": bool(slack_token),
                "client_id": slack_oauth_provider.client_id[:8] + "...",
                "scopes": (
                    context.auth.scopes if hasattr(context.auth, "scopes") else []
                ),
            }
        )

    return result


# Resource for session information
@mcp.resource("session://info")
async def get_session_info() -> dict:
    """Get current session information"""
    # Get context and auth info
    context = mcp.get_context()

    # Check if user is authenticated
    is_authenticated = hasattr(context, "auth") and context.auth is not None

    result = {
        "authenticated": is_authenticated,
        "environment": "cloud" if is_cloud_environment() else "local",
    }

    if is_authenticated and context.auth:
        # Get Slack token info
        mcp_token = context.auth.access_token
        slack_token = await slack_oauth_provider.get_slack_token_for_mcp_token(
            mcp_token
        )

        result.update(
            {
                "has_slack_token": bool(slack_token),
                "client_id": slack_oauth_provider.client_id[:8] + "...",
                "session_id": (
                    context.session.session_id
                    if hasattr(context.session, "session_id")
                    else None
                ),
            }
        )

    return result


# Custom route: Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Fargate and monitoring"""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "slack-mcp-server",
            "environment": "cloud" if is_cloud_environment() else "local",
            "version": "1.0.0",
        }
    )




# Custom route: Slack OAuth callback endpoint
@mcp.custom_route("/slack/callback", methods=["GET"])
async def slack_oauth_callback(request: Request) -> HTMLResponse:
    """Handle Slack OAuth callback after user authorization"""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(
            f"""
            <html>
            <head>
                <title>認証エラー - Slack MCP</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    h1 {{ color: #e01e5a; }}
                    .error {{ background: #fee; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <h1>❌ Slack認証でエラーが発生しました</h1>
                <div class="error">
                    <p>エラー: <strong>{error}</strong></p>
                    <p>認証をやり直してください。</p>
                </div>
            </body>
            </html>
            """
        )

    if not code or not state:
        return HTMLResponse(
            """
            <html>
            <head>
                <title>認証エラー - Slack MCP</title>
                <style>
                    body { font-family: -apple-system, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                    h1 { color: #e01e5a; }
                    .error { background: #fee; padding: 20px; border-radius: 8px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <h1>❌ 無効なリクエスト</h1>
                <div class="error">
                    <p>必要なパラメータが不足しています。</p>
                </div>
            </body>
            </html>
            """
        )

    try:
        # Handle the Slack callback in the OAuth provider
        auth_code = await slack_oauth_provider.handle_slack_callback(code, state)

        # Get the redirect URI from the authorization code
        redirect_uri = str(auth_code.redirect_uri)

        # Add our MCP authorization code to the redirect
        if "?" in redirect_uri:
            final_redirect = f"{redirect_uri}&code={auth_code.code}"
        else:
            final_redirect = f"{redirect_uri}?code={auth_code.code}"

        # Add state if it was provided
        if auth_code.slack_state:
            final_redirect += f"&state={auth_code.slack_state}"

        # Redirect to the MCP client's callback URL
        return HTMLResponse(
            f"""
            <html>
            <head>
                <title>認証完了 - Slack MCP</title>
                <meta http-equiv="refresh" content="0; url={final_redirect}">
                <style>
                    body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    h1 {{ color: #2ea664; }}
                    .message {{ background: #f8f8f8; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <h1>✅ Slack認証が完了しました</h1>
                <div class="message">
                    <p>MCPクライアントにリダイレクトしています...</p>
                    <p>自動的にリダイレクトされない場合は、<a href="{final_redirect}">こちら</a>をクリックしてください。</p>
                </div>
            </body>
            </html>
            """
        )

    except Exception as e:
        print(f"Slack OAuth callback error: {e}")
        return HTMLResponse(
            f"""
            <html>
            <head>
                <title>認証エラー - Slack MCP</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    h1 {{ color: #e01e5a; }}
                    .error {{ background: #fee; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    pre {{ background: #f4f4f4; padding: 10px; overflow: auto; }}
                </style>
            </head>
            <body>
                <h1>❌ 認証処理でエラーが発生しました</h1>
                <div class="error">
                    <p>エラーの詳細:</p>
                    <pre>{str(e)}</pre>
                </div>
            </body>
            </html>
            """
        )


def run_server():
    """Run MCP server with custom routes"""
    # Check if running in Docker
    is_docker = os.getenv("DOCKER_ENV") or os.path.exists("/.dockerenv")

    # Run MCP server with HTTP transport
    print("📍 MCP endpoint: http://0.0.0.0:8080/mcp")
    print("💚 Health check: http://0.0.0.0:8080/health")
    print("🔗 OAuth callback: http://0.0.0.0:8080/slack/callback")
    print("🔄 Using streamable-http transport")

    if is_docker:
        print("🐳 Docker environment detected")

    # Run the MCP server using the SDK's built-in transport
    mcp.run(transport="streamable-http")


def main():
    """Main entry point for the MCP server"""
    print("=== Slack MCP Server (MCP SDK) ===")
    print("🚀 Starting Slack MCP server...")
    print("📝 OAuth authentication will start automatically when tools are used")
    print("🌐 All endpoints on port 8080")
    
    # Configure logging to filter out health check requests
    # Get uvicorn access logger
    uvicorn_logger = logging.getLogger("uvicorn.access")
    health_filter = HealthCheckFilter()
    uvicorn_logger.addFilter(health_filter)

    # Run server
    run_server()


if __name__ == "__main__":
    main()
