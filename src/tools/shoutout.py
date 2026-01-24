"""
Streamer shoutout tools.
"""

import asyncio

from ..app import mcp, get_obs_client, get_twitch_client


@mcp.tool()
def shoutout_streamer(
    username: str,
    show_clip: bool = True,
    duration_seconds: int = 15,
    custom_message: str = "",
    use_profile_data: bool = True,
) -> str:
    """
    Shoutout another streamer with optional clip overlay.

    Now includes profile-based personalization:
    - Mentions if they're a Partner/Affiliate
    - Includes their current game/category
    - Shows view count context
    - Smarter fallback if no clips

    1. Sends personalized shoutout in chat
    2. Optionally displays their latest clip on stream
    3. Auto-removes after duration

    Args:
        username: The streamer to shoutout
        show_clip: Whether to show their latest clip (default: True)
        duration_seconds: How long to show the clip overlay
        custom_message: Custom shoutout message (optional)
        use_profile_data: Personalize with profile info (default: True)
    """
    twitch = get_twitch_client()
    obs = get_obs_client()

    # Generate personalized message
    if custom_message:
        message = f"Go check out @{username}! {custom_message} https://twitch.tv/{username}"
    elif use_profile_data:
        # Fetch profile data (uses cache)
        profile = twitch.get_user_profile(username)
        channel = twitch.get_channel_info(username)

        # Build context-aware message
        message_parts = []

        # Broadcaster type
        if profile and profile.get("broadcaster_type") == "partner":
            message_parts.append(f"🎯 Go check out verified partner @{username}!")
        elif profile and profile.get("broadcaster_type") == "affiliate":
            message_parts.append(f"⭐ Go check out affiliate @{username}!")
        else:
            message_parts.append(f"✨ Go check out @{username}!")

        # Game/category
        if channel and channel.get("game_name"):
            message_parts.append(f"They stream {channel['game_name']}.")

        # View count context
        if profile and profile.get("view_count"):
            views = profile["view_count"]
            if views > 1000000:
                message_parts.append(f"Over {views // 1000000}M channel views!")
            elif views > 10000:
                message_parts.append(f"{views // 1000}K+ channel views!")

        message_parts.append(f"https://twitch.tv/{username}")
        message = " ".join(message_parts)
    else:
        # Fallback to generic message
        message = f"🎉 Go check out @{username}! They're awesome! https://twitch.tv/{username}"

    twitch.send_chat_message(message)

    # Try official shoutout command
    try:
        twitch.shoutout(username)
    except Exception:
        pass  # May fail if not affiliate/partner

    result = f"Shouted out {username} in chat"

    # Show clip if requested
    if show_clip:
        clips = twitch.get_user_clips(username, count=1)
        if clips:
            clip = clips[0]
            scene = obs.get_current_scene()
            embed_url = f"{clip['embed_url']}&parent=localhost&autoplay=true&muted=false"

            # Try to edit existing source first, create if doesn't exist
            try:
                obs.set_input_settings("shoutout-clip", {"url": embed_url})
                # Make sure it's visible
                try:
                    item_id = obs.client.get_scene_item_id(scene, "shoutout-clip").scene_item_id
                    obs.set_scene_item_enabled(scene, item_id, True)
                except Exception:
                    pass
            except Exception:
                # Source doesn't exist, create it
                obs.create_browser_source(scene, "shoutout-clip", embed_url, 640, 360)
                # Position in corner
                item_id = obs.client.get_scene_item_id(scene, "shoutout-clip").scene_item_id
                obs.set_scene_item_transform(scene, item_id, 1600, 100, alignment=9)  # Top-right

            result += f" with clip: {clip['title']}"

            # Schedule hiding (not removal)
            async def hide_after_delay():
                await asyncio.sleep(duration_seconds)
                try:
                    item_id = obs.client.get_scene_item_id(scene, "shoutout-clip").scene_item_id
                    obs.set_scene_item_enabled(scene, item_id, False)
                except Exception:
                    pass

            asyncio.create_task(hide_after_delay())
        else:
            result += " (no clips found)"

    return result


@mcp.tool()
def get_streamer_profile(username: str) -> dict:
    """
    Get full Twitch profile for a streamer.

    Returns profile data including bio, broadcaster type, view count, panels, etc.
    Cached for 1 hour to reduce API calls.

    Args:
        username: Twitch username

    Returns:
        Profile dict with bio, broadcaster_type, view_count, panels, etc.
    """
    twitch = get_twitch_client()
    profile = twitch.get_user_profile(username)

    if not profile:
        return {"error": f"User {username} not found"}

    return {
        "username": profile["login"],
        "display_name": profile["display_name"],
        "bio": profile["description"],
        "broadcaster_type": profile["broadcaster_type"] or "user",
        "profile_image": profile["profile_image_url"],
        "view_count": profile["view_count"],
        "created_at": profile["created_at"],
        "panels": profile.get("panels", []),
    }


@mcp.tool()
def get_streamer_channel_info(username: str) -> dict:
    """
    Get current channel info (game, title, language).

    Args:
        username: Twitch username

    Returns:
        Channel info dict with current game, title, language
    """
    twitch = get_twitch_client()
    channel = twitch.get_channel_info(username)

    if not channel:
        return {"error": f"Channel info for {username} not found"}

    return {
        "username": channel["broadcaster_login"],
        "display_name": channel["broadcaster_name"],
        "game": channel["game_name"],
        "title": channel["title"],
        "language": channel["broadcaster_language"],
    }


@mcp.tool()
def get_streamer_clips(username: str, count: int = 5) -> list[dict]:
    """
    Get recent clips from a streamer.

    Args:
        username: The streamer's username
        count: Number of clips to fetch (max 100)
    """
    twitch = get_twitch_client()
    return twitch.get_user_clips(username, count)


@mcp.tool()
def get_streamer_panels(username: str) -> list[dict]:
    """
    Get custom panels from a Twitch channel (e.g., "My Game Grimoire", "The Rig").

    Returns panels from cache if available (1-hour TTL), otherwise scrapes.

    Args:
        username: Twitch username

    Returns:
        List of panel dicts with title, description, image_url, link_url
    """
    twitch = get_twitch_client()
    profile = twitch.get_user_profile(username)

    if not profile:
        return []

    return profile.get("panels", [])


@mcp.tool()
def clear_shoutout_clip() -> str:
    """Remove the shoutout clip overlay."""
    obs = get_obs_client()
    try:
        obs.remove_source("shoutout-clip")
        return "Shoutout clip removed"
    except Exception:
        return "No shoutout clip to remove"
