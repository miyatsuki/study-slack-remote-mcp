"""トークン検証の実装（セッション対応版）"""

from typing import Optional

from parameter_store import get_parameter_store_client
from session_manager import SessionTokenManager
from slack_auth_provider import SlackAuthProvider


class AccessToken:
    """アクセストークン情報を保持するクラス"""

    def __init__(
        self,
        token: str,
        client_id: str,
        scopes: list[str],
        expires_at: Optional[int] = None,
        resource: Optional[str] = None,
    ):
        self.token = token
        self.client_id = client_id
        self.scopes = scopes
        self.expires_at = expires_at
        self.resource = resource


class SlackTokenVerifier:
    """Slackのトークン検証を行うクラス（セッション対応版）"""

    def __init__(self):
        # Parameter Store または環境変数からSlackアプリのクレデンシャルを取得
        parameter_store = get_parameter_store_client()
        slack_config = parameter_store.get_slack_config()

        client_id = slack_config["client_id"]
        client_secret = slack_config["client_secret"]

        if not client_id or not client_secret:
            raise RuntimeError(
                "Slack Client IDまたはClient Secretが設定されていません。Parameter Store または環境変数を確認してください。"
            )

        # セッション管理とSlack認証プロバイダーを初期化
        self.session_manager = SessionTokenManager()
        self.auth_provider = SlackAuthProvider(
            client_id, client_secret, self.session_manager
        )

        # 現在のセッションID（簡易実装：将来的には適切にセッション管理）
        self.current_session_id: Optional[str] = None

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """トークンを検証し、アクセストークンを返す"""
        print(f"🔐 トークン検証を開始: {token[:20]}...")

        # セッションベースのトークン検証は現在無効
        # （FastMCPでは認証ヘッダーがない場合verify_tokenが呼ばれないため）
        print("❌ トークン検証に失敗しました - OAuth認証のみサポート")
        return None

    async def start_session_auth(self, client_info: Optional[dict] = None) -> str:
        """新しいセッションを作成し、OAuth認証を開始"""
        session_id = self.session_manager.create_session(client_info)
        self.current_session_id = session_id

        print(f"🔗 セッション {session_id[:8]}... でOAuth認証を開始...")
        await self.auth_provider.start_oauth_for_session(session_id)

        return session_id

    async def get_session_token(
        self, session_id: Optional[str] = None
    ) -> Optional[str]:
        """セッションのSlackトークンを取得"""
        if not session_id:
            session_id = self.current_session_id

        if not session_id:
            return None

        return await self.session_manager.get_slack_token(session_id)

    def get_session_status(self, session_id: Optional[str] = None) -> Optional[str]:
        """セッションの認証状態を取得"""
        if not session_id:
            session_id = self.current_session_id

        if not session_id:
            return None

        return self.session_manager.get_session_status(session_id)

    def list_sessions(self) -> dict:
        """全セッションの情報を取得（デバッグ用）"""
        return self.session_manager.list_sessions()

    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.auth_provider:
            self.auth_provider.cleanup()

        # 期限切れセッションのクリーンアップ
        self.session_manager.cleanup_expired_sessions()
