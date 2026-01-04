"""
OBS + Twitch MCP Server

A unified MCP server for OBS Studio control, Twitch integration,
and real-time game translation.
"""

from .app import mcp

# Import tools to register them with the mcp instance
from .tools import obs, chat, moderation, twitch, translation, alerts, shoutout, clips, uploads  # noqa: F401


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
