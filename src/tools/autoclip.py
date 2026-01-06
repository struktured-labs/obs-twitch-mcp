"""
Auto-clip system that detects hype moments in chat.

Monitors chat activity and automatically creates clips when:
- Chat speed spikes (many messages in short time)
- Certain keywords appear (POG, CLIP, etc.)
- Emote spam is detected

Uses a sliding window to detect activity spikes.
"""

import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from ..app import mcp, get_twitch_client
from ..utils.logger import get_logger
from ..utils.twitch_client import ChatMessage

logger = get_logger("autoclip")

# Hype detection settings
WINDOW_SECONDS = 10  # Sliding window for message rate
SPIKE_THRESHOLD = 5  # Messages per second to trigger (normally ~1-2 msg/sec)
COOLDOWN_SECONDS = 60  # Minimum time between auto-clips
HYPE_KEYWORDS = [
    "pog", "pogchamp", "pogu", "clip", "clip it", "omg", "holy",
    "wtf", "lol", "lmao", "gg", "ez", "w", "dub", "let's go",
    "no way", "insane", "crazy", "nani", "bruh",
]
HYPE_EMOTES = [
    "PogChamp", "KEKW", "LUL", "OMEGALUL", "PepeHands", "Pog",
    "POGGERS", "monkaS", "monkaW", "PauseChamp", "Kreygasm",
]


@dataclass
class HypeDetector:
    """Detects hype moments in chat."""

    message_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_clip_time: float = 0
    enabled: bool = False
    clip_callback: Callable[[], None] | None = None
    _monitor_thread: threading.Thread | None = None
    _running: bool = False

    def on_message(self, msg: ChatMessage) -> None:
        """Process an incoming chat message."""
        if not self.enabled:
            return

        now = time.time()
        self.message_times.append(now)

        # Check for hype keywords/emotes
        text_lower = msg.message.lower()
        keyword_match = any(kw in text_lower for kw in HYPE_KEYWORDS)
        emote_match = any(emote in msg.message for emote in HYPE_EMOTES)

        # Calculate recent message rate
        cutoff = now - WINDOW_SECONDS
        recent = sum(1 for t in self.message_times if t > cutoff)
        msg_rate = recent / WINDOW_SECONDS

        # Check if this is a hype moment
        is_hype = False
        reason = ""

        if msg_rate >= SPIKE_THRESHOLD:
            is_hype = True
            reason = f"Chat spike: {msg_rate:.1f} msg/sec"
        elif keyword_match and msg_rate >= SPIKE_THRESHOLD * 0.5:
            is_hype = True
            reason = f"Keyword + activity: {msg_rate:.1f} msg/sec"
        elif emote_match and msg_rate >= SPIKE_THRESHOLD * 0.5:
            is_hype = True
            reason = f"Emote spam + activity: {msg_rate:.1f} msg/sec"

        # Trigger clip if hype detected and not on cooldown
        if is_hype and (now - self.last_clip_time) >= COOLDOWN_SECONDS:
            logger.info(f"Hype detected! {reason}")
            self.last_clip_time = now
            if self.clip_callback:
                try:
                    self.clip_callback()
                except Exception as e:
                    logger.error(f"Auto-clip callback failed: {e}")

    def get_stats(self) -> dict:
        """Get current detection stats."""
        now = time.time()
        cutoff = now - WINDOW_SECONDS
        recent = sum(1 for t in self.message_times if t > cutoff)
        msg_rate = recent / WINDOW_SECONDS

        return {
            "enabled": self.enabled,
            "current_msg_rate": round(msg_rate, 2),
            "spike_threshold": SPIKE_THRESHOLD,
            "window_seconds": WINDOW_SECONDS,
            "cooldown_remaining": max(0, COOLDOWN_SECONDS - (now - self.last_clip_time)),
            "last_clip_time": datetime.fromtimestamp(self.last_clip_time).isoformat() if self.last_clip_time else None,
        }


# Global detector instance
_detector = HypeDetector()


def _create_clip():
    """Callback to create a clip when hype is detected."""
    from .clips import obs_clip
    result = obs_clip()
    if result.get("status") == "clipped":
        logger.info(f"Auto-clip saved: {result.get('file_path')}")
        # Optionally announce in chat
        try:
            twitch = get_twitch_client()
            twitch.send_chat_message("Hype moment clipped! PogChamp")
        except Exception:
            pass
    else:
        logger.warning(f"Auto-clip failed: {result}")


def _message_handler(msg: ChatMessage) -> None:
    """Handler for incoming chat messages."""
    _detector.on_message(msg)


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
def enable_autoclip() -> dict:
    """
    Enable automatic clip detection.

    Monitors chat for hype moments and automatically creates clips.

    Returns:
        Status dict.
    """
    if _detector.enabled:
        return {"status": "already_enabled"}

    _detector.enabled = True
    _detector.clip_callback = _create_clip

    # Register as chat message handler
    try:
        twitch = get_twitch_client()
        twitch.add_message_handler(_message_handler)
        logger.info("Auto-clip enabled")
        return {
            "status": "enabled",
            "settings": {
                "spike_threshold": f"{SPIKE_THRESHOLD} msg/sec",
                "window": f"{WINDOW_SECONDS} seconds",
                "cooldown": f"{COOLDOWN_SECONDS} seconds",
            },
        }
    except Exception as e:
        _detector.enabled = False
        logger.error(f"Failed to enable auto-clip: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def disable_autoclip() -> dict:
    """
    Disable automatic clip detection.

    Returns:
        Status dict.
    """
    _detector.enabled = False
    logger.info("Auto-clip disabled")
    return {"status": "disabled"}


@mcp.tool()
def get_autoclip_stats() -> dict:
    """
    Get current auto-clip detection stats.

    Shows message rate, detection thresholds, and cooldown status.

    Returns:
        Stats dict.
    """
    return _detector.get_stats()


@mcp.tool()
def set_autoclip_threshold(messages_per_second: float) -> dict:
    """
    Set the message rate threshold for auto-clip detection.

    Args:
        messages_per_second: New threshold (default is 5 msg/sec)

    Returns:
        Status dict.
    """
    global SPIKE_THRESHOLD
    SPIKE_THRESHOLD = messages_per_second
    return {
        "status": "updated",
        "new_threshold": messages_per_second,
    }


@mcp.tool()
def set_autoclip_cooldown(seconds: int) -> dict:
    """
    Set the cooldown between auto-clips.

    Args:
        seconds: New cooldown in seconds (default is 60)

    Returns:
        Status dict.
    """
    global COOLDOWN_SECONDS
    COOLDOWN_SECONDS = seconds
    return {
        "status": "updated",
        "new_cooldown": seconds,
    }


@mcp.tool()
def add_hype_keyword(keyword: str) -> dict:
    """
    Add a keyword that triggers hype detection.

    Args:
        keyword: The keyword to add (case-insensitive)

    Returns:
        Status dict.
    """
    keyword_lower = keyword.lower()
    if keyword_lower not in HYPE_KEYWORDS:
        HYPE_KEYWORDS.append(keyword_lower)
        return {"status": "added", "keyword": keyword_lower}
    return {"status": "already_exists", "keyword": keyword_lower}


@mcp.tool()
def list_hype_keywords() -> dict:
    """
    List all hype detection keywords.

    Returns:
        Dict with keywords and emotes.
    """
    return {
        "keywords": HYPE_KEYWORDS,
        "emotes": HYPE_EMOTES,
    }
