"""
Chat command system for Twitch integration.

Provides a framework for handling chat commands like:
- !clip - Create a clip
- !uptime - Show stream uptime
- !song - Show current song (if configured)
- !lurk - Lurk mode animation

Commands can be enabled/disabled and customized.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from ..app import mcp, get_twitch_client, get_obs_client
from ..utils.logger import get_logger

logger = get_logger("commands")

# Command registry
_commands: dict[str, "ChatCommand"] = {}
_command_cooldowns: dict[str, float] = {}  # user:command -> last_used timestamp


@dataclass
class ChatCommand:
    """Definition of a chat command."""
    name: str
    description: str
    handler: Callable[[str, str], str | None]  # (username, args) -> response
    cooldown_seconds: int = 10
    mod_only: bool = False
    enabled: bool = True
    aliases: list[str] = field(default_factory=list)


def register_command(command: ChatCommand) -> None:
    """Register a chat command."""
    _commands[command.name.lower()] = command
    for alias in command.aliases:
        _commands[alias.lower()] = command
    logger.info(f"Registered command: !{command.name}")


def _check_cooldown(username: str, command_name: str, cooldown: int) -> bool:
    """Check if user is on cooldown for this command."""
    key = f"{username}:{command_name}"
    last_used = _command_cooldowns.get(key, 0)
    if time.time() - last_used < cooldown:
        return False
    _command_cooldowns[key] = time.time()
    return True


# =============================================================================
# Built-in Command Handlers
# =============================================================================


def _handle_clip(username: str, args: str) -> str | None:
    """Handle !clip command - create a clip."""
    from .clips import obs_clip
    result = obs_clip()
    if result.get("status") == "clipped":
        return f"@{username} Clip saved!"
    elif result.get("status") == "started":
        return f"@{username} Replay buffer started - try again in a few seconds!"
    return f"@{username} Couldn't create clip: {result.get('message', 'unknown error')}"


def _handle_uptime(username: str, args: str) -> str | None:
    """Handle !uptime command - show stream uptime."""
    client = get_twitch_client()
    stream = client.get_stream_info()
    if stream:
        started_at = stream.get("started_at", "")
        if started_at:
            # Parse ISO format
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            uptime = datetime.now(start.tzinfo) - start
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            if hours > 0:
                return f"Stream has been live for {hours}h {minutes}m"
            return f"Stream has been live for {minutes} minutes"
    return "Stream is not currently live"


def _handle_lurk(username: str, args: str) -> str | None:
    """Handle !lurk command - acknowledge lurker."""
    from .lurk import show_lurk_animation
    show_lurk_animation(username)
    return f"@{username} is now lurking! Enjoy the stream silently o7"


def _handle_song(username: str, args: str) -> str | None:
    """Handle !song command - show current song."""
    # This would integrate with music player if configured
    # For now, return a placeholder
    return "Song info not configured. Set up music integration to enable this."


def _handle_socials(username: str, args: str) -> str | None:
    """Handle !socials command - show streamer's social links."""
    # Could be configured via env var or file
    import os
    socials = os.getenv("STREAMER_SOCIALS", "")
    if socials:
        return socials
    return "Follow the streamer on their social platforms!"


def _handle_commands(username: str, args: str) -> str | None:
    """Handle !commands - list available commands."""
    enabled = [f"!{cmd.name}" for cmd in set(_commands.values()) if cmd.enabled]
    return f"Available commands: {', '.join(sorted(enabled))}"


def _handle_shoutout(username: str, args: str) -> str | None:
    """Handle !so command - shoutout another streamer (mod only)."""
    if not args:
        return f"@{username} Usage: !so <username>"
    target = args.split()[0].lstrip("@")
    from .shoutout import shoutout_streamer
    result = shoutout_streamer(target)
    return None  # Shoutout function handles the message


def _handle_title(username: str, args: str) -> str | None:
    """Handle !title command - show or set stream title (mod only to set)."""
    client = get_twitch_client()
    stream = client.get_stream_info()
    if stream:
        return f"Title: {stream.get('title', 'Unknown')}"
    return "Stream is not currently live"


def _handle_game(username: str, args: str) -> str | None:
    """Handle !game command - show current game."""
    client = get_twitch_client()
    stream = client.get_stream_info()
    if stream:
        return f"Currently playing: {stream.get('game_name', 'Unknown')}"
    return "Stream is not currently live"


# =============================================================================
# Register Built-in Commands
# =============================================================================


