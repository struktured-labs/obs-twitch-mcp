"""
Twitch Device Code Flow authentication.

This provides a CLI-friendly way to authenticate with Twitch without
needing to handle redirect URIs or run a local server.
"""

import json
import time
from pathlib import Path

import httpx

from .logger import get_logger

logger = get_logger("twitch_auth")

TOKEN_FILE = Path(__file__).parent.parent.parent / ".twitch_token.json"


def get_device_code(client_id: str, scopes: list[str]) -> dict:
    """Request a device code from Twitch."""
    resp = httpx.post(
        "https://id.twitch.tv/oauth2/device",
        data={
            "client_id": client_id,
            "scopes": " ".join(scopes),
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def poll_for_token(client_id: str, scopes: list[str], device_code: str, interval: int = 5, timeout: int = 300) -> dict:
    """Poll Twitch until the user authorizes or timeout."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        resp = httpx.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": client_id,
                "scopes": " ".join(scopes),
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=10.0,
        )

        data = resp.json()

        if resp.status_code == 200:
            # Success!
            return data
        elif data.get("message") == "authorization_pending":
            # User hasn't authorized yet, wait and retry
            time.sleep(interval)
        elif data.get("message") == "slow_down":
            # We're polling too fast
            interval += 5
            time.sleep(interval)
        else:
            # Some other error
            raise ValueError(f"Token request failed: {data}")

    raise TimeoutError("User did not authorize in time")


def save_token(token_data: dict) -> None:
    """Save token to file."""
    token_data["saved_at"] = time.time()
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    logger.info(f"Token saved to {TOKEN_FILE}")


def load_token() -> dict | None:
    """Load token from file if it exists."""
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Refresh an expired access token."""
    resp = httpx.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def validate_token(access_token: str) -> dict | None:
    """Validate a token and get info about it."""
    resp = httpx.get(
        "https://id.twitch.tv/oauth2/validate",
        headers={"Authorization": f"OAuth {access_token}"},
        timeout=10.0,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def authenticate(client_id: str, scopes: list[str] | None = None) -> str:
    """
    Full device code authentication flow.

    Returns the access token.
    """
    if scopes is None:
        scopes = [
            "chat:edit",
            "chat:read",
            "channel:manage:broadcast",
            "channel:manage:raids",
            "channel:manage:videos",
            "moderator:manage:banned_users",
            "moderator:manage:chat_messages",
            "moderator:manage:shoutouts",
            "clips:edit",
        ]

    # Check for existing valid token
    existing = load_token()
    if existing:
        validation = validate_token(existing.get("access_token", ""))
        if validation:
            logger.info(f"Existing token valid for user: {validation.get('login')}")
            logger.info(f"Expires in: {validation.get('expires_in', 0) // 3600} hours")
            return existing["access_token"]
        else:
            logger.warning("Existing token expired, need to re-authenticate")

    # Start device code flow
    logger.info("Starting Twitch Device Code authentication...")
    logger.info(f"Requesting scopes: {', '.join(scopes)}")

    device_data = get_device_code(client_id, scopes)

    user_code = device_data["user_code"]
    verification_uri = device_data["verification_uri"]
    device_code = device_data["device_code"]
    expires_in = device_data["expires_in"]
    interval = device_data.get("interval", 5)

    logger.info("=" * 50)
    logger.info("Go to this URL in your browser:")
    logger.info(f"  {verification_uri}")
    logger.info(f"Enter this code: {user_code}")
    logger.info("=" * 50)
    logger.info(f"Waiting for authorization (expires in {expires_in} seconds)...")

    # Poll for token
    token_data = poll_for_token(client_id, scopes, device_code, interval, expires_in)

    logger.info("Authorization successful!")

    # Validate to get username
    validation = validate_token(token_data["access_token"])
    if validation:
        logger.info(f"Authenticated as: {validation.get('login')}")

    # Save token
    save_token(token_data)

    return token_data["access_token"]


def get_valid_token(client_id: str, client_secret: str = "", scopes: list[str] | None = None) -> str:
    """
    Get a valid access token, refreshing or re-authenticating if needed.

    This is the main function to use from other code.
    """
    existing = load_token()

    if existing:
        # Check if token is still valid
        validation = validate_token(existing.get("access_token", ""))
        if validation:
            return existing["access_token"]

        # Try to refresh
        if existing.get("refresh_token") and client_secret:
            try:
                logger.info("Access token expired, refreshing...")
                new_token = refresh_token(client_id, client_secret, existing["refresh_token"])
                save_token(new_token)
                logger.info("Token refresh successful")
                return new_token["access_token"]
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
        elif existing.get("refresh_token") and not client_secret:
            logger.warning("Have refresh_token but no client_secret - cannot refresh automatically")

    # Need full re-auth
    return authenticate(client_id, scopes)


if __name__ == "__main__":
    import os

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    if not client_id:
        logger.error("TWITCH_CLIENT_ID environment variable not set")
        logger.info("Run: source setenv.sh")
        exit(1)

    token = authenticate(client_id)
    logger.info(f"Your access token: {token}")
    logger.info("Add this to your setenv.sh:")
    logger.info(f"export TWITCH_OAUTH_TOKEN={token}")
