"""Environment-based configuration for the I14Y API client."""

import os

__all__ = ["get_base_url", "get_server_host", "get_server_port"]

I14Y_ENVIRONMENTS: dict[str, str] = {
    "prod": "https://api.i14y.admin.ch/api/public/v1",
    "test": "https://api-a.i14y.admin.ch/api/public/v1",
}


def get_base_url() -> str:
    """Return the I14Y API base URL for the configured environment."""
    env = os.getenv("I14Y_API_ENV", "prod").lower()
    if env not in I14Y_ENVIRONMENTS:
        raise ValueError(
            f"Unknown I14Y_API_ENV '{env}'. Valid values: {list(I14Y_ENVIRONMENTS.keys())}"
        )
    return I14Y_ENVIRONMENTS[env]


def get_server_host() -> str:
    # Bind on all interfaces: required for Azure Container Apps ingress routing.
    # Override via MCP_HOST env var for local dev if needed.
    return os.getenv("MCP_HOST", "0.0.0.0")  # nosec B104


def get_server_port() -> int:
    return int(os.getenv("MCP_PORT", "8400"))
