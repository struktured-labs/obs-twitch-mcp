"""
Twitch chat interaction tools.
"""

import os
from datetime import datetime

from ..app import mcp, get_twitch_client, refresh_twitch_client, get_chat_listener
from ..utils import chat_logger
from ..utils.twitch_auth import save_token, get_valid_token, TokenExpiredError



@mcp.tool()
def twitch_send_message(message: str) -> str:
    """Send a message to Twitch chat."""
    # Use the persistent chat listener connection (non-blocking)
    listener = get_chat_listener()
    if listener and listener.is_running:
        listener.send_message(message)
        return f"Sent to chat: {message}"
    else:
        # Fallback to client method (blocks for 8s, but only if listener not running)
        client = get_twitch_client()
        client.send_chat_message(message)
        return f"Sent to chat (fallback): {message}"


@mcp.tool()
def twitch_reply_to_user(username: str, message: str) -> str:
    """Reply to a specific user in chat (mentions them)."""
    full_message = f"@{username} {message}"
    # Use the persistent chat listener connection (non-blocking)
    listener = get_chat_listener()
    if listener and listener.is_running:
        listener.send_message(full_message)
        return f"Replied to @{username}: {message}"
    else:
        # Fallback to client method (blocks for 8s, but only if listener not running)
        client = get_twitch_client()
        client.send_chat_message(full_message)
        return f"Replied to @{username}: {message} (fallback)"


@mcp.tool()
def twitch_get_recent_messages(count: int = 10) -> list[dict]:
    """
    Get recent chat messages from the cache.

    Note: Messages are only cached while the server is running.
    """
    client = get_twitch_client()
    messages = client.get_recent_messages(count)
    return [
        {
            "username": m.username,
            "message": m.message,
            "is_mod": m.is_mod,
            "is_subscriber": m.is_subscriber,
        }
        for m in messages
    ]


@mcp.tool()
def twitch_get_chat_history(date: str = "", limit: int = 100) -> list[dict]:
    """
    Get chat history from saved logs.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        limit: Maximum number of messages to return.

    Returns:
        List of chat messages with timestamp, username, message, etc.
    """
    if date:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return [{"error": "Invalid date format. Use YYYY-MM-DD"}]
    else:
        dt = None

    return chat_logger.read_logs(dt, limit)


@mcp.tool()
def twitch_list_chat_log_dates() -> list[str]:
    """
    List all available chat log dates.

    Returns:
        List of dates (YYYY-MM-DD) that have chat logs, newest first.
    """
    return chat_logger.get_available_dates()


@mcp.tool()
def twitch_refresh_token() -> dict:
    """
    Refresh the Twitch OAuth token and reconnect.

    This actually calls Twitch's OAuth endpoint to refresh the access token
    using the refresh_token, then restarts the client with the new token.

    Use this when API calls fail with 401 Unauthorized.
    """
    client_id = os.getenv("TWITCH_CLIENT_ID", "")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return {
            "status": "error",
            "message": "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET required for token refresh",
        }

    try:
        # Actually refresh the token via Twitch OAuth API
        new_token = get_valid_token(client_id, client_secret)

        # Now reload the client with the fresh token
        client = refresh_twitch_client()

        return {
            "status": "refreshed",
            "channel": client.channel,
            "message": "Token refreshed via Twitch OAuth and client restarted",
        }
    except TokenExpiredError as e:
        return {
            "status": "error",
            "message": f"Token refresh failed - run 'uv run python auth.py' manually: {e}",
        }


@mcp.tool()
def twitch_reconnect() -> dict:
    """
    Reconnect to Twitch with fresh credentials.

    This refreshes the OAuth token, recreates the Twitch client,
    and restarts the chat listener - all without restarting the MCP server.

    Use this when:
    - Chat messages aren't sending
    - Token has expired
    - IRC connection dropped
    """
    from ..utils.twitch_auth import validate_token, load_token

    # Refresh the client (stops listener, gets new token, restarts listener)
    client = refresh_twitch_client()

    # Validate the new token and get expiry info
    token_data = load_token()
    token = token_data.get("access_token", "") if token_data else ""
    validation = validate_token(token) if token else None

    if validation:
        expires_hours = validation.get("expires_in", 0) // 3600
        return {
            "status": "connected",
            "channel": client.channel,
            "user": validation.get("login"),
            "token_expires_in": f"{expires_hours} hours",
            "scopes": validation.get("scopes", []),
        }
    else:
        return {
            "status": "warning",
            "channel": client.channel,
            "message": "Reconnected but could not validate token - may need to re-auth",
        }


