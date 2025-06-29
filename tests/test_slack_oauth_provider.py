import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mcp.server.models import OAuthAuthorizationRequest, OAuthTokenRequest, OAuthClientInformationFull
from slack_oauth_provider import SlackOAuthProvider
import httpx


class TestSlackOAuthProvider:
    """Test cases for SlackOAuthProvider"""

    @pytest.mark.asyncio
    async def test_init(self, mock_env, mock_storage):
        """Test provider initialization"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        assert provider.client_id == "test_client_id"
        assert provider.client_secret == "test_client_secret"
        assert provider.base_url == "https://test.example.com"
        assert provider.storage == mock_storage

    @pytest.mark.asyncio
    async def test_register_client(self, mock_env, mock_storage):
        """Test client registration"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        client_info = OAuthClientInformationFull(
            client_id="test_client_123",
            client_name="Test Client",
            redirect_uris=["https://test.com/callback"],
            grant_types=["authorization_code"],
            response_types=["code"],
            scope="test:scope"
        )
        
        await provider.register_client(client_info)
        
        mock_storage.save_item.assert_called_once_with(
            "client:test_client_123",
            {
                "client_id": "test_client_123",
                "client_name": "Test Client",
                "redirect_uris": ["https://test.com/callback"]
            }
        )

    @pytest.mark.asyncio
    async def test_get_client_registered(self, mock_env, mock_storage):
        """Test getting a registered client"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        mock_storage.get_item.return_value = {
            "client_id": "test_client_123",
            "client_name": "Test Client",
            "redirect_uris": ["https://test.com/callback"]
        }
        
        client = await provider.get_client("test_client_123")
        
        assert client is not None
        assert client.client_id == "test_client_123"
        assert client.client_name == "Test Client"
        assert client.redirect_uris == ["https://test.com/callback"]

    @pytest.mark.asyncio
    async def test_get_client_not_registered(self, mock_env, mock_storage):
        """Test getting a non-registered client (dynamic registration)"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        mock_storage.get_item.return_value = None
        
        client = await provider.get_client("unknown_client")
        
        assert client is not None
        assert client.client_id == "unknown_client"
        assert client.client_name == "unknown_client"
        assert client.redirect_uris == []

    @pytest.mark.asyncio
    async def test_get_slack_authorization_url(self, mock_env, mock_storage):
        """Test getting Slack authorization URL"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        request = OAuthAuthorizationRequest(
            response_type="code",
            client_id="test_client",
            redirect_uri="https://test.com/callback",
            scope="chat:write channels:read",
            state="test_state"
        )
        
        auth_url = await provider.get_slack_authorization_url(request)
        
        assert "https://slack.com/oauth/v2/authorize" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "redirect_uri=https%3A%2F%2Ftest.example.com%2Fslack%2Fcallback" in auth_url
        assert "scope=chat%3Awrite+channels%3Aread" in auth_url
        assert "state=" in auth_url

    @pytest.mark.asyncio
    async def test_exchange_slack_code_success(self, mock_env, mock_storage, mock_httpx_client, sample_oauth_token):
        """Test successful Slack code exchange"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            **sample_oauth_token
        }
        mock_httpx_client.post.return_value = mock_response
        
        token_data = await provider.exchange_slack_code("test_code", "test_state")
        
        assert token_data["access_token"] == "xoxb-test-token"
        assert token_data["scope"] == "chat:write,channels:read"
        
        mock_httpx_client.post.assert_called_once_with(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "code": "test_code",
                "redirect_uri": "https://test.example.com/slack/callback"
            }
        )

    @pytest.mark.asyncio
    async def test_exchange_slack_code_failure(self, mock_env, mock_storage, mock_httpx_client):
        """Test failed Slack code exchange"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "error": "invalid_code"
        }
        mock_httpx_client.post.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            await provider.exchange_slack_code("bad_code", "test_state")
        
        assert "Slack OAuth error: invalid_code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_token_exchange_success(self, mock_env, mock_storage, sample_oauth_token):
        """Test successful MCP token exchange"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        # Mock Slack token retrieval
        mock_storage.get_item.return_value = {
            "slack_token": sample_oauth_token["access_token"],
            "scope": sample_oauth_token["scope"],
            "user_id": "U123456",
            "team_id": "T123456"
        }
        
        request = OAuthTokenRequest(
            grant_type="authorization_code",
            code="mcp_token_123",
            redirect_uri="https://test.com/callback",
            client_id="test_client"
        )
        
        response = await provider.token_exchange(request)
        
        assert response.access_token == "mcp_token_123"
        assert response.token_type == "bearer"
        assert response.scope == "chat:write,channels:read"

    @pytest.mark.asyncio
    async def test_token_exchange_invalid_token(self, mock_env, mock_storage):
        """Test MCP token exchange with invalid token"""
        provider = SlackOAuthProvider(
            client_id=mock_env["SLACK_CLIENT_ID"],
            client_secret=mock_env["SLACK_CLIENT_SECRET"],
            base_url=mock_env["SERVICE_BASE_URL"],
            storage=mock_storage
        )
        
        # Mock no token found
        mock_storage.get_item.return_value = None
        
        request = OAuthTokenRequest(
            grant_type="authorization_code",
            code="invalid_token",
            redirect_uri="https://test.com/callback",
            client_id="test_client"
        )
        
        with pytest.raises(Exception) as exc_info:
            await provider.token_exchange(request)
        
        assert "Token not found" in str(exc_info.value)