import os

from fastmcp import FastMCP
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from pydantic import BaseModel


class OIDCConfigError(Exception):
    """Exception raised when OIDC configuration is invalid or incomplete."""

    pass


class OIDCConfig(BaseModel):
    """Configuration for OpenID Connect (OIDC) authentication.

    This class handles the configuration required to set up OIDC authentication
    for the MCP server, including the discovery URL, client credentials, and
    base URL for the application.

    Attributes:
        config_url: The OIDC discovery/configuration URL (e.g., Keycloak's .well-known endpoint)
        client_id: The OAuth2 client identifier
        client_secret: The OAuth2 client secret
        base_url: Public base URL of this MCP server (scheme + host + port). Must match the
            streamable-http URL your client uses (same host: `localhost` vs `127.0.0.1` are
            distinct for OAuth protected resource checks).
    """

    config_url: str
    client_id: str
    client_secret: str
    base_url: str

    @classmethod
    def from_env(cls) -> "OIDCConfig":
        """Create an OIDCConfig instance from environment variables.

        Reads OIDC configuration from the following environment variables:
        - OIDC_CONFIG_URL: The OIDC discovery/configuration URL
        - OIDC_CLIENT_ID: The OAuth2 client identifier
        - OIDC_CLIENT_SECRET: The OAuth2 client secret
        - OIDC_BASE_URL: The base URL of the MCP server

        Returns:
            OIDCConfig: A configured instance with values from environment variables

        Raises:
            OIDCConfigError: If any required environment variables are missing
        """
        config_url = os.getenv("OIDC_CONFIG_URL")
        client_id = os.getenv("OIDC_CLIENT_ID")
        client_secret = os.getenv("OIDC_CLIENT_SECRET")
        base_url = os.getenv("OIDC_BASE_URL")

        check = {
            "OIDC_CONFIG_URL": config_url,
            "OIDC_CLIENT_ID": client_id,
            "OIDC_CLIENT_SECRET": client_secret,
            "OIDC_BASE_URL": base_url,
        }

        if any(v is None for v in check.values()):
            raise OIDCConfigError(
                f"All environment variables must be set. Missing: {', '.join([str(k) for k, v in check.items() if v is None])}"
            )

        # Calm the linter down by asserting the types
        assert config_url is not None and isinstance(config_url, str), (
            "OIDC_CONFIG_URL must be a string"
        )
        assert client_id is not None and isinstance(client_id, str), (
            "OIDC_CLIENT_ID must be a string"
        )
        assert client_secret is not None and isinstance(client_secret, str), (
            "OIDC_CLIENT_SECRET must be a string"
        )
        assert base_url is not None and isinstance(base_url, str), (
            "OIDC_BASE_URL must be a string"
        )

        return cls(
            config_url=config_url,
            client_id=client_id,
            client_secret=client_secret,
            base_url=base_url,
        )

    def add_to_mcp_app(self, app: FastMCP):
        """Add OIDC authentication to a FastMCP application.

        Creates an OIDCProxy instance with the configured parameters and
        attaches it to the FastMCP application as the authentication handler.

        Args:
            app: The FastMCP application instance to configure with OIDC auth
        """
        proxy = OIDCProxy(
            config_url=self.config_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            base_url=self.base_url,
        )
        app.auth = proxy
