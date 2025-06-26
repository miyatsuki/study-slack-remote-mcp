"""Slack token persistence using JSONL file storage"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from storage_interface import TokenStorageInterface


class TokenStorage(TokenStorageInterface):
    """Simple JSONL-based token storage for Slack OAuth tokens"""

    def __init__(self, storage_file: str = "slack_tokens.jsonl"):
        self.storage_file = storage_file
        self.ensure_storage_file_exists()

    def ensure_storage_file_exists(self):
        """Create storage file if it doesn't exist"""
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, "w") as f:
                pass  # Create empty file

    def save_token(
        self, client_id: str, token: str, expires_in_seconds: Optional[int] = None
    ) -> bool:
        """
        Save Slack token to JSONL file

        Args:
            client_id: Slack client ID
            token: Slack access token
            expires_in_seconds: Token expiration in seconds (None for no expiration)

        Returns:
            bool: True if saved successfully
        """
        try:
            # Calculate expiration timestamp
            expiration = None
            if expires_in_seconds:
                expiration = time.time() + expires_in_seconds

            # Create token record
            token_record = {
                "client_id": client_id,
                "token": token,
                "created_at": time.time(),
                "expires_at": expiration,
                "created_date": datetime.now().isoformat(),
            }

            # Remove existing token for this client_id first
            self._remove_token_for_client(client_id)

            # Append new token record
            with open(self.storage_file, "a") as f:
                f.write(json.dumps(token_record) + "\n")

            print(f"✅ トークンを保存しました (クライアント: {client_id[:8]}...)")
            return True

        except Exception as e:
            print(f"❌ トークン保存エラー: {e}")
            return False

    def load_token(self, client_id: str) -> Optional[str]:
        """
        Load valid Slack token for client_id

        Args:
            client_id: Slack client ID

        Returns:
            str: Valid token or None if not found/expired
        """
        try:
            if not os.path.exists(self.storage_file):
                return None

            with open(self.storage_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        if record.get("client_id") == client_id:
                            # Check if token is expired
                            if self._is_token_expired(record):
                                print(
                                    f"⚠️ 保存されたトークンが期限切れです (クライアント: {client_id[:8]}...)"
                                )
                                return None

                            print(
                                f"✅ 保存されたトークンを使用します (クライアント: {client_id[:8]}...)"
                            )
                            return record.get("token")
                    except json.JSONDecodeError:
                        continue

            return None

        except Exception as e:
            print(f"❌ トークン読み込みエラー: {e}")
            return None

    def _is_token_expired(self, record: Dict) -> bool:
        """Check if token record is expired"""
        expires_at = record.get("expires_at")
        if expires_at is None:
            return False  # No expiration set

        return time.time() >= expires_at

    def _remove_token_for_client(self, client_id: str):
        """Remove existing token records for a specific client_id"""
        try:
            if not os.path.exists(self.storage_file):
                return

            # Read all records except the ones for this client_id
            records_to_keep = []
            with open(self.storage_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        if record.get("client_id") != client_id:
                            records_to_keep.append(line)
                    except json.JSONDecodeError:
                        records_to_keep.append(line)  # Keep invalid JSON as-is

            # Rewrite file with remaining records
            with open(self.storage_file, "w") as f:
                for record in records_to_keep:
                    f.write(record + "\n")

        except Exception as e:
            print(f"❌ トークン削除エラー: {e}")

    def cleanup_expired_tokens(self):
        """Remove all expired tokens from storage"""
        try:
            if not os.path.exists(self.storage_file):
                return

            valid_records = []
            expired_count = 0

            with open(self.storage_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        if not self._is_token_expired(record):
                            valid_records.append(line)
                        else:
                            expired_count += 1
                    except json.JSONDecodeError:
                        valid_records.append(line)  # Keep invalid JSON as-is

            # Rewrite file with only valid records
            with open(self.storage_file, "w") as f:
                for record in valid_records:
                    f.write(record + "\n")

            if expired_count > 0:
                print(f"🧹 期限切れトークン {expired_count} 件を削除しました")

        except Exception as e:
            print(f"❌ トークンクリーンアップエラー: {e}")

    def list_tokens(self) -> List[Dict]:
        """List all stored tokens (for debugging)"""
        tokens = []
        try:
            if not os.path.exists(self.storage_file):
                return tokens

            with open(self.storage_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        # Don't expose actual token, just metadata
                        safe_record = {
                            "client_id": record.get("client_id", "")[:8] + "...",
                            "created_date": record.get("created_date", ""),
                            "expired": self._is_token_expired(record),
                            "has_expiration": record.get("expires_at") is not None,
                            "storage_backend": "JSONL",
                        }
                        tokens.append(safe_record)
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"❌ トークン一覧取得エラー: {e}")

        return tokens
