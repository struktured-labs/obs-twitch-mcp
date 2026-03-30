"""
Twitch chat interaction tools.
"""

import os
from datetime import datetime

from ..app import mcp, get_twitch_client, refresh_twitch_client, get_chat_listener
from ..utils import chat_logger
from ..utils.logger import get_logger
from ..utils.twitch_auth import save_token, load_token, get_valid_token, TokenExpiredError

logger = get_logger("chat_tools")



@mcp.tool()
def twitch_send_message(message: str) -> str:
    """Send a message to Twitch chat."""
    # Use the persistent chat listener connection (non-blocking)
    listener = get_chat_listener()
    if listener and listener.is_running:
        listener.send_message(message)
        return f"Sent to chat: {message}"
    else:
        # Fallback to client method (blocks for 8s, but only if listener not running)
        client = get_twitch_client()
        client.send_chat_message(message)
        return f"Sent to chat (fallback): {message}"


@mcp.tool()
def twitch_reply_to_user(username: str, message: str) -> str:
    """Reply to a specific user in chat (mentions them)."""
    full_message = f"@{username} {message}"
    # Use the persistent chat listener connection (non-blocking)
    listener = get_chat_listener()
    if listener and listener.is_running:
        listener.send_message(full_message)
        return f"Replied to @{username}: {message}"
    else:
        # Fallback to client method (blocks for 8s, but only if listener not running)
        client = get_twitch_client()
        client.send_chat_message(full_message)
        return f"Replied to @{username}: {message} (fallback)"


@mcp.tool()
def twitch_get_recent_messages(count: int = 10) -> list[dict]:
    """
    Get recent chat messages from the cache.

    Note: Messages are only cached while the server is running.
    """
    client = get_twitch_client()
    messages = client.get_recent_messages(count)
    return [
        {
            "username": m.username,
            "message": m.message,
            "is_mod": m.is_mod,
            "is_subscriber": m.is_subscriber,
        }
        for m in messages
    ]


@mcp.tool()
def twitch_get_chat_history(date: str = "", limit: int = 100) -> list[dict]:
    """
    Get chat history from saved logs.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        limit: Maximum number of messages to return.

    Returns:
        List of chat messages with timestamp, username, message, etc.
    """
    if date:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return [{"error": "Invalid date format. Use YYYY-MM-DD"}]
    else:
        dt = None

    return chat_logger.read_logs(dt, limit)


@mcp.tool()
def twitch_list_chat_log_dates() -> list[str]:
    """
    List all available chat log dates.

    Returns:
        List of dates (YYYY-MM-DD) that have chat logs, newest first.
    """
    return chat_logger.get_available_dates()


@mcp.tool()
def twitch_refresh_token() -> dict:
    """
    Refresh the Twitch OAuth token and reconnect.

    This actually calls Twitch's OAuth endpoint to refresh the access token
    using the refresh_token, then restarts the client with the new token.

    Use this when API calls fail with 401 Unauthorized.
    """
    client_id = os.getenv("TWITCH_CLIENT_ID", "")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return {
            "status": "error",
            "message": "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET required for token refresh",
        }

    try:
        # Actually refresh the token via Twitch OAuth API
        new_token = get_valid_token(client_id, client_secret)

        # Reload the client with the SAME token - don't re-discover
        client = refresh_twitch_client(token=new_token)

        return {
            "status": "refreshed",
            "channel": client.channel,
            "message": "Token refreshed via Twitch OAuth and client restarted",
        }
    except TokenExpiredError as e:
        return {
            "status": "error",
            "message": f"Token refresh failed - run 'uv run python auth.py' manually: {e}",
        }


@mcp.tool()
def twitch_reconnect() -> dict:
    """
    Reconnect to Twitch with fresh credentials.

    This refreshes the OAuth token, recreates the Twitch client,
    and restarts the chat listener - all without restarting the MCP server.

    Use this when:
    - Chat messages aren't sending
    - Token has expired
    - IRC connection dropped
    """
    from ..utils.twitch_auth import validate_token, load_token

    # Get a valid token first, then pass it through
    client_id = os.getenv("TWITCH_CLIENT_ID", "")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")
    token = ""
    if client_id and client_secret:
        try:
            token = get_valid_token(client_id, client_secret)
        except Exception:
            pass
    if not token:
        token_data = load_token()
        token = token_data.get("access_token", "") if token_data else ""

    # Refresh the client with the known token
    client = refresh_twitch_client(token=token)

    # Validate the token
    validation = validate_token(token) if token else None

    if validation:
        expires_hours = validation.get("expires_in", 0) // 3600
        return {
            "status": "connected",
            "channel": client.channel,
            "user": validation.get("login"),
            "token_expires_in": f"{expires_hours} hours",
            "scopes": validation.get("scopes", []),
        }
    else:
        return {
            "status": "warning",
            "channel": client.channel,
            "message": "Reconnected but could not validate token - may need to re-auth",
        }