@mcp.tool()
def twitch_create_poll(
    title: str,
    choices: list[str],
    duration: int = 60,
) -> dict:
    """
    Create a poll on Twitch.

    Args:
        title: Poll question (max 60 chars)
        choices: List of 2-5 choices (max 25 chars each)
        duration: Duration in seconds (15-1800, default 60)

    Returns:
        Poll details including ID for ending early
    """
    client = get_twitch_client()
    return client.create_poll(title, choices, duration)


@mcp.tool()
def twitch_end_poll(poll_id: str, show_results: bool = True) -> dict:
    """
    End a poll early.

    Args:
        poll_id: The poll ID from create_poll
        show_results: If True, show final results. If False, cancel silently.

    Returns:
        Final poll results with vote counts
    """
    client = get_twitch_client()
    return client.end_poll(poll_id, archive=show_results)


@mcp.tool()
def twitch_get_polls() -> list[dict]:
    """
    Get active and recent polls.

    Returns:
        List of polls with their status and vote counts
    """
    client = get_twitch_client()
    return client.get_polls()


@mcp.tool()
def twitch_reauth() -> dict:
    """
    Refresh Twitch token and reconnect automatically.

    Uses the saved refresh_token to get a new access token without any
    manual intervention. This is the preferred way to fix auth issues.

    Use this when:
    - Chat messages aren't sending
    - API calls fail with 401
    - Token has expired

    Returns:
        Dict with status, channel, user info, and token expiry
    """
    from ..utils.twitch_auth import refresh_token, load_token, validate_token

    client_id = os.getenv("TWITCH_CLIENT_ID", "")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return {
            "status": "error",
            "message": "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET required",
        }

    token_data = load_token()
    if not token_data or not token_data.get("refresh_token"):
        return {
            "status": "error",
            "message": "No refresh_token found. Run 'uv run python auth.py' for initial setup.",
        }

    try:
        # Refresh token via Twitch OAuth API
        new_token = refresh_token(client_id, client_secret, token_data["refresh_token"])
        save_token(new_token)

        # Reconnect client with new token
        client = refresh_twitch_client()

        # Validate and get info
        validation = validate_token(new_token["access_token"])
        if validation:
            expires_hours = validation.get("expires_in", 0) // 3600
            return {
                "status": "success",
                "channel": client.channel,
                "user": validation.get("login"),
                "token_expires_in": f"{expires_hours} hours",
                "scopes": validation.get("scopes", []),
            }
        else:
            return {
                "status": "refreshed",
                "channel": client.channel,
                "message": "Token refreshed but validation failed - may still work",
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Refresh failed: {e}. Run 'uv run python auth.py' if refresh_token is invalid.",
        }


@mcp.tool()
def twitch_reauth_status() -> dict:
    """
    Check current token status.

    Returns:
        Dict with token validity, user, and expiry info
    """
    from ..utils.twitch_auth import load_token, validate_token
    import time

    token_data = load_token()
    if not token_data:
        return {"status": "no_token", "message": "No token file found. Run twitch_reauth() or 'uv run python auth.py'."}

    token = token_data.get("access_token", "")
    validation = validate_token(token) if token else None

    if validation:
        expires_in = validation.get("expires_in", 0)
        return {
            "status": "valid",
            "user": validation.get("login"),
            "expires_in_hours": expires_in // 3600,
            "expires_in_minutes": (expires_in % 3600) // 60,
            "scopes": validation.get("scopes", []),
        }
    else:
        # Check if we have expires_at to give more info
        expires_at = token_data.get("expires_at", 0)
        if expires_at and time.time() > expires_at:
            return {"status": "expired", "message": "Token expired. Run twitch_reauth() to refresh."}
        return {"status": "invalid", "message": "Token invalid. Run twitch_reauth() to refresh."}
