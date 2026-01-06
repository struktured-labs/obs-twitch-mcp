"""
Viewer engagement tracking system.

Tracks viewer activity to:
- Distinguish lurkers from active chatters
- Welcome back returning viewers
- Track viewer loyalty/participation
- Identify most active community members
"""

import os
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from ..app import mcp, get_twitch_client
from ..utils.logger import get_logger
from ..utils.twitch_client import ChatMessage

logger = get_logger("engagement")

# Data file for persistence
DATA_DIR = Path(__file__).parent.parent.parent / "data"
ENGAGEMENT_FILE = DATA_DIR / "viewer_engagement.json"


@dataclass
class ViewerStats:
    """Stats for a single viewer."""
    username: str
    message_count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    sessions: int = 0  # How many separate stream sessions they've been in
    lurk_count: int = 0  # How many times they've lurked


@dataclass
class EngagementTracker:
    """Tracks viewer engagement across streams."""

    viewers: dict[str, ViewerStats] = field(default_factory=dict)
    session_viewers: set = field(default_factory=set)  # Viewers seen this session
    last_message_time: dict[str, float] = field(default_factory=dict)
    welcome_enabled: bool = True
    welcome_threshold_minutes: int = 30  # Welcome back if gone > 30 min
    _loaded: bool = False

    def load(self) -> None:
        """Load engagement data from file."""
        if self._loaded:
            return

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if ENGAGEMENT_FILE.exists():
                with open(ENGAGEMENT_FILE) as f:
                    data = json.load(f)
                    for username, stats in data.get("viewers", {}).items():
                        self.viewers[username] = ViewerStats(
                            username=username,
                            message_count=stats.get("message_count", 0),
                            first_seen=stats.get("first_seen", ""),
                            last_seen=stats.get("last_seen", ""),
                            sessions=stats.get("sessions", 0),
                            lurk_count=stats.get("lurk_count", 0),
                        )
                logger.info(f"Loaded engagement data for {len(self.viewers)} viewers")
        except Exception as e:
            logger.warning(f"Could not load engagement data: {e}")

        self._loaded = True

    def save(self) -> None:
        """Save engagement data to file."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "viewers": {
                    username: {
                        "message_count": v.message_count,
                        "first_seen": v.first_seen,
                        "last_seen": v.last_seen,
                        "sessions": v.sessions,
                        "lurk_count": v.lurk_count,
                    }
                    for username, v in self.viewers.items()
                },
                "last_updated": datetime.now().isoformat(),
            }
            with open(ENGAGEMENT_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save engagement data: {e}")

    def on_message(self, msg: ChatMessage) -> str | None:
        """Process a chat message and return welcome message if appropriate."""
        self.load()

        username = msg.username.lower()
        now = datetime.now()
        now_str = now.isoformat()
        now_ts = time.time()

        # Get or create viewer stats
        if username not in self.viewers:
            self.viewers[username] = ViewerStats(
                username=username,
                first_seen=now_str,
            )
            is_new = True
        else:
            is_new = False

        viewer = self.viewers[username]
        viewer.message_count += 1
        viewer.last_seen = now_str

        # Check if this is a new session (first message in a while)
        last_msg_time = self.last_message_time.get(username, 0)
        minutes_since_last = (now_ts - last_msg_time) / 60

        welcome_message = None

        if username not in self.session_viewers:
            # First time seeing them this session
            self.session_viewers.add(username)
            viewer.sessions += 1

            if self.welcome_enabled:
                if is_new:
                    welcome_message = f"Welcome to the stream, @{msg.username}! 👋"
                elif minutes_since_last > self.welcome_threshold_minutes and viewer.sessions > 1:
                    welcome_message = f"Welcome back, @{msg.username}! Good to see you again!"

        self.last_message_time[username] = now_ts

        # Periodic save (every 50 messages)
        if sum(v.message_count for v in self.viewers.values()) % 50 == 0:
            self.save()

        return welcome_message

    def record_lurk(self, username: str) -> None:
        """Record that a user is lurking."""
        self.load()
        username = username.lower()
        if username not in self.viewers:
            self.viewers[username] = ViewerStats(
                username=username,
                first_seen=datetime.now().isoformat(),
            )
        self.viewers[username].lurk_count += 1
        self.viewers[username].last_seen = datetime.now().isoformat()

    def get_top_chatters(self, count: int = 10) -> list[dict]:
        """Get most active chatters."""
        self.load()
        sorted_viewers = sorted(
            self.viewers.values(),
            key=lambda v: v.message_count,
            reverse=True,
        )
        return [
            {
                "username": v.username,
                "message_count": v.message_count,
                "sessions": v.sessions,
                "first_seen": v.first_seen,
            }
            for v in sorted_viewers[:count]
        ]

    def get_loyal_viewers(self, count: int = 10) -> list[dict]:
        """Get viewers with most sessions (most loyal)."""
        self.load()
        sorted_viewers = sorted(
            self.viewers.values(),
            key=lambda v: v.sessions,
            reverse=True,
        )
        return [
            {
                "username": v.username,
                "sessions": v.sessions,
                "message_count": v.message_count,
                "first_seen": v.first_seen,
            }
            for v in sorted_viewers[:count]
        ]


# Global tracker instance
_tracker = EngagementTracker()


def _message_handler(msg: ChatMessage) -> None:
    """Handler for incoming chat messages."""
    welcome = _tracker.on_message(msg)
    if welcome:
        try:
            twitch = get_twitch_client()
            twitch.send_chat_message(welcome)
        except Exception as e:
            logger.warning(f"Could not send welcome message: {e}")


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
def enable_welcome_messages() -> dict:
    """
    Enable automatic welcome messages for viewers.

    Welcomes new viewers and greets returning viewers.

    Returns:
        Status dict.
    """
    _tracker.load()
    _tracker.welcome_enabled = True

    # Register as chat message handler
    try:
        twitch = get_twitch_client()
        twitch.add_message_handler(_message_handler)
        logger.info("Welcome messages enabled")
        return {"status": "enabled"}
    except Exception as e:
        logger.error(f"Failed to enable welcome messages: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def disable_welcome_messages() -> dict:
    """
    Disable automatic welcome messages.

    Returns:
        Status dict.
    """
    _tracker.welcome_enabled = False
    logger.info("Welcome messages disabled")
    return {"status": "disabled"}


@mcp.tool()
def set_welcome_threshold(minutes: int) -> dict:
    """
    Set how long a viewer must be gone before getting a "welcome back" message.

    Args:
        minutes: Minutes of inactivity before welcome back (default: 30)

    Returns:
        Status dict.
    """
    _tracker.welcome_threshold_minutes = minutes
    return {"status": "updated", "threshold_minutes": minutes}


@mcp.tool()
def get_viewer_stats(username: str) -> dict:
    """
    Get engagement stats for a specific viewer.

    Args:
        username: The viewer's username

    Returns:
        Stats dict.
    """
    _tracker.load()
    username = username.lower()
    if username in _tracker.viewers:
        v = _tracker.viewers[username]
        return {
            "username": v.username,
            "message_count": v.message_count,
            "sessions": v.sessions,
            "first_seen": v.first_seen,
            "last_seen": v.last_seen,
            "lurk_count": v.lurk_count,
        }
    return {"status": "not_found", "username": username}


@mcp.tool()
def get_top_chatters(count: int = 10) -> list[dict]:
    """
    Get the most active chatters by message count.

    Args:
        count: Number of top chatters to return

    Returns:
        List of chatter stats.
    """
    return _tracker.get_top_chatters(count)


@mcp.tool()
def get_loyal_viewers(count: int = 10) -> list[dict]:
    """
    Get the most loyal viewers by session count.

    These are viewers who come back stream after stream.

    Args:
        count: Number of loyal viewers to return

    Returns:
        List of viewer stats.
    """
    return _tracker.get_loyal_viewers(count)


@mcp.tool()
def get_session_summary() -> dict:
    """
    Get a summary of this stream session's engagement.

    Returns:
        Dict with session stats.
    """
    _tracker.load()

    # Get viewers from this session
    session_viewers = list(_tracker.session_viewers)
    session_message_counts = {
        v: _tracker.viewers.get(v, ViewerStats(v)).message_count
        for v in session_viewers
    }

    new_viewers = [
        v for v in session_viewers
        if _tracker.viewers.get(v) and _tracker.viewers[v].sessions == 1
    ]

    returning_viewers = [
        v for v in session_viewers
        if _tracker.viewers.get(v) and _tracker.viewers[v].sessions > 1
    ]

    total_messages = sum(session_message_counts.values())
    top_chatters = sorted(
        session_message_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    return {
        "unique_viewers": len(session_viewers),
        "new_viewers": len(new_viewers),
        "returning_viewers": len(returning_viewers),
        "total_messages": total_messages,
        "top_chatters": [{"username": u, "messages": c} for u, c in top_chatters],
    }


@mcp.tool()
def reset_session() -> dict:
    """
    Reset session tracking for a new stream.

    Call this at the start of each stream to properly track per-session stats.

    Returns:
        Status dict.
    """
    _tracker.session_viewers.clear()
    _tracker.last_message_time.clear()
    _tracker.save()
    logger.info("Session reset")
    return {"status": "reset"}


@mcp.tool()
def export_engagement_data() -> dict:
    """
    Export all engagement data.

    Returns:
        Full engagement data dict.
    """
    _tracker.load()
    return {
        "total_viewers_tracked": len(_tracker.viewers),
        "viewers": [
            {
                "username": v.username,
                "message_count": v.message_count,
                "sessions": v.sessions,
                "first_seen": v.first_seen,
                "last_seen": v.last_seen,
                "lurk_count": v.lurk_count,
            }
            for v in sorted(_tracker.viewers.values(), key=lambda x: x.message_count, reverse=True)
        ],
    }
