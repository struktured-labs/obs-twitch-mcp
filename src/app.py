"""
Shared application state and client factories.
"""

import asyncio
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .utils.logger import get_logger
from .utils.obs_client import OBSClient
from .utils.twitch_client import TwitchClient
from .utils.chat_listener import ChatListener
from .utils.twitch_auth import get_valid_token
from .utils.chat_filter import get_chat_filter
from .utils.sse_server import start_sse_server, broadcast_message_sync, get_sse_server

logger = get_logger("app")

# Initialize FastMCP server
mcp = FastMCP(name="obs-twitch-mcp")


def _validate_env() -> list[str]:
    """Validate required environment variables. Returns list of missing vars."""
    missing = []
    if not os.getenv("TWITCH_CLIENT_ID"):
        missing.append("TWITCH_CLIENT_ID")
    if not os.getenv("TWITCH_CLIENT_SECRET"):
        missing.append("TWITCH_CLIENT_SECRET")
    if not os.getenv("TWITCH_CHANNEL"):
        missing.append("TWITCH_CHANNEL")
    return missing

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
            token = get_valid_token(client_id, client_secret)
            logger.debug("Got token via auto-refresh")
            return token
        except Exception as e:
            logger.error(f"Token auto-refresh failed: {e}")
    elif client_id and not client_secret:
        logger.warning("TWITCH_CLIENT_SECRET not set - token auto-refresh disabled")

    # Fallback: read from file without refresh
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
                token = data.get("access_token", "")
                if token:
                    logger.info("Using token from file (may be expired)")
                    return token
        except Exception as e:
            logger.warning(f"Failed to read token file: {e}")

    # Fall back to environment variable
    env_token = os.getenv("TWITCH_OAUTH_TOKEN", "")
    if env_token:
        logger.info("Using token from TWITCH_OAUTH_TOKEN env var")
    else:
        logger.error("No OAuth token available from any source")
    return env_token


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


def _create_sse_handler():
    """Create a handler that forwards filtered messages to SSE clients."""
    chat_filter = get_chat_filter()

    def handler(msg):
        """Forward chat message to SSE server if it passes filters."""
        # Convert ChatMessage to dict
        msg_dict = {
            "username": msg.username,
            "message": msg.message,
            "is_mod": msg.is_mod,
            "is_subscriber": msg.is_subscriber,
            "is_broadcaster": msg.username.lower() == os.getenv("TWITCH_CHANNEL", "").lower(),
        }

        # Apply filters
        filtered = chat_filter.process(msg_dict)
        if filtered:
            broadcast_message_sync(filtered)

    return handler


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

    # Add SSE broadcast handler
    _chat_listener.add_handler(_create_sse_handler())

    _chat_listener.start()
    return _chat_listener


def stop_chat_listener() -> None:
    """Stop the background chat listener."""
    global _chat_listener
    if _chat_listener:
        _chat_listener.stop()
        _chat_listener = None


# Auto-start chat listener and SSE server when module loads
def _auto_start_services():
    """Try to auto-start the chat listener and SSE server in background thread."""
    def _startup_worker():
        """Worker thread that handles potentially slow startup operations."""
        # Validate env vars first
        missing = _validate_env()
        if missing:
            logger.warning(f"Missing env vars (run 'source setenv.sh'): {', '.join(missing)}")
            logger.warning("Services not started due to missing configuration")
            return

        # Start SSE server for chat overlay
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_sse_server())
            # Keep the loop running in a thread for SSE
            def run_loop():
                loop.run_forever()
            sse_thread = threading.Thread(target=run_loop, daemon=True)
            sse_thread.start()
            logger.info("SSE server auto-started successfully")
        except Exception as e:
            logger.warning(f"Could not auto-start SSE server: {e}")

        # Start chat listener (may block on IRC connection with 8s timeout)
        try:
            start_chat_listener()
            logger.info("Chat listener auto-started successfully")
        except Exception as e:
            logger.error(f"Could not auto-start chat listener: {e}")

    # Run all startup in a background daemon thread
    # This ensures MCP tools are never blocked by startup
    import threading
    startup_thread = threading.Thread(target=_startup_worker, daemon=True, name="mcp-auto-start")
    startup_thread.start()
    logger.debug("Auto-start services initiated in background thread")


# Start auto-start immediately (no delay needed since it's non-blocking now)
_auto_start_services()
