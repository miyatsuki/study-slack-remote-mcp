"""セッション管理とトークンキャッシュ"""

import time
import uuid
from typing import Dict, Optional

import httpx


class SessionTokenManager:
    """MCPセッションとSlackトークンのマッピング管理"""

    def __init__(self):
        # session_id -> {"slack_token": str, "created_at": float, "client_info": dict}
        self.session_tokens: Dict[str, Dict] = {}
        # OAuth認証進行中のセッション
        self.pending_sessions: Dict[str, Dict] = {}

    def create_session(self, client_info: Optional[Dict] = None) -> str:
        """新しいセッションを作成し、セッションIDを返す"""
        session_id = str(uuid.uuid4())

        # クライアント情報から一意な識別子を生成
        client_name = "unknown"
        if client_info:
            client_name = client_info.get("name", "unknown")

        print(
            f"🆔 新しいセッションを作成: {session_id[:8]}... (クライアント: {client_name})"
        )

        # セッション情報を初期化
        self.session_tokens[session_id] = {
            "slack_token": None,
            "created_at": time.time(),
            "client_info": client_info or {},
            "status": "pending_auth",  # pending_auth, authenticated, failed
        }

        return session_id

    async def get_slack_token(self, session_id: str) -> Optional[str]:
        """セッションIDに対応するSlackトークンを取得"""
        if session_id not in self.session_tokens:
            return None

        session_data = self.session_tokens[session_id]
        slack_token = session_data.get("slack_token")

        if slack_token:
            # トークンが有効かチェック
            if await self._validate_slack_token(slack_token):
                return slack_token
            else:
                # 無効なトークンを削除
                print(f"⚠️ セッション {session_id[:8]}... の無効なトークンを削除")
                session_data["slack_token"] = None
                session_data["status"] = "pending_auth"

        return None

    def set_slack_token(self, session_id: str, slack_token: str):
        """セッションIDにSlackトークンを設定"""
        if session_id in self.session_tokens:
            self.session_tokens[session_id]["slack_token"] = slack_token
            self.session_tokens[session_id]["status"] = "authenticated"
            print(f"✅ セッション {session_id[:8]}... にSlackトークンを設定")
        else:
            print(f"❌ セッション {session_id[:8]}... が見つかりません")

    def remove_session(self, session_id: str):
        """セッションを削除"""
        if session_id in self.session_tokens:
            client_info = self.session_tokens[session_id].get("client_info", {})
            client_name = client_info.get("name", "unknown")
            print(
                f"🗑️ セッション {session_id[:8]}... を削除 (クライアント: {client_name})"
            )
            del self.session_tokens[session_id]

        if session_id in self.pending_sessions:
            del self.pending_sessions[session_id]

    def get_session_status(self, session_id: str) -> Optional[str]:
        """セッションの認証状態を取得"""
        if session_id in self.session_tokens:
            return self.session_tokens[session_id].get("status")
        return None

    def list_sessions(self) -> Dict[str, Dict]:
        """全セッションの情報を取得（デバッグ用）"""
        result = {}
        for session_id, data in self.session_tokens.items():
            result[session_id[:8]] = {
                "status": data.get("status"),
                "client": data.get("client_info", {}).get("name", "unknown"),
                "created_at": data.get("created_at"),
                "has_token": bool(data.get("slack_token")),
            }
        return result

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

    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """古いセッションをクリーンアップ"""
        current_time = time.time()
        expired_sessions = []

        for session_id, data in self.session_tokens.items():
            age_hours = (current_time - data["created_at"]) / 3600
            if age_hours > max_age_hours:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            print(f"🕒 期限切れセッション {session_id[:8]}... を削除")
            self.remove_session(session_id)
