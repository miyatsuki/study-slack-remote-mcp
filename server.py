"""Slack MCP Server - Using MCP SDK"""

import asyncio
import os
from typing import Dict, Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from storage_interface import is_cloud_environment
from token_verifier import SlackTokenVerifier

# Load environment variables
load_dotenv()

# Create MCP server instance using official MCP SDK's FastMCP
# Bind to 0.0.0.0:8080 to allow external access
mcp = FastMCP("slack-mcp-server", host="0.0.0.0", port=8080)

# Token verifier instance - lazy initialization to speed up startup
token_verifier = None

# Track OAuth initiation per session
oauth_initiated_sessions: Dict[str, bool] = {}

# Note: MCP SDK's FastMCP doesn't provide direct access to HTTP headers
# This is a limitation compared to the third-party fastmcp package
# For multi-user support, we'll need to use the session ID mechanism


def get_user_identifier() -> str:
    """Get a unique user identifier.

    Note: The MCP SDK's FastMCP doesn't provide access to HTTP headers,
    so we cannot implement header-based user identification as before.
    This is a known limitation when using the official SDK.
    """
    # TODO: Implement proper session-based user identification
    # For now, default to single user mode
    return "default_user"


async def get_session_slack_token() -> Optional[str]:
    """Get Slack token for current session (initiates OAuth on first call)"""
    global token_verifier

    # Lazy initialize token verifier on first use
    if token_verifier is None:
        token_verifier = SlackTokenVerifier()

    # Get unique user identifier
    user_id = get_user_identifier()
    print(f"🔍 User identifier: {user_id}")

    # Create a user-specific storage key
    storage_key = f"{token_verifier.auth_provider.client_id}:{user_id}"

    # First, check if we have a saved token for this user
    persisted_token = token_verifier.auth_provider.token_storage.load_token(storage_key)

    if persisted_token:
        # Validate the token
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {persisted_token}"},
                )
                data = response.json()
                if data.get("ok", False):
                    print(f"✅ Using existing valid Slack token for user {user_id}")
                    return persisted_token
                else:
                    print(
                        f"⚠️ Token validation failed for user {user_id}: {data.get('error', 'unknown')}"
                    )
        except Exception as e:
            print(f"⚠️ Token validation error for user {user_id}: {e}")

    # No valid token found for this user, start OAuth
    session_id = f"session_{user_id}"

    if session_id not in oauth_initiated_sessions:
        oauth_initiated_sessions[session_id] = True
        print(
            f"🔐 No valid token found for user {user_id}. Starting OAuth authentication..."
        )

        # Create client info with user ID
        client_info = {
            "name": "mcp_client",
            "version": "1.0.0",
            "session_id": session_id,
            "user_id": user_id,
        }

        # Start OAuth flow
        auth_session_id = await token_verifier.start_session_auth(client_info)
        print(
            f"✅ OAuth process started for user {user_id} (session {auth_session_id[:8]}...)"
        )

        # Wait for user to complete OAuth
        print("⏳ Waiting for OAuth completion...")
        for i in range(30):  # Wait up to 30 seconds
            await asyncio.sleep(1)
            # Check if we now have a token
            token = await token_verifier.get_session_token(auth_session_id)
            if token:
                # Save token with user-specific key
                token_verifier.auth_provider.token_storage.save_token(
                    storage_key, token, expires_in_seconds=365 * 24 * 60 * 60
                )
                print(f"✅ OAuth completed successfully for user {user_id}!")
                return token

        print(
            f"❌ OAuth timeout for user {user_id} - please complete authentication and try again"
        )
        return None

    # OAuth already initiated for this user, check if we have a token now
    return await token_verifier.get_session_token(session_id)


@mcp.tool()
async def list_channels(user_id: Optional[str] = None) -> dict:
    """Slackワークスペース内のチャンネル一覧を取得

    Args:
        user_id: ユーザーID（オプション）

    Returns:
        チャンネル名とIDのディクショナリ、またはエラー情報
    """
    slack_token = await get_session_slack_token()
    if not slack_token:
        return {
            "error": "Slackアクセストークンが取得できません。認証を完了してください。"
        }

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
async def post_message(
    channel_id: str, text: str, user_id: Optional[str] = None
) -> str:
    """指定したチャンネルにメッセージを投稿

    Args:
        channel_id: チャンネルID
        text: メッセージテキスト
        user_id: ユーザーID（オプション）

    Returns:
        成功/失敗のメッセージ
    """
    if not channel_id or not text:
        return "❌ channel_idとtextが必要です"

    slack_token = await get_session_slack_token()
    if not slack_token:
        return "❌ Slackアクセストークンが取得できません。認証を完了してください。"

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
    global token_verifier

    # Lazy initialize token verifier on first use
    if token_verifier is None:
        token_verifier = SlackTokenVerifier()

    # Get user identifier
    user_id = get_user_identifier()

    # Check if we have a valid token for this user
    storage_key = f"{token_verifier.auth_provider.client_id}:{user_id}"
    user_token = token_verifier.auth_provider.token_storage.load_token(storage_key)
    has_token = bool(user_token)

    # Get all persisted tokens info
    all_tokens = token_verifier.auth_provider.token_storage.list_tokens()

    # Filter tokens for current app
    app_tokens = [
        t
        for t in all_tokens
        if t["client_id"].startswith(token_verifier.auth_provider.client_id[:8])
    ]

    # Get all sessions from token verifier
    all_sessions = token_verifier.list_sessions()

    return {
        "user_id": user_id,
        "has_valid_token": has_token,
        "app_tokens_count": len(app_tokens),
        "all_tokens_count": len(all_tokens),
        "all_sessions": all_sessions,
        "oauth_initiated_for_user": f"session_{user_id}" in oauth_initiated_sessions,
        "client_id": token_verifier.auth_provider.client_id[:8] + "...",
    }


