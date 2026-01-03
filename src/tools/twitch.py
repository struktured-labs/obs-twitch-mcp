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


@mcp.tool()
def twitch_raid(username: str = "") -> dict:
    """
    Start a raid to another channel.

    If no username is provided, finds streamers in the same category
    and returns suggestions. If a username is provided, starts the raid.

    Args:
        username: The streamer to raid (optional - if empty, finds suggestions)

    Returns:
        If username provided: raid status
        If no username: list of suggested raid targets in same category
    """
    client = get_twitch_client()

    if username:
        # Direct raid to specified user
        result = client.start_raid(username)
        return {
            "status": "raid_started",
            "target": username,
            "details": result,
        }

    # No username - find suggestions based on current category
    stream_info = client.get_stream_info()
    if not stream_info:
        return {
            "status": "error",
            "message": "Not currently streaming - cannot determine category",
        }

    game_id = stream_info.get("game_id")
    game_name = stream_info.get("game_name")

    if not game_id:
        return {
            "status": "error",
            "message": "No game/category set on stream",
        }

    # Get streamers in same category
    streams = client.get_streams_by_game(game_id, count=20)

    # Filter out self
    my_channel = client.channel.lower()
    suggestions = [
        s for s in streams
        if s["user_login"].lower() != my_channel
    ]

    # Sort by viewer count (prefer similar-sized streams)
    suggestions.sort(key=lambda x: x["viewer_count"])

    return {
        "status": "suggestions",
        "category": game_name,
        "targets": suggestions[:10],  # Top 10 suggestions
        "hint": "Call twitch_raid with a username to start the raid",
    }


@mcp.tool()
def twitch_cancel_raid() -> str:
    """Cancel an ongoing raid."""
    client = get_twitch_client()
    return client.cancel_raid()


@mcp.tool()
def twitch_find_raid_targets(category: str = "", count: int = 10) -> dict:
    """
    Find potential raid targets.

    Args:
        category: Game/category to search (uses current stream category if empty)
        count: Number of suggestions to return (default 10)

    Returns:
        List of streamers in the category sorted by viewer count
    """
    client = get_twitch_client()

    game_id = None
    game_name = category

    if not category:
        # Use current stream's category
        stream_info = client.get_stream_info()
        if stream_info:
            game_id = stream_info.get("game_id")
            game_name = stream_info.get("game_name")

    if not game_id and category:
        # Search for the category
        games = client.search_game(category)
        if games:
            game_id = games[0]["id"]
            game_name = games[0]["name"]

    if not game_id:
        return {
            "status": "error",
            "message": "Could not determine category",
        }

    # Get streamers
    streams = client.get_streams_by_game(game_id, count=count + 5)

    # Filter out self
    my_channel = client.channel.lower()
    targets = [
        s for s in streams
        if s["user_login"].lower() != my_channel
    ][:count]

    return {
        "category": game_name,
        "targets": targets,
    }
