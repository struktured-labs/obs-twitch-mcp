"""
Centralized logging for obs-twitch-mcp server.

Provides consistent logging across all modules with proper formatting.
"""

import logging
import sys

# Create logger
logger = logging.getLogger("obs-twitch-mcp")
logger.setLevel(logging.DEBUG)

# Console handler with formatting
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
console_handler.setFormatter(formatter)

# Add handler if not already added
if not logger.handlers:
    logger.addHandler(console_handler)


def get_logger(name: str = "") -> logging.Logger:
    """Get a child logger with optional name suffix."""
    if name:
        return logger.getChild(name)
    return logger
