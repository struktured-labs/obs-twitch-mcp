"""
Shared application state and client factories.
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .utils.obs_client import OBSClient
from .utils.twitch_client import TwitchClient
from .utils.chat_listener import ChatListener
from .utils.twitch_auth import get_valid_token

# Initialize FastMCP server
mcp = FastMCP(name="obs-twitch-mcp")

# Global clients (initialized on first use)
_obs_client: OBSClient | None = None
_twitch_client: TwitchClient | None = None
_chat_listener: ChatListener | None = None

# Token file path
TOKEN_FILE = Path(__file__).parent.parent / ".twitch_token.json"


def _get_oauth_token() -> str:
    """Get OAuth token, auto-refreshing if expired."""
    client_id = os.getenv("TWITCH_CLIENT_ID", "")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")

    if client_id and client_secret:
        try:
            # Use auto-refresh logic
            return get_valid_token(client_id, client_secret)
        except Exception as e:
            print(f"Token auto-refresh failed: {e}")

    # Fallback: read from file without refresh
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
                token = data.get("access_token", "")
                if token:
                    return token
        except Exception:
            pass
    # Fall back to environment variable
    return os.getenv("TWITCH_OAUTH_TOKEN", "")


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
            oauth_token=_get_oauth_token(),
            channel=os.getenv("TWITCH_CHANNEL", ""),
        )
    return _twitch_client


def refresh_twitch_client() -> TwitchClient:
    """Force refresh of Twitch client (e.g., after token update)."""
    global _twitch_client, _chat_listener

    # Stop existing listener
    if _chat_listener and _chat_listener.is_running:
        _chat_listener.stop()
        _chat_listener = None

    _twitch_client = None
    client = get_twitch_client()

    # Restart listener with new token
    start_chat_listener()

    return client


def get_chat_listener() -> ChatListener | None:
    """Get the chat listener instance."""
    return _chat_listener


def start_chat_listener() -> ChatListener:
    """Start the background chat listener."""
    global _chat_listener

    if _chat_listener and _chat_listener.is_running:
        return _chat_listener

    channel = os.getenv("TWITCH_CHANNEL", "")
    token = _get_oauth_token()

    if not channel or not token:
        raise ValueError("TWITCH_CHANNEL and OAuth token required for chat listener")

    _chat_listener = ChatListener(
        channel=channel,
        oauth_token=token,
    )
    _chat_listener.start()
    return _chat_listener


def stop_chat_listener() -> None:
    """Stop the background chat listener."""
    global _chat_listener
    if _chat_listener:
        _chat_listener.stop()
        _chat_listener = None


# Auto-start chat listener when module loads
def _auto_start_listener():
    """Try to auto-start the chat listener."""
    try:
        start_chat_listener()
    except Exception as e:
        print(f"Could not auto-start chat listener: {e}")


# Delay auto-start slightly to let env vars load
import threading
threading.Timer(2.0, _auto_start_listener).start()
