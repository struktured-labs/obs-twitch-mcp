"""
Automatic spam detection and moderation for Twitch chat.

Monitors chat messages for common spam patterns and auto-bans spammers.
"""

import re
from typing import Callable

from .logger import get_logger
from .twitch_client import ChatMessage

logger = get_logger("spam_filter")


class SpamFilter:
    """
    Auto-moderator for detecting and banning spam in Twitch chat.

    Detects common spam patterns like fake viewer services, follow bots, etc.
    """

    # Spam patterns to detect (case-insensitive)
    SPAM_PATTERNS = [
        # Fake viewer services
        r"streamboo",
        r"viewbotting",
        r"buy.*viewers",
        r"boost.*viewers",
        r"get.*viewers.*cheap",

        # Follow bots
        r"followbot",
        r"instant.*followers",
        r"buy.*followers",

        # Common spam domains
        r"bigfollows\.com",
        r"primebot\.org",

        # Suspicious patterns
        r"@\w+ remove the space",  # Common spam format
        r"best viewers on \w+\.com",
    ]

    def __init__(self, ban_callback: Callable[[str, str], None]):
        """
        Initialize spam filter.

        Args:
            ban_callback: Function to call when spam is detected.
                         Takes (username, reason) as arguments.
        """
        self.ban_callback = ban_callback
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.SPAM_PATTERNS]
        logger.info(f"Spam filter initialized with {len(self.patterns)} patterns")

    def check_message(self, msg: ChatMessage) -> bool:
        """
        Check if a message is spam.

        Args:
            msg: Chat message to check

        Returns:
            True if message is spam, False otherwise
        """
        # Don't check mods/subs (they're trusted)
        if msg.is_mod or msg.is_subscriber:
            return False

        message_lower = msg.message.lower()

        # Check each spam pattern
        for pattern in self.patterns:
            if pattern.search(message_lower):
                logger.warning(
                    f"SPAM DETECTED from {msg.username}: {msg.message[:100]} "
                    f"(matched pattern: {pattern.pattern})"
                )
                return True

        return False

    def handle_message(self, msg: ChatMessage) -> None:
        """
        Message handler that auto-bans spammers.

        This is called for every chat message by the chat listener.

        Args:
            msg: Incoming chat message
        """
        if self.check_message(msg):
            try:
                reason = f"Automatic ban: spam detected ({msg.message[:50]}...)"
                self.ban_callback(msg.username, reason)
                logger.info(f"Auto-banned spam account: {msg.username}")
            except Exception as e:
                logger.error(f"Failed to ban spammer {msg.username}: {e}")


# Global spam filter instance
_spam_filter: SpamFilter | None = None


def get_spam_filter() -> SpamFilter | None:
    """Get the global spam filter instance."""
    return _spam_filter


def enable_spam_filter(ban_callback: Callable[[str, str], None]) -> SpamFilter:
    """
    Enable automatic spam filtering.

    Args:
        ban_callback: Function to call when banning spammers

    Returns:
        The spam filter instance
    """
    global _spam_filter

    if _spam_filter is not None:
        logger.warning("Spam filter already enabled")
        return _spam_filter

    _spam_filter = SpamFilter(ban_callback)
    logger.info("Spam filter enabled - auto-banning spam accounts")
    return _spam_filter


def disable_spam_filter() -> None:
    """Disable automatic spam filtering."""
    global _spam_filter

    if _spam_filter is None:
        logger.warning("Spam filter not enabled")
        return

    _spam_filter = None
    logger.info("Spam filter disabled")
