"""Slack OAuth Provider implementation for MCP FastMCP framework."""

import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from storage_interface import is_cloud_environment


class SlackAuthorizationCode(AuthorizationCode):
    """Slack-specific authorization code with additional fields."""

    slack_state: str | None = None


class SlackRefreshToken(RefreshToken):
    """Slack-specific refresh token."""

    pass


class SlackAccessToken(AccessToken):
    """Slack-specific access token."""

    pass


class SlackOAuthProvider:
    """
    Slack OAuth provider implementation for MCP FastMCP framework.

    This provider implements the OAuthAuthorizationServerProvider protocol
    to handle Slack OAuth 2.0 authentication flow.
    """

    def __init__(self):
        self.client_id = os.getenv("SLACK_CLIENT_ID")
        self.client_secret = os.getenv("SLACK_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError("SLACK_CLIENT_ID and SLACK_CLIENT_SECRET must be set")

        # Storage for authorization codes and tokens
        self.storage = self._create_storage()

        # In-memory storage for authorization codes (short-lived)
        self.authorization_codes: Dict[str, SlackAuthorizationCode] = {}

        # Slack OAuth scopes
        self.default_scopes = ["chat:write", "channels:read"]

    def _get_slack_redirect_uri(self) -> str:
        """Get the correct Slack redirect URI based on environment."""
        base_url = os.getenv("SERVICE_BASE_URL")
        if base_url:
            # Cloud environment
            return f"{base_url}/slack/callback"
        else:
            # Local development
            return "http://localhost:8080/slack/callback"

    def _create_storage(self):
        """Create appropriate storage backend based on environment."""
        if is_cloud_environment():
            # Use DynamoDB in cloud
            import boto3

            dynamodb = boto3.resource("dynamodb")
            table_name = os.getenv(
                "DYNAMODB_TABLE_NAME", f"slack-mcp-tokens-{os.getenv('MCP_ENV', 'dev')}"
            )

            class DynamoDBStorage:
                def __init__(self, table_name):
                    self.table = dynamodb.Table(table_name)

                async def save_item(
                    self, key: str, value: Dict[str, Any], ttl: Optional[int] = None
                ):
                    """Save an item to DynamoDB."""
                    item = {
                        "client_id": key,
                        "data": value,
                    }
                    if ttl:
                        item["expires_at"] = int(time.time()) + ttl
                    self.table.put_item(Item=item)

                async def get_item(self, key: str) -> Optional[Dict[str, Any]]:
                    """Get an item from DynamoDB."""
                    try:
                        response = self.table.get_item(Key={"client_id": key})
                        if "Item" in response:
                            return response["Item"].get("data")
                    except Exception:
                        pass
                    return None

                async def delete_item(self, key: str):
                    """Delete an item from DynamoDB."""
                    try:
                        self.table.delete_item(Key={"client_id": key})
                    except Exception:
                        pass

            return DynamoDBStorage(table_name)
        else:
            # Use in-memory storage for local development
            class InMemoryStorage:
                def __init__(self):
                    self.data: Dict[str, Any] = {}

                async def save_item(
                    self, key: str, value: Dict[str, Any], ttl: Optional[int] = None
                ):
                    """Save an item to memory."""
                    self.data[key] = {
                        "value": value,
                        "expires_at": time.time() + ttl if ttl else None,
                    }

                async def get_item(self, key: str) -> Optional[Dict[str, Any]]:
                    """Get an item from memory."""
                    if key in self.data:
                        item = self.data[key]
                        if (
                            item["expires_at"] is None
                            or time.time() < item["expires_at"]
                        ):
                            return item["value"]
                        else:
                            # Expired, remove it
                            del self.data[key]
                    return None

                async def delete_item(self, key: str):
                    """Delete an item from memory."""
                    if key in self.data:
                        del self.data[key]

            return InMemoryStorage()

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """
        Get client information by ID.

        For Slack integration, we accept any client ID but always return
        our Slack app configuration.
        """
        # Accept any client ID for dynamic registration support
        return OAuthClientInformationFull(
            client_id=client_id,  # Use the requested client_id
            client_name="Slack MCP Server",
            redirect_uris=[
                "http://localhost/redirect",  # Generic redirect URI for MCP clients
                "http://localhost:12345/callback",  # Common VSCode MCP redirect
                "http://localhost:8080/oauth/callback",
                "https://localhost:8080/oauth/callback",
                # Production URLs
                f"{os.getenv('SERVICE_BASE_URL', 'http://localhost:8080')}/oauth/callback",
            ],
        )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """
        Register a new client.

        For Slack integration, we accept any client registration but use our
        pre-configured Slack app for the actual OAuth flow.
        """
        # Log the client registration for debugging
        print(f"Client registration request:")
        print(f"  client_id: {client_info.client_id}")
        print(f"  client_name: {client_info.client_name}")
        print(f"  redirect_uris: {client_info.redirect_uris}")
        print(f"  grant_types: {client_info.grant_types}")
        print(f"  response_types: {client_info.response_types}")
        print(f"  token_endpoint_auth_method: {client_info.token_endpoint_auth_method}")
        print(f"  scope: {client_info.scope}")
        
        # Store the client info for later retrieval
        # Note: In production, you'd want to persist this to a database
        await self.storage.save_item(f"client:{client_info.client_id}", {
            "client_id": client_info.client_id,
            "client_name": client_info.client_name,
            "redirect_uris": list(client_info.redirect_uris) if client_info.redirect_uris else [],
        })

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """
        Start the authorization flow by redirecting to Slack's OAuth page.

        This initiates the Slack OAuth flow where the user will authorize
        the app to access their Slack workspace.
        """
        # Generate a unique state parameter for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store the authorization params with the state for later verification
        self.authorization_codes[state] = SlackAuthorizationCode(
            code="",  # Will be filled after Slack callback
            scopes=params.scopes or self.default_scopes,
            expires_at=time.time() + 600,  # 10 minutes
            client_id=client.client_id,  # Store the MCP client ID
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            slack_state=state,
        )

        # Build Slack OAuth URL
        slack_params = {
            "client_id": self.client_id,
            "scope": " ".join(params.scopes or self.default_scopes),
            "redirect_uri": self._get_slack_redirect_uri(),
            "state": state,
        }

        slack_auth_url = (
            f"https://slack.com/oauth/v2/authorize?{urlencode(slack_params)}"
        )
        return slack_auth_url

    async def handle_slack_callback(
        self, code: str, state: str
    ) -> SlackAuthorizationCode:
        """
        Handle the callback from Slack after user authorization.

        This is called when Slack redirects back with an authorization code.
        """
        # Verify state parameter
        if state not in self.authorization_codes:
            raise AuthorizeError("invalid_request", "Invalid state parameter")

        auth_code_data = self.authorization_codes[state]

        # Update with the actual code from Slack
        auth_code_data.code = code

        # Generate our own authorization code for the MCP client
        mcp_code = secrets.token_urlsafe(32)
        self.authorization_codes[mcp_code] = auth_code_data

        # Clean up the state-based entry
        del self.authorization_codes[state]

        return auth_code_data

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> SlackAuthorizationCode | None:
        """Load an authorization code by its code value."""
        auth_code = self.authorization_codes.get(authorization_code)

        if auth_code and auth_code.client_id == client.client_id:
            # Check expiration
            if time.time() > auth_code.expires_at:
                del self.authorization_codes[authorization_code]
                return None
            return auth_code

        return None

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: SlackAuthorizationCode,
    ) -> OAuthToken:
        """
        Exchange an authorization code for access and refresh tokens.

        This exchanges the Slack authorization code for Slack tokens,
        then creates MCP tokens for the client.
        """
        # Exchange Slack authorization code for Slack tokens
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": authorization_code.code,
                    "redirect_uri": self._get_slack_redirect_uri(),
                },
            )

            slack_data = response.json()

            if not slack_data.get("ok"):
                raise TokenError(
                    "invalid_grant", slack_data.get("error", "Unknown error")
                )

        # Get Slack access token
        slack_access_token = slack_data.get("access_token")
        if not slack_access_token:
            raise TokenError("invalid_grant", "No access token received from Slack")

        # Generate MCP tokens
        mcp_access_token = secrets.token_urlsafe(32)
        mcp_refresh_token = secrets.token_urlsafe(32)

        # Store the mapping between MCP tokens and Slack tokens
        token_data = {
            "slack_token": slack_access_token,
            "client_id": client.client_id,
            "scopes": authorization_code.scopes,
            "created_at": time.time(),
        }

        # Save tokens in storage
        await self.storage.save_item(
            f"mcp_token:{mcp_access_token}", token_data, ttl=3600
        )  # 1 hour
        await self.storage.save_item(
            f"mcp_refresh:{mcp_refresh_token}", token_data, ttl=86400 * 30
        )  # 30 days

        # Clean up authorization code
        if authorization_code.code in self.authorization_codes:
            del self.authorization_codes[authorization_code.code]

        return OAuthToken(
            access_token=mcp_access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=mcp_refresh_token,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> SlackRefreshToken | None:
        """Load a refresh token."""
        token_data = await self.storage.get_item(f"mcp_refresh:{refresh_token}")

        if token_data and token_data.get("client_id") == client.client_id:
            return SlackRefreshToken(
                token=refresh_token,
                client_id=client.client_id,
                scopes=token_data.get("scopes", []),
            )

        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: SlackRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """
        Exchange a refresh token for new tokens.

        Note: Slack doesn't support refresh tokens in the traditional OAuth sense,
        so we just issue new MCP tokens that still point to the same Slack token.
        """
        # Load the associated token data
        token_data = await self.storage.get_item(f"mcp_refresh:{refresh_token.token}")

        if not token_data:
            raise TokenError("invalid_grant", "Refresh token not found")

        # Generate new MCP tokens
        new_access_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)

        # Update token data with requested scopes
        if scopes:
            # Ensure requested scopes are subset of original scopes
            original_scopes = set(token_data.get("scopes", []))
            requested_scopes = set(scopes)
            if not requested_scopes.issubset(original_scopes):
                raise TokenError(
                    "invalid_scope", "Requested scopes exceed original grant"
                )
            token_data["scopes"] = list(requested_scopes)

        # Save new tokens
        await self.storage.save_item(
            f"mcp_token:{new_access_token}", token_data, ttl=3600
        )
        await self.storage.save_item(
            f"mcp_refresh:{new_refresh_token}", token_data, ttl=86400 * 30
        )

        # Delete old refresh token
        await self.storage.delete_item(f"mcp_refresh:{refresh_token.token}")

        return OAuthToken(
            access_token=new_access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=new_refresh_token,
            scope=" ".join(token_data.get("scopes", [])),
        )

    async def load_access_token(self, token: str) -> SlackAccessToken | None:
        """Load an access token."""
        token_data = await self.storage.get_item(f"mcp_token:{token}")

        if token_data:
            return SlackAccessToken(
                token=token,
                client_id=token_data.get("client_id"),
                scopes=token_data.get("scopes", []),
                expires_at=int(token_data.get("created_at", 0)) + 3600,
            )

        return None

    async def revoke_token(
        self, token: str, token_type_hint: str | None = None
    ) -> None:
        """Revoke a token."""
        # Try to revoke as access token first
        if token_type_hint != "refresh_token":
            await self.storage.delete_item(f"mcp_token:{token}")

        # Try to revoke as refresh token
        if token_type_hint != "access_token":
            await self.storage.delete_item(f"mcp_refresh:{token}")

    async def get_slack_token_for_mcp_token(self, mcp_token: str) -> Optional[str]:
        """Get the Slack token associated with an MCP token."""
        token_data = await self.storage.get_item(f"mcp_token:{mcp_token}")
        if token_data:
            return token_data.get("slack_token")
        return None
