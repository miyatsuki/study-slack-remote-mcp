import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from fastmcp import FastMCP
from mcp.server.models import OAuthTokenResponse


class TestMCPTools:
    """Test cases for MCP tools in server.py"""

    @pytest.fixture
    def mock_mcp_server(self, mock_env, mock_storage):
        """Create a mock MCP server instance"""
        with patch.dict("os.environ", mock_env):
            # We need to import after patching environment
            from server import mcp
            return mcp

    @pytest.mark.asyncio
    async def test_list_channels_success(self, mock_mcp_server, mock_httpx_client, mock_slack_api_response):
        """Test successful channel listing"""
        # Mock token exchange
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = "xoxb-test-token"
            
            # Mock Slack API response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_slack_api_response["conversations.list"]
            mock_httpx_client.get.return_value = mock_response
            
            # Call the tool
            from server import list_channels
            result = await list_channels(auth_token="mcp_test_token")
            
            assert result["general"] == "C123456"
            assert result["random"] == "C789012"
            assert len(result) == 2
            
            # Verify API call
            mock_httpx_client.get.assert_called_once()
            call_args = mock_httpx_client.get.call_args
            assert call_args[0][0] == "https://slack.com/api/conversations.list"
            assert call_args[1]["headers"]["Authorization"] == "Bearer xoxb-test-token"

    @pytest.mark.asyncio
    async def test_list_channels_no_token(self, mock_mcp_server):
        """Test channel listing without token"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = None
            
            from server import list_channels
            
            with pytest.raises(Exception) as exc_info:
                await list_channels(auth_token="invalid_token")
            
            assert "No Slack token found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_channels_api_error(self, mock_mcp_server, mock_httpx_client):
        """Test channel listing with API error"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = "xoxb-test-token"
            
            # Mock Slack API error response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": False,
                "error": "invalid_auth"
            }
            mock_httpx_client.get.return_value = mock_response
            
            from server import list_channels
            
            with pytest.raises(Exception) as exc_info:
                await list_channels(auth_token="mcp_test_token")
            
            assert "Slack API error: invalid_auth" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_post_message_success(self, mock_mcp_server, mock_httpx_client, mock_slack_api_response):
        """Test successful message posting"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = "xoxb-test-token"
            
            # Mock Slack API response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_slack_api_response["chat.postMessage"]
            mock_httpx_client.post.return_value = mock_response
            
            from server import post_message
            result = await post_message(
                channel_id="C123456",
                text="Test message",
                auth_token="mcp_test_token"
            )
            
            assert "Successfully posted message" in result
            
            # Verify API call
            mock_httpx_client.post.assert_called_once()
            call_args = mock_httpx_client.post.call_args
            assert call_args[0][0] == "https://slack.com/api/chat.postMessage"
            assert call_args[1]["json"]["channel"] == "C123456"
            assert call_args[1]["json"]["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_post_message_no_token(self, mock_mcp_server):
        """Test message posting without token"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = None
            
            from server import post_message
            
            with pytest.raises(Exception) as exc_info:
                await post_message(
                    channel_id="C123456",
                    text="Test message",
                    auth_token="invalid_token"
                )
            
            assert "No Slack token found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_auth_status_authenticated(self, mock_mcp_server, mock_httpx_client, mock_slack_api_response):
        """Test auth status when authenticated"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = "xoxb-test-token"
            
            # Mock Slack API auth.test response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_slack_api_response["auth.test"]
            mock_httpx_client.get.return_value = mock_response
            
            from server import get_auth_status
            result = await get_auth_status(auth_token="mcp_test_token")
            
            assert result["authenticated"] is True
            assert result["workspace"] == "Test Workspace"
            assert result["user"] == "testbot"
            assert "auth_url" not in result

    @pytest.mark.asyncio
    async def test_get_auth_status_not_authenticated(self, mock_mcp_server):
        """Test auth status when not authenticated"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = None
            
            from server import get_auth_status
            result = await get_auth_status(auth_token="new_token")
            
            assert result["authenticated"] is False
            assert "auth_url" in result
            assert "https://slack.com/oauth/v2/authorize" in result["auth_url"]
            assert result["message"] == "Please complete OAuth flow by visiting the auth_url"

    @pytest.mark.asyncio
    async def test_get_auth_status_invalid_token(self, mock_mcp_server, mock_httpx_client):
        """Test auth status with invalid Slack token"""
        with patch("server.oauth_provider.get_slack_token_for_mcp_token") as mock_get_token:
            mock_get_token.return_value = "xoxb-invalid-token"
            
            # Mock Slack API error response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": False,
                "error": "invalid_auth"
            }
            mock_httpx_client.get.return_value = mock_response
            
            from server import get_auth_status
            result = await get_auth_status(auth_token="mcp_test_token")
            
            assert result["authenticated"] is False
            assert result["error"] == "invalid_auth"
            assert "auth_url" in result