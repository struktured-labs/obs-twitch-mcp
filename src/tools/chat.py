"""
Twitch chat interaction tools.
"""

from datetime import datetime

from ..app import mcp, get_twitch_client, refresh_twitch_client
from ..utils import chat_logger


@mcp.tool()
def twitch_send_message(message: str) -> str:
    """Send a message to Twitch chat."""
    client = get_twitch_client()
    client.send_chat_message(message)
    return f"Sent to chat: {message}"


@mcp.tool()
def twitch_reply_to_user(username: str, message: str) -> str:
    """Reply to a specific user in chat (mentions them)."""
    client = get_twitch_client()
    full_message = f"@{username} {message}"
    client.send_chat_message(full_message)
    return f"Replied to @{username}: {message}"


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
def twitch_refresh_token() -> str:
    """
    Refresh the Twitch client to pick up a new token.

    Call this after running auth.py to update the token without restarting.
    """
    client = refresh_twitch_client()
    return f"Twitch client refreshed. Channel: {client.channel}"
