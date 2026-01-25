"""
Twitch chat interaction tools.
"""

from datetime import datetime

from ..app import mcp, get_twitch_client, refresh_twitch_client, get_chat_listener
from ..utils import chat_logger


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
    Refresh the Twitch client to pick up a new token.

    Call this after running auth.py to update the token without restarting.
    """
    client = refresh_twitch_client()
    return {
        "status": "refreshed",
        "channel": client.channel,
        "message": "Twitch client and chat listener restarted with fresh token",
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
