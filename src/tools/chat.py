"""
Twitch chat interaction tools.
"""

from ..app import mcp, get_twitch_client


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
