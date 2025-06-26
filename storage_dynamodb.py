"""DynamoDB-based token storage for cloud deployment"""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from storage_interface import TokenStorageInterface


class DynamoDBTokenStorage(TokenStorageInterface):
    """DynamoDB-based token storage for AWS deployment"""

    def __init__(self, table_name: str = None, region: str = None):
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for DynamoDB storage. Install with: pip install boto3"
            )

        self.table_name = table_name or os.getenv(
            "DYNAMODB_TABLE_NAME", "slack-mcp-tokens"
        )
        self.region = region or os.getenv("AWS_REGION", "ap-northeast-1")

        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)
            self._ensure_table_exists()
        except NoCredentialsError:
            print(
                "❌ AWS認証情報が見つかりません。IAMロールまたは環境変数を設定してください。"
            )
            raise
        except Exception as e:
            print(f"❌ DynamoDB接続エラー: {e}")
            raise

    def _ensure_table_exists(self):
        """Create DynamoDB table if it doesn't exist"""
        try:
            # Test if table exists by describing it
            self.table.load()
            print(f"✅ DynamoDBテーブル '{self.table_name}' を使用します")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"📝 DynamoDBテーブル '{self.table_name}' を作成中...")
                self._create_table()
            else:
                raise

    def _create_table(self):
        """Create the DynamoDB table"""
        try:
            table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[{"AttributeName": "client_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "client_id", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
                Tags=[
                    {"Key": "Application", "Value": "slack-mcp-server"},
                    {
                        "Key": "Environment",
                        "Value": os.getenv("ENVIRONMENT", "production"),
                    },
                ],
            )

            # Wait for table to be created
            table.wait_until_exists()
            self.table = table
            print(f"✅ DynamoDBテーブル '{self.table_name}' を作成しました")

        except ClientError as e:
            print(f"❌ DynamoDBテーブル作成エラー: {e}")
            raise

    def save_token(
        self, client_id: str, token: str, expires_in_seconds: Optional[int] = None
    ) -> bool:
        """Save Slack token to DynamoDB"""
        try:
            # Calculate expiration timestamp
            expiration = None
            if expires_in_seconds:
                expiration = int(time.time() + expires_in_seconds)

            # Create token record
            item = {
                "client_id": client_id,
                "token": token,
                "created_at": int(time.time()),
                "created_date": datetime.now().isoformat(),
            }

            if expiration:
                item["expires_at"] = expiration

            # Save to DynamoDB
            self.table.put_item(Item=item)

            print(
                f"✅ トークンをDynamoDBに保存しました (クライアント: {client_id[:8]}...)"
            )
            return True

        except ClientError as e:
            print(f"❌ DynamoDBトークン保存エラー: {e}")
            return False
        except Exception as e:
            print(f"❌ トークン保存エラー: {e}")
            return False

    def load_token(self, client_id: str) -> Optional[str]:
        """Load valid Slack token for client_id from DynamoDB"""
        try:
            response = self.table.get_item(Key={"client_id": client_id})

            if "Item" not in response:
                return None

            item = response["Item"]

            # Check if token is expired
            if self._is_token_expired(item):
                print(
                    f"⚠️ DynamoDB保存トークンが期限切れです (クライアント: {client_id[:8]}...)"
                )
                # Delete expired token
                self.table.delete_item(Key={"client_id": client_id})
                return None

            print(
                f"✅ DynamoDB保存トークンを使用します (クライアント: {client_id[:8]}...)"
            )
            return item.get("token")

        except ClientError as e:
            print(f"❌ DynamoDBトークン読み込みエラー: {e}")
            return None
        except Exception as e:
            print(f"❌ トークン読み込みエラー: {e}")
            return None

    def _is_token_expired(self, item: Dict) -> bool:
        """Check if token record is expired"""
        expires_at = item.get("expires_at")
        if expires_at is None:
            return False  # No expiration set

        return time.time() >= expires_at

    def cleanup_expired_tokens(self):
        """Remove all expired tokens from DynamoDB"""
        try:
            # Scan for all items (in production, consider using pagination for large datasets)
            response = self.table.scan()
            items = response.get("Items", [])

            expired_count = 0
            for item in items:
                if self._is_token_expired(item):
                    self.table.delete_item(Key={"client_id": item["client_id"]})
                    expired_count += 1

            if expired_count > 0:
                print(
                    f"🧹 DynamoDBから期限切れトークン {expired_count} 件を削除しました"
                )

        except ClientError as e:
            print(f"❌ DynamoDBトークンクリーンアップエラー: {e}")
        except Exception as e:
            print(f"❌ トークンクリーンアップエラー: {e}")

    def list_tokens(self) -> List[Dict]:
        """List all stored tokens (for debugging)"""
        tokens = []
        try:
            response = self.table.scan()
            items = response.get("Items", [])

            for item in items:
                # Don't expose actual token, just metadata
                safe_record = {
                    "client_id": str(item.get("client_id", ""))[:8] + "...",
                    "created_date": item.get("created_date", ""),
                    "expired": self._is_token_expired(item),
                    "has_expiration": "expires_at" in item,
                    "storage_backend": "DynamoDB",
                }
                tokens.append(safe_record)

        except ClientError as e:
            print(f"❌ DynamoDBトークン一覧取得エラー: {e}")
        except Exception as e:
            print(f"❌ トークン一覧取得エラー: {e}")

        return tokens
