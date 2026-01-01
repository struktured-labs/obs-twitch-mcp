"""
Twitch stream management tools.
"""

from ..app import mcp, get_twitch_client


@mcp.tool()
def twitch_get_stream_info() -> dict:
    """
    Get current stream information.

    Returns title, game, viewer count, and start time.
    Returns None if not currently streaming.
    """
    client = get_twitch_client()
    info = client.get_stream_info()
    if info is None:
        return {"status": "offline"}
    return info


@mcp.tool()
def twitch_set_stream_title(title: str) -> str:
    """Update the stream title."""
    client = get_twitch_client()
    client.set_stream_info(title=title)
    return f"Stream title updated to: {title}"


@mcp.tool()
def twitch_set_stream_game(game_name: str) -> str:
    """
    Update the stream game/category.

    Searches for the game by name and sets it.
    """
    client = get_twitch_client()

    # Search for game
    games = client.search_game(game_name)
    if not games:
        return f"Game not found: {game_name}"

    # Use first match
    game = games[0]
    client.set_stream_info(game_id=game["id"])
    return f"Stream game updated to: {game['name']}"


@mcp.tool()
def twitch_search_game(query: str) -> list[dict]:
    """
    Search for a game/category by name.

    Returns list of matching games with IDs.
    """
    client = get_twitch_client()
    return client.search_game(query)