# Resource for session information
@mcp.resource("session://info")
async def get_session_info() -> dict:
    """Get current session information"""
    global token_verifier

    # Lazy initialize token verifier on first use
    if token_verifier is None:
        token_verifier = SlackTokenVerifier()

    # Get user identifier
    user_id = get_user_identifier()

    # Check authentication status for this user
    storage_key = f"{token_verifier.auth_provider.client_id}:{user_id}"
    user_token = token_verifier.auth_provider.token_storage.load_token(storage_key)

    return {
        "user_id": user_id,
        "session_id": f"session_{user_id}",
        "authenticated": bool(user_token),
        "environment": "cloud" if is_cloud_environment() else "local",
        "client_id": token_verifier.auth_provider.client_id[:8] + "...",
    }


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


# Custom route: OAuth callback endpoint
@mcp.custom_route("/oauth/callback", methods=["GET"])
async def oauth_callback(request: Request) -> HTMLResponse:
    """OAuth callback endpoint for Slack authentication"""
    query_params = dict(request.query_params)

    if "code" in query_params:
        # Handle OAuth success
        code = query_params["code"]
        state = query_params.get("state", "")

        try:
            # Exchange code for token
            token_data = await exchange_oauth_code(code)

            if token_data and token_data.get("ok"):
                access_token = token_data.get("access_token")

                # Extract session_id from state if available
                session_id = state if state else "default_session"

                # For single-user mode, we'll use the default user
                user_id = get_user_identifier()
                storage_key = f"{token_verifier.auth_provider.client_id}:{user_id}"

                # Save token
                token_verifier.auth_provider.token_storage.save_token(
                    storage_key, access_token, expires_in_seconds=365 * 24 * 60 * 60
                )

                # Update session if we have one
                if session_id in oauth_initiated_sessions:
                    # Mark session as completed
                    oauth_initiated_sessions[session_id] = True

                return HTMLResponse(
                    """
                    <html>
                    <head>
                        <title>認証完了 - Slack MCP</title>
                        <style>
                            body { font-family: -apple-system, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                            h1 { color: #2ea664; }
                            .message { background: #f8f8f8; padding: 20px; border-radius: 8px; margin: 20px 0; }
                            .footer { color: #666; font-size: 14px; margin-top: 30px; }
                        </style>
                    </head>
                    <body>
                        <h1>✅ Slack認証が完了しました</h1>
                        <div class="message">
                            <p>トークンが正常に保存されました。</p>
                            <p>MCPクライアントに戻ってツールを実行してください。</p>
                        </div>
                        <div class="footer">
                            <p>このウィンドウは閉じても問題ありません。</p>
                        </div>
                    </body>
                    </html>
                    """
                )

            # Token exchange failed
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
                    <h1>❌ トークン取得に失敗しました</h1>
                    <div class="error">
                        <p>Slackからのトークン取得に失敗しました。</p>
                        <p>もう一度認証をやり直してください。</p>
                    </div>
                </body>
                </html>
                """
            )

        except Exception as e:
            print(f"OAuth callback error: {e}")
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

    elif "error" in query_params:
        # Handle OAuth error
        error = query_params["error"]
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
                    <p>Slackからエラーが返されました: <strong>{error}</strong></p>
                    <p>認証をやり直してください。</p>
                </div>
            </body>
            </html>
            """
        )

    # No code or error parameter
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
                <p>認証コードが含まれていません。</p>
                <p>Slack認証フローから正しくアクセスしてください。</p>
            </div>
        </body>
        </html>
        """
    )


async def exchange_oauth_code(code: str) -> Optional[Dict]:
    """Exchange OAuth authorization code for access token"""
    client_id = os.getenv("SLACK_CLIENT_ID")
    client_secret = os.getenv("SLACK_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Missing Slack OAuth credentials")
        return None

    # Build redirect URI based on environment
    if is_cloud_environment():
        # In cloud environment, get from environment variable (set by App Runner)
        base_url = os.getenv("SERVICE_BASE_URL")
        if not base_url:
            print("Missing SERVICE_BASE_URL environment variable")
            return None
        redirect_uri = f"{base_url}/oauth/callback"
    else:
        # Local development - use MCP server port (8080)
        redirect_uri = "http://localhost:8080/oauth/callback"

    token_url = "https://slack.com/api/oauth.v2.access"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            return response.json()
        except Exception as e:
            print(f"Error exchanging OAuth code: {e}")
            return None


def run_server():
    """Run MCP server with custom routes"""
    # Check if running in Docker
    is_docker = os.getenv("DOCKER_ENV") or os.path.exists("/.dockerenv")

    # Run MCP server with HTTP transport
    print("📍 MCP endpoint: http://0.0.0.0:8080/mcp")
    print("💚 Health check: http://0.0.0.0:8080/health")
    print("🔗 OAuth callback: http://0.0.0.0:8080/oauth/callback")
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

    try:
        # Run server
        run_server()
    finally:
        # Cleanup only if token_verifier was initialized
        if token_verifier is not None:
            print("🔄 Slack MCP Server shutting down...")
            token_verifier.cleanup()
            print("✅ Cleanup completed")


if __name__ == "__main__":
    main()
