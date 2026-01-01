"""
Shared application state and client factories.
"""

import os
from mcp.server.fastmcp import FastMCP

from .utils.obs_client import OBSClient
from .utils.twitch_client import TwitchClient

# Initialize FastMCP server
mcp = FastMCP(
    name="obs-twitch-mcp",
    version="0.1.0",
)

# Global clients (initialized on first use)
_obs_client: OBSClient | None = None
_twitch_client: TwitchClient | None = None


def get_obs_client() -> OBSClient:
    """Get or create OBS client singleton."""
    global _obs_client
    if _obs_client is None:
        _obs_client = OBSClient(
            host=os.getenv("OBS_WEBSOCKET_HOST", "localhost"),
            port=int(os.getenv("OBS_WEBSOCKET_PORT", "4455")),
            password=os.getenv("OBS_WEBSOCKET_PASSWORD", ""),
        )
    return _obs_client


def get_twitch_client() -> TwitchClient:
    """Get or create Twitch client singleton."""
    global _twitch_client
    if _twitch_client is None:
        _twitch_client = TwitchClient(
            client_id=os.getenv("TWITCH_CLIENT_ID", ""),
            client_secret=os.getenv("TWITCH_CLIENT_SECRET", ""),
            oauth_token=os.getenv("TWITCH_OAUTH_TOKEN", ""),
            channel=os.getenv("TWITCH_CHANNEL", ""),
        )
    return _twitch_client