@mcp.tool()
def twitch_create_poll(
    title: str,
    choices: list[str],
    duration: int = 60,
) -> dict:
    """
    Create a poll on Twitch.

    Args:
        title: Poll question (max 60 chars)
        choices: List of 2-5 choices (max 25 chars each)
        duration: Duration in seconds (15-1800, default 60)

    Returns:
        Poll details including ID for ending early
    """
    client = get_twitch_client()
    return client.create_poll(title, choices, duration)


@mcp.tool()
def twitch_end_poll(poll_id: str, show_results: bool = True) -> dict:
    """
    End a poll early.

    Args:
        poll_id: The poll ID from create_poll
        show_results: If True, show final results. If False, cancel silently.

    Returns:
        Final poll results with vote counts
    """
    client = get_twitch_client()
    return client.end_poll(poll_id, archive=show_results)


@mcp.tool()
def twitch_get_polls() -> list[dict]:
    """
    Get active and recent polls.

    Returns:
        List of polls with their status and vote counts
    """
    client = get_twitch_client()
    return client.get_polls()


_device_code_state: dict | None = None
"""Tracks in-progress device code auth flow (non-blocking)."""


def _try_token_file_and_reconnect(client_id: str, client_secret: str) -> dict | None:
    """
    Try to get a valid token from the token file (same as auth.py does).
    Returns success dict or None if it didn't work.
    """
    from ..utils.twitch_auth import validate_token

    try:
        new_token = get_valid_token(client_id, client_secret)
        client = refresh_twitch_client(token=new_token)
        validation = validate_token(new_token)
        if validation:
            expires_hours = validation.get("expires_in", 0) // 3600
            return {
                "status": "success",
                "channel": client.channel,
                "user": validation.get("login"),
                "token_expires_in": f"{expires_hours} hours",
                "scopes": validation.get("scopes", []),
            }
        else:
            return {
                "status": "refreshed",
                "channel": client.channel,
                "message": "Token refreshed but validation failed - may still work",
            }
    except Exception:
        return None


