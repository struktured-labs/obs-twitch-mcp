"""
Twitch chat moderation tools.
"""

from ..app import mcp, get_twitch_client


@mcp.tool()
def twitch_ban_user(username: str, reason: str = "") -> str:
    """
    Permanently ban a user from chat.

    Args:
        username: The username to ban
        reason: Optional reason for the ban
    """
    client = get_twitch_client()
    client.ban_user(username, reason)
    return f"Banned user: {username}" + (f" (reason: {reason})" if reason else "")


@mcp.tool()
def twitch_timeout_user(
    username: str,
    duration_seconds: int = 600,
    reason: str = "",
) -> str:
    """
    Timeout a user from chat for a specified duration.

    Args:
        username: The username to timeout
        duration_seconds: Duration in seconds (default: 600 = 10 minutes)
        reason: Optional reason for the timeout
    """
    client = get_twitch_client()
    client.timeout_user(username, duration_seconds, reason)
    minutes = duration_seconds // 60
    return f"Timed out {username} for {minutes} minutes" + (f" (reason: {reason})" if reason else "")


@mcp.tool()
def twitch_unban_user(username: str) -> str:
    """Unban a user from chat."""
    client = get_twitch_client()
    client.unban_user(username)
    return f"Unbanned user: {username}"


@mcp.tool()
def twitch_slow_mode(seconds: int = 30) -> str:
    """
    Enable slow mode in chat.

    Args:
        seconds: Seconds between messages (0 to disable)
    """
    client = get_twitch_client()
    if seconds > 0:
        client.send_chat_message(f"/slow {seconds}")
        return f"Enabled slow mode: {seconds} seconds between messages"
    else:
        client.send_chat_message("/slowoff")
        return "Disabled slow mode"


@mcp.tool()
def twitch_emote_only(enabled: bool = True) -> str:
    """Toggle emote-only mode in chat."""
    client = get_twitch_client()
    if enabled:
        client.send_chat_message("/emoteonly")
        return "Enabled emote-only mode"
    else:
        client.send_chat_message("/emoteonlyoff")
        return "Disabled emote-only mode"


@mcp.tool()
def twitch_subscriber_only(enabled: bool = True) -> str:
    """Toggle subscriber-only mode in chat."""
    client = get_twitch_client()
    if enabled:
        client.send_chat_message("/subscribers")
        return "Enabled subscriber-only mode"
    else:
        client.send_chat_message("/subscribersoff")
        return "Disabled subscriber-only mode"


@mcp.tool()
def twitch_clear_chat() -> str:
    """Clear all messages in chat."""
    client = get_twitch_client()
    client.send_chat_message("/clear")
    return "Chat cleared"