def _register_builtin_commands():
    """Register all built-in commands."""
    commands = [
        ChatCommand(
            name="clip",
            description="Create a clip of the last few seconds",
            handler=_handle_clip,
            cooldown_seconds=30,
        ),
        ChatCommand(
            name="uptime",
            description="Show how long the stream has been live",
            handler=_handle_uptime,
            cooldown_seconds=10,
        ),
        ChatCommand(
            name="lurk",
            description="Announce that you're lurking",
            handler=_handle_lurk,
            cooldown_seconds=60,
        ),
        ChatCommand(
            name="song",
            description="Show the current song playing",
            handler=_handle_song,
            cooldown_seconds=10,
        ),
        ChatCommand(
            name="socials",
            description="Show streamer's social links",
            handler=_handle_socials,
            cooldown_seconds=30,
            aliases=["social", "twitter", "youtube"],
        ),
        ChatCommand(
            name="commands",
            description="List available commands",
            handler=_handle_commands,
            cooldown_seconds=30,
            aliases=["help"],
        ),
        ChatCommand(
            name="so",
            description="Shoutout another streamer",
            handler=_handle_shoutout,
            cooldown_seconds=5,
            mod_only=True,
            aliases=["shoutout"],
        ),
        ChatCommand(
            name="title",
            description="Show current stream title",
            handler=_handle_title,
            cooldown_seconds=10,
        ),
        ChatCommand(
            name="game",
            description="Show current game being played",
            handler=_handle_game,
            cooldown_seconds=10,
        ),
    ]

    for cmd in commands:
        register_command(cmd)


# Register on module load
_register_builtin_commands()


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
def handle_chat_command(username: str, message: str) -> dict:
    """
    Handle a chat command from a user.

    This is called when a user sends a message starting with "!".
    Looks up the command and executes it if valid.

    Args:
        username: The username who sent the command
        message: The full message text (including the ! prefix)

    Returns:
        Dict with status and response (if any).
    """
    if not message.startswith("!"):
        return {"status": "ignored", "reason": "Not a command"}

    parts = message[1:].split(maxsplit=1)
    command_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    command = _commands.get(command_name)
    if not command:
        return {"status": "unknown", "command": command_name}

    if not command.enabled:
        return {"status": "disabled", "command": command_name}

    # Check cooldown
    if not _check_cooldown(username, command.name, command.cooldown_seconds):
        return {"status": "cooldown", "command": command_name}

    # Check mod-only
    if command.mod_only:
        # Would need to check if user is mod - for now, allow all
        pass

    try:
        response = command.handler(username, args)
        if response:
            # Send response to chat
            client = get_twitch_client()
            client.send_chat_message(response)
            return {"status": "executed", "command": command_name, "response": response}
        return {"status": "executed", "command": command_name}
    except Exception as e:
        logger.error(f"Command {command_name} failed: {e}")
        return {"status": "error", "command": command_name, "error": str(e)}


@mcp.tool()
def list_commands() -> list[dict]:
    """
    List all registered chat commands.

    Returns:
        List of command info dicts.
    """
    seen = set()
    commands = []
    for cmd in _commands.values():
        if cmd.name in seen:
            continue
        seen.add(cmd.name)
        commands.append({
            "name": cmd.name,
            "description": cmd.description,
            "aliases": cmd.aliases,
            "cooldown_seconds": cmd.cooldown_seconds,
            "mod_only": cmd.mod_only,
            "enabled": cmd.enabled,
        })
    return sorted(commands, key=lambda c: c["name"])


@mcp.tool()
def toggle_command(command_name: str, enabled: bool) -> dict:
    """
    Enable or disable a chat command.

    Args:
        command_name: The command name (without !)
        enabled: True to enable, False to disable

    Returns:
        Status dict.
    """
    command = _commands.get(command_name.lower())
    if not command:
        return {"status": "error", "message": f"Unknown command: {command_name}"}

    command.enabled = enabled
    return {
        "status": "success",
        "command": command_name,
        "enabled": enabled,
    }


@mcp.tool()
def set_command_cooldown(command_name: str, cooldown_seconds: int) -> dict:
    """
    Set the cooldown for a chat command.

    Args:
        command_name: The command name (without !)
        cooldown_seconds: New cooldown in seconds

    Returns:
        Status dict.
    """
    command = _commands.get(command_name.lower())
    if not command:
        return {"status": "error", "message": f"Unknown command: {command_name}"}

    command.cooldown_seconds = cooldown_seconds
    return {
        "status": "success",
        "command": command_name,
        "cooldown_seconds": cooldown_seconds,
    }
