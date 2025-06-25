"""Slack認証プロバイダーの実装（セッション対応版）"""

import asyncio
import os
from typing import Dict, Optional

import httpx

from auth_server import AuthServer
from session_manager import SessionTokenManager
from storage_interface import create_token_storage, is_cloud_environment
from parameter_store import get_parameter_store_client


class SlackAuthProvider:
    """Slack OAuth認証プロバイダー（セッション対応版）"""

    def __init__(
        self, client_id: str, client_secret: str, session_manager: SessionTokenManager
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = "chat:write,channels:read"
        self.session_manager = session_manager
        self.auth_server: Optional[AuthServer] = None
        self.token_storage = create_token_storage()
        self.is_cloud = is_cloud_environment()

    async def start_oauth_for_session(self, session_id: str) -> bool:
        """指定セッションのOAuth認証を開始（永続化されたトークンをチェック）"""
        print(f"🔐 セッション {session_id[:8]}... のOAuth認証を開始します...")

        # 1. 永続化されたトークンをチェック
        persisted_token = self.token_storage.load_token(self.client_id)
        if persisted_token:
            # トークンが有効かSlack APIで確認
            if await self._validate_slack_token(persisted_token):
                print(f"✅ 永続化されたトークンを使用します (クライアント: {self.client_id[:8]}...)")
                self.session_manager.set_slack_token(session_id, persisted_token)
                return True
            else:
                print(f"⚠️ 永続化されたトークンが無効です。新しいトークンを取得します...")

        # 2. 新しいOAuth認証を実行
        if self.is_cloud:
            # クラウド環境では手動認証フローを使用
            success = await self._perform_cloud_oauth_flow(session_id)
        else:
            # ローカル環境では従来のOAuth認証を使用
            token = await self._perform_oauth_flow(session_id)
            success = bool(token)
            if success:
                # セッションに設定
                self.session_manager.set_slack_token(session_id, token)
                # 永続化（Slackトークンは通常期限なし、但し安全のため1年を設定）
                self.token_storage.save_token(self.client_id, token, expires_in_seconds=365*24*60*60)

        if success:
            print(f"✅ セッション {session_id[:8]}... のOAuth認証が完了し、トークンを永続化しました")
            return True

        print(f"❌ セッション {session_id[:8]}... のOAuth認証に失敗しました")
        return False

    async def get_session_token(self, session_id: str) -> Optional[str]:
        """セッションのSlackトークンを取得"""
        return await self.session_manager.get_slack_token(session_id)

    async def _validate_slack_token(self, slack_token: str) -> bool:
        """SlackトークンをSlack APIで検証"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {slack_token}"},
                )
                data = response.json()
                return data.get("ok", False)
        except Exception:
            return False

    async def _perform_oauth_flow(self, session_id: str) -> Optional[str]:
        """OAuth認証フローを実行"""
        try:
            # 認証サーバーを起動
            self.auth_server = AuthServer(self.client_id, self.client_secret)
            port = self.auth_server.start_callback_server()

            if not port:
                print("❌ 認証サーバーの起動に失敗しました")
                return None

            # OAuth URLを生成してブラウザで開く
            oauth_url = self.auth_server.make_oauth_request(self.scope)
            if not oauth_url:
                print("❌ OAuth URLの生成に失敗しました")
                return None

            print(f"🌐 セッション {session_id[:8]}... のブラウザでOAuth認証を開始...")
            print(f"📋 OAuth URL: {oauth_url}")

            # 認証完了を待機
            code = await self.auth_server.wait_for_auth_completion()
            if not code:
                print("❌ 認証コードの取得に失敗しました")
                return None

            # トークンに交換
            token_data = self.auth_server.exchange_code_for_token(code)

            if token_data.get("ok"):
                slack_token = token_data.get("access_token")
                if slack_token:
                    return slack_token

            print(f"❌ トークン取得失敗: {token_data.get('error', 'unknown_error')}")
            return None

        except Exception as e:
            print(f"❌ OAuth認証エラー: {e}")
            return None
        finally:
            # 認証サーバーをクリーンアップ
            if self.auth_server:
                self.auth_server.shutdown()
                self.auth_server = None

    async def _perform_cloud_oauth_flow(self, session_id: str) -> bool:
        """クラウド環境でのOAuth認証フロー（手動認証）"""
        try:
            # クラウド環境では、Parameter Store からサービスのパブリックURLを取得
            parameter_store = get_parameter_store_client()
            slack_config = parameter_store.get_slack_config()
            base_url = slack_config['service_base_url']
            
            if not base_url:
                print("❌ SERVICE_BASE_URL パラメータが設定されていません")
                print("💡 Parameter Store に /slack-mcp/service-base-url を設定してください")
                return False
            
            callback_url = f"{base_url}/oauth/callback"
            oauth_url = self._generate_oauth_url(callback_url)
            
            print("="*60)
            print("🌩️ クラウドOAuth認証 - 手動認証が必要です")
            print("="*60)
            print(f"1. 以下のURLをブラウザで開いてください:")
            print(f"   {oauth_url}")
            print("")
            print(f"2. Slack認証完了後、以下のエンドポイントでトークンを確認できます:")
            print(f"   {base_url}/oauth/status")
            print("")
            print("3. 認証が完了したら、MCP ツールを再度実行してください")
            print("="*60)
            
            return False  # 手動認証のため、ここでは完了しない
            
        except Exception as e:
            print(f"❌ クラウドOAuth認証エラー: {e}")
            return False
    
    def _generate_oauth_url(self, redirect_uri: str) -> str:
        """OAuth URLを生成"""
        import urllib.parse
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.scope,
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"https://slack.com/oauth/v2/authorize?{query_string}"

    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.auth_server:
            self.auth_server.shutdown()
            self.auth_server = None
        
        # 期限切れトークンのクリーンアップ
        self.token_storage.cleanup_expired_tokens()
