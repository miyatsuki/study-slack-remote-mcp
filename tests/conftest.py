import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from typing import Any, Dict

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def mock_env():
    """Mock environment variables for testing"""
    env_vars = {
        "SLACK_CLIENT_ID": "test_client_id",
        "SLACK_CLIENT_SECRET": "test_client_secret",
        "SERVICE_BASE_URL": "https://test.example.com",
        "AWS_REGION": "us-east-1",
        "DYNAMODB_TABLE_NAME": "test-slack-tokens",
        "MCP_ENV": "test"
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars

@pytest.fixture
def mock_storage():
    """Mock storage interface"""
    storage = AsyncMock()
    storage.save_item = AsyncMock()
    storage.get_item = AsyncMock()
    storage.delete_item = AsyncMock()
    storage.scan_items = AsyncMock()
    storage.cleanup_expired_tokens = AsyncMock()
    return storage

@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API calls"""
    with patch("httpx.AsyncClient") as mock_client:
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        yield client_instance

@pytest.fixture
def sample_oauth_token():
    """Sample OAuth token for testing"""
    return {
        "access_token": "xoxb-test-token",
        "token_type": "bearer",
        "scope": "chat:write,channels:read",
        "bot_user_id": "U123456",
        "app_id": "A123456",
        "team": {
            "id": "T123456",
            "name": "Test Workspace"
        },
        "authed_user": {
            "id": "U654321",
            "scope": "chat:write,channels:read",
            "access_token": "xoxp-test-token",
            "token_type": "bearer"
        }
    }

@pytest.fixture
def sample_client_info():
    """Sample client information for testing"""
    return {
        "client_id": "test_client_id",
        "client_name": "Test Client",
        "redirect_uris": ["https://test.example.com/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": "chat:write channels:read"
    }

@pytest.fixture
def mock_slack_api_response():
    """Mock Slack API responses"""
    return {
        "conversations.list": {
            "ok": True,
            "channels": [
                {
                    "id": "C123456",
                    "name": "general",
                    "is_channel": True,
                    "is_group": False,
                    "is_im": False,
                    "is_private": False,
                    "is_archived": False
                },
                {
                    "id": "C789012",
                    "name": "random",
                    "is_channel": True,
                    "is_group": False,
                    "is_im": False,
                    "is_private": False,
                    "is_archived": False
                }
            ]
        },
        "chat.postMessage": {
            "ok": True,
            "channel": "C123456",
            "ts": "1234567890.123456",
            "message": {
                "text": "Test message",
                "username": "Test Bot",
                "bot_id": "B123456",
                "type": "message",
                "subtype": "bot_message",
                "ts": "1234567890.123456"
            }
        },
        "auth.test": {
            "ok": True,
            "url": "https://test.slack.com/",
            "team": "Test Workspace",
            "user": "testbot",
            "team_id": "T123456",
            "user_id": "U123456"
        }
    }