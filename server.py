"""Slack MCP Server - Using FastMCP v2"""

import asyncio
import hashlib
import os
from typing import Dict, Optional

import httpx
from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_http_headers

from http_endpoints import HTTPEndpointServer
from storage_interface import is_cloud_environment
from token_verifier import SlackTokenVerifier

# Load environment variables
load_dotenv()

# Create FastMCP server instance
mcp = FastMCP("slack-mcp-server")

# Token verifier instance
token_verifier = SlackTokenVerifier()

# Track OAuth initiation per session
oauth_initiated_sessions: Dict[str, bool] = {}


def get_user_identifier() -> str:
    """Get a unique user identifier from HTTP headers or generate one"""
    try:
        headers = get_http_headers()

        # Try to get user ID from various headers (in priority order)
        user_id = (
            headers.get("mcp-session-id")  # MCP standard session header
            or headers.get("x-user-id")
            or headers.get("x-mcp-user-id")
            or headers.get("x-session-id")
            or headers.get("authorization", "")[
                :20
            ]  # Use first 20 chars of auth header
        )

        if user_id:
            # Hash the user ID for privacy (except for MCP session ID which is already secure)
            if headers.get("mcp-session-id") == user_id:
                return user_id[:16]  # Use first 16 chars of MCP session ID
            else:
                return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    except Exception as e:
        print(f"⚠️ Could not get headers for user identification: {e}")

    # Fallback to default user
    return "default_user"


async def get_session_slack_token(ctx: Context) -> Optional[str]:
    """Get Slack token for current session (initiates OAuth on first call)"""
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


@mcp.tool
async def list_channels(ctx: Context, user_id: Optional[str] = None) -> dict:
    """Slackワークスペース内のチャンネル一覧を取得

    Args:
        user_id: ユーザーID（オプション）

    Returns:
        チャンネル名とIDのディクショナリ、またはエラー情報
    """
    slack_token = await get_session_slack_token(ctx)
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


@mcp.tool
async def post_message(
    ctx: Context, channel_id: str, text: str, user_id: Optional[str] = None
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

    slack_token = await get_session_slack_token(ctx)
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


@mcp.tool
async def get_auth_status(ctx: Context) -> dict:
    """認証状態とセッション情報を取得

    Returns:
        認証状態とセッション情報のディクショナリ
    """
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
async def get_session_info(ctx: Context) -> dict:
    """Get current session information"""
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


def run_with_http_endpoints():
    """Run MCP server with separate HTTP endpoints server"""
    # Create HTTP endpoint server for OAuth and health checks
    http_server = HTTPEndpointServer(token_verifier)

    # Run HTTP endpoints server in background
    import threading

    def run_http_server():
        import asyncio

        print("💡 Health check: http://0.0.0.0:8002/health")
        print("🔗 OAuth callback: http://0.0.0.0:8002/oauth/callback")
        print("📊 OAuth status: http://0.0.0.0:8002/oauth/status")
        asyncio.run(http_server.run(host="0.0.0.0", port=8002))

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # Run MCP server (synchronous)
    print("📍 MCP endpoint: http://0.0.0.0:8001")
    print("🔄 Using streamable-http transport")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)


def main():
    """Main entry point for the MCP server"""
    print("=== Slack MCP Server (FastMCP v2) ===")
    print("🚀 Starting Slack MCP server with session support...")
    print("📝 OAuth authentication will start automatically when tools are used")

    # Multi-port mode - MCP on 8001, HTTP endpoints on 8002
    print("🌐 Running in multi-port mode")

    try:
        # Run servers
        run_with_http_endpoints()
    finally:
        # Cleanup
        print("🔄 Slack MCP Server shutting down...")
        token_verifier.cleanup()
        print("✅ Cleanup completed")


if __name__ == "__main__":
    main()