def _run_auth_py_subprocess(client_id: str, client_secret: str) -> dict | None:
    """
    Run auth.py as a subprocess — this is what always works.
    auth.py reads the token file, refreshes via Twitch API, and saves.
    Only blocks for a few seconds (no interactive prompts unless refresh
    token is truly dead).
    """
    import subprocess
    from pathlib import Path
    from ..utils.twitch_auth import validate_token

    auth_py = Path(__file__).parent.parent.parent / "auth.py"
    if not auth_py.exists():
        return None

    try:
        logger.info(f"twitch_reauth: running auth.py subprocess from {auth_py.parent}...")
        env = dict(os.environ)
        env["TWITCH_CLIENT_ID"] = client_id
        env["TWITCH_CLIENT_SECRET"] = client_secret

        # Find uv binary — might not be in MCP server's PATH
        import shutil
        uv_path = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv") or "uv"
        logger.info(f"twitch_reauth: using uv at {uv_path}")

        result = subprocess.run(
            [uv_path, "run", "python", str(auth_py)],
            cwd=str(auth_py.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0 and "SUCCESS" in result.stdout:
            logger.info("twitch_reauth: auth.py succeeded, loading fresh token...")
            # auth.py saved the token file — now load and reconnect
            new_token = get_valid_token(client_id, client_secret)
            client = refresh_twitch_client(token=new_token)
            validation = validate_token(new_token)
            if validation:
                expires_hours = validation.get("expires_in", 0) // 3600
                return {
                    "status": "success",
                    "channel": client.channel,
                    "user": validation.get("login"),
                    "token_expires_in": f"{expires_hours} hours",
                    "scopes": validation.get("scopes", []),
                }
            return {
                "status": "refreshed",
                "channel": client.channel,
                "message": "Token refreshed via auth.py",
            }
        else:
            logger.warning(f"twitch_reauth: auth.py failed (rc={result.returncode}): stdout={result.stdout[:200]} stderr={result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning("twitch_reauth: auth.py timed out (probably needs browser auth)")
        return None
    except Exception as e:
        logger.warning(f"twitch_reauth: auth.py subprocess error: {e}")
        return None


@mcp.tool()
def twitch_reauth() -> dict:
    """
    Refresh Twitch token and reconnect automatically.

    Flow:
    1. Return existing token if still valid
    2. Refresh via refresh_token if expired
    3. If refresh_token itself is invalid, start device code flow
       and return the URL/code for the user to authorize in browser.
       Call twitch_reauth again after authorizing to complete.

    Use this when:
    - Chat messages aren't sending
    - API calls fail with 401
    - Token has expired

    Returns:
        Dict with status, channel, user info, and token expiry
    """
    global _device_code_state
    from ..utils.twitch_auth import (
        validate_token,
        get_device_code,
        save_token,
    )

    client_id = os.getenv("TWITCH_CLIENT_ID", "")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return {
            "status": "error",
            "message": "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET required",
        }

    # ALWAYS try the token file first — even if there's a pending device code.
    # Another process (auth.py, another session) may have refreshed it.
    logger.info("twitch_reauth: trying token file first...")
    result = _try_token_file_and_reconnect(client_id, client_secret)
    if result:
        _device_code_state = None  # Clear any pending device code
        return result

    # Token file didn't work — try running auth.py subprocess.
    # This is the most reliable path: same thing that works from CLI.
    logger.info("twitch_reauth: token file failed, trying auth.py subprocess...")
    result = _run_auth_py_subprocess(client_id, client_secret)
    if result:
        _device_code_state = None
        return result

    # If there's a pending device code flow, check if user authorized
    if _device_code_state:
        logger.info("twitch_reauth: checking pending device code auth...")
        try:
            import time
            state = _device_code_state
            elapsed = time.time() - state["started_at"]
            if elapsed > state["expires_in"]:
                _device_code_state = None
                return {
                    "status": "error",
                    "message": "Device code expired. Call twitch_reauth again to get a new code.",
                }

            import httpx
            resp = httpx.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": client_id,
                    "scopes": " ".join(state["scopes"]),
                    "device_code": state["device_code"],
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                timeout=10.0,
            )
            data = resp.json()

            if resp.status_code == 200:
                _device_code_state = None
                save_token(data)
                new_token = data["access_token"]
                client = refresh_twitch_client(token=new_token)
                validation = validate_token(new_token)
                if validation:
                    expires_hours = validation.get("expires_in", 0) // 3600
                    return {
                        "status": "success",
                        "channel": client.channel,
                        "user": validation.get("login"),
                        "token_expires_in": f"{expires_hours} hours",
                        "scopes": validation.get("scopes", []),
                    }
                return {
                    "status": "success",
                    "channel": client.channel,
                    "message": "Authorized via device code flow",
                }
            elif data.get("message") == "authorization_pending":
                return {
                    "status": "awaiting_auth",
                    "message": f"Still waiting for browser authorization. Go to: {state['verification_uri']}?device-code={state['user_code']} and enter code: {state['user_code']}",
                    "url": state["verification_uri"],
                    "code": state["user_code"],
                    "elapsed_seconds": int(elapsed),
                    "expires_in_seconds": state["expires_in"] - int(elapsed),
                }
            else:
                _device_code_state = None
                return {
                    "status": "error",
                    "message": f"Device code auth failed: {data}",
                }
        except Exception as e:
            _device_code_state = None
            return {"status": "error", "message": f"Device code poll failed: {e}"}

    # Last resort: start device code flow
    logger.warning("twitch_reauth: all refresh methods failed, starting device code flow...")
    try:
        import time
        scopes = [
            "chat:edit", "chat:read",
            "channel:manage:broadcast", "channel:manage:polls",
            "channel:manage:predictions", "channel:manage:raids",
            "channel:manage:schedule", "channel:manage:videos",
            "channel:read:polls", "channel:read:predictions",
            "channel:read:subscriptions", "channel:read:vips",
            "moderator:manage:announcements",
            "moderator:manage:banned_users", "moderator:manage:blocked_terms",
            "moderator:manage:chat_messages", "moderator:manage:shoutouts",
            "moderator:read:blocked_terms", "moderator:read:chatters",
            "clips:edit",
        ]
        device_data = get_device_code(client_id, scopes)
        _device_code_state = {
            "device_code": device_data["device_code"],
            "user_code": device_data["user_code"],
            "verification_uri": device_data["verification_uri"],
            "expires_in": device_data["expires_in"],
            "scopes": scopes,
            "started_at": time.time(),
        }

        return {
            "status": "device_code_started",
            "message": "Refresh token expired. Authorize in browser, then call twitch_reauth again.",
            "url": device_data["verification_uri"],
            "code": device_data["user_code"],
            "full_url": f"{device_data['verification_uri']}?device-code={device_data['user_code']}",
            "expires_in_seconds": device_data["expires_in"],
        }
    except Exception as dc_err:
        return {
            "status": "error",
            "message": f"All auth methods failed: {dc_err}",
        }


@mcp.tool()
def twitch_reauth_status() -> dict:
    """
    Check current token status.

    Returns:
        Dict with token validity, user, and expiry info
    """
    from ..utils.twitch_auth import load_token, validate_token
    import time

    token_data = load_token()
    if not token_data:
        return {"status": "no_token", "message": "No token file found. Run twitch_reauth() or 'uv run python auth.py'."}

    token = token_data.get("access_token", "")
    validation = validate_token(token) if token else None

    if validation:
        expires_in = validation.get("expires_in", 0)
        return {
            "status": "valid",
            "user": validation.get("login"),
            "expires_in_hours": expires_in // 3600,
            "expires_in_minutes": (expires_in % 3600) // 60,
            "scopes": validation.get("scopes", []),
        }
    else:
        # Check if we have expires_at to give more info
        expires_at = token_data.get("expires_at", 0)
        if expires_at and time.time() > expires_at:
            return {"status": "expired", "message": "Token expired. Run twitch_reauth() to refresh."}
        return {"status": "invalid", "message": "Token invalid. Run twitch_reauth() to refresh."}
