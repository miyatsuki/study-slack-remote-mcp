"""HTTP endpoints for OAuth callback and health check"""

from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from parameter_store import get_parameter_store_client
from storage_interface import is_cloud_environment
from token_verifier import SlackTokenVerifier


class HTTPEndpointServer:
    """Separate HTTP server for OAuth and health endpoints"""

    def __init__(self, token_verifier: SlackTokenVerifier):
        self.token_verifier = token_verifier
        self.app = FastAPI(
            title="Slack MCP HTTP Endpoints", version="1.0.0", lifespan=self._lifespan
        )
        self._setup_routes()

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """FastAPI application lifecycle management"""
        print("🌐 HTTP endpoint server starting up...")
        yield
        print("🌐 HTTP endpoint server shutting down...")

    def _setup_routes(self):
        """Set up HTTP routes"""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for Fargate"""
            return {
                "status": "healthy",
                "service": "slack-mcp-server",
                "environment": "cloud" if is_cloud_environment() else "local",
            }

        @self.app.get("/oauth/callback")
        async def oauth_callback(request: Request):
            """OAuth callback endpoint for cloud deployment"""
            query_params = dict(request.query_params)

            if "code" in query_params:
                # Handle OAuth success
                code = query_params["code"]

                # Exchange code for token
                try:
                    token_data = await self._exchange_oauth_code(code)
                    if token_data and token_data.get("ok"):
                        # Save token to storage
                        parameter_store = get_parameter_store_client()
                        slack_config = parameter_store.get_slack_config()
                        client_id = slack_config["client_id"]
                        access_token = token_data.get("access_token")

                        if client_id and access_token:
                            self.token_verifier.auth_provider.token_storage.save_token(
                                client_id,
                                access_token,
                                expires_in_seconds=365 * 24 * 60 * 60,
                            )

                            return HTMLResponse(
                                """
                            <html>
                            <head><title>認証完了</title></head>
                            <body>
                                <h1>✅ Slack認証が完了しました</h1>
                                <p>トークンが正常に保存されました。</p>
                                <p>MCP クライアントでツールを実行してください。</p>
                            </body>
                            </html>
                            """
                            )

                    return HTMLResponse(
                        """
                    <html>
                    <head><title>認証エラー</title></head>
                    <body>
                        <h1>❌ トークン取得に失敗しました</h1>
                        <p>もう一度認証をやり直してください。</p>
                    </body>
                    </html>
                    """
                    )

                except Exception as e:
                    return HTMLResponse(
                        f"""
                    <html>
                    <head><title>認証エラー</title></head>
                    <body>
                        <h1>❌ 認証処理でエラーが発生しました</h1>
                        <p>エラー: {e}</p>
                    </body>
                    </html>
                    """
                    )

            elif "error" in query_params:
                error = query_params["error"]
                return HTMLResponse(
                    f"""
                <html>
                <head><title>認証エラー</title></head>
                <body>
                    <h1>❌ Slack認証でエラーが発生しました</h1>
                    <p>エラー: {error}</p>
                </body>
                </html>
                """
                )

            return HTMLResponse(
                """
            <html>
            <head><title>不正なリクエスト</title></head>
            <body>
                <h1>⚠️ 不正なOAuthリクエスト</h1>
                <p>認証コードまたはエラーパラメータが見つかりません。</p>
            </body>
            </html>
            """
            )

        @self.app.get("/oauth/status")
        async def oauth_status():
            """OAuth authentication status endpoint"""
            parameter_store = get_parameter_store_client()
            slack_config = parameter_store.get_slack_config()
            client_id = slack_config["client_id"]

            if not client_id:
                return {"error": "SLACK_CLIENT_ID not configured"}

            # Check if token exists
            token = self.token_verifier.auth_provider.token_storage.load_token(
                client_id
            )
            has_token = bool(token)

            return {
                "client_id": client_id[:8] + "...",
                "has_valid_token": has_token,
                "storage_backend": type(
                    self.token_verifier.auth_provider.token_storage
                ).__name__,
                "environment": "cloud" if is_cloud_environment() else "local",
            }

    async def _exchange_oauth_code(self, code: str) -> Optional[dict]:
        """Exchange OAuth authorization code for access token"""
        parameter_store = get_parameter_store_client()
        slack_config = parameter_store.get_slack_config()

        client_id = slack_config["client_id"]
        client_secret = slack_config["client_secret"]

        if not client_id or not client_secret:
            return None

        # Build redirect URI based on environment
        if is_cloud_environment():
            base_url = slack_config["service_base_url"]
            if not base_url:
                return None
            redirect_uri = f"{base_url}/oauth/callback"
        else:
            redirect_uri = "https://localhost:8443"

        token_url = "https://slack.com/api/oauth.v2.access"
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"❌ OAuth token exchange error: {e}")
            return None

    async def run(self, host: str = "0.0.0.0", port: int = 8002):
        """Run the HTTP endpoint server"""
        import uvicorn

        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()
