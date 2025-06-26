"""Abstract storage interface for token persistence"""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class TokenStorageInterface(ABC):
    """Abstract interface for token storage backends"""

    @abstractmethod
    def save_token(
        self, client_id: str, token: str, expires_in_seconds: Optional[int] = None
    ) -> bool:
        """Save a token for a client"""
        pass

    @abstractmethod
    def load_token(self, client_id: str) -> Optional[str]:
        """Load a valid token for a client"""
        pass

    @abstractmethod
    def cleanup_expired_tokens(self):
        """Remove expired tokens"""
        pass

    @abstractmethod
    def list_tokens(self) -> List[Dict]:
        """List all stored tokens (for debugging)"""
        pass


def create_token_storage() -> TokenStorageInterface:
    """Factory function to create appropriate token storage based on environment"""

    # Check if we're running in AWS (Fargate/ECS)
    if os.getenv("AWS_EXECUTION_ENV") or os.getenv("ECS_CONTAINER_METADATA_URI_V4"):
        print("🌩️ AWS環境を検出 - DynamoDBストレージを使用します")
        from storage_dynamodb import DynamoDBTokenStorage

        return DynamoDBTokenStorage()
    else:
        print("💻 ローカル環境を検出 - JSONLストレージを使用します")
        from token_storage import TokenStorage

        return TokenStorage()


def is_cloud_environment() -> bool:
    """Check if running in cloud environment"""
    return bool(
        os.getenv("AWS_EXECUTION_ENV") or os.getenv("ECS_CONTAINER_METADATA_URI_V4")
    )
