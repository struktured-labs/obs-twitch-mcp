# OBS + Twitch MCP Server Configuration
# Copy this file to setenv.sh and fill in your credentials
# NEVER commit setenv.sh to git - it contains sensitive data!

# =============================================================================
# REQUIRED: Twitch API Credentials
# =============================================================================
# Get these from https://dev.twitch.tv/console/apps
export TWITCH_CLIENT_ID=your_client_id
export TWITCH_CLIENT_SECRET=your_client_secret
export TWITCH_CHANNEL=your_twitch_username

# OAuth token - run 'uv run python auth.py' to generate
# Leave empty initially, the auth script will fill it in
export TWITCH_OAUTH_TOKEN=

# =============================================================================
# REQUIRED: OBS WebSocket Connection
# =============================================================================
# Enable in OBS: Tools → WebSocket Server Settings
export OBS_WEBSOCKET_HOST=localhost
export OBS_WEBSOCKET_PORT=4455
export OBS_WEBSOCKET_PASSWORD=your_password

# =============================================================================
# OPTIONAL: Anthropic API (for game translation)
# =============================================================================
# Get from https://console.anthropic.com/
# Required for: translate_screenshot, translation_service_*
export ANTHROPIC_API_KEY=

# =============================================================================
# OPTIONAL: YouTube API (for video uploads)
# =============================================================================
# Get from Google Cloud Console:
# 1. Create project at https://console.cloud.google.com
# 2. Enable YouTube Data API v3
# 3. Create OAuth credentials (Desktop app)
# Required for: upload_video_to_youtube, get_my_youtube_videos
export YOUTUBE_CLIENT_ID=
export YOUTUBE_CLIENT_SECRET=

# =============================================================================
# OPTIONAL: Recording paths
# =============================================================================
# Default locations to scan for video files
# Used by: list_recordings, upload_recording
export OBS_RECORDING_PATH=~/Videos

# =============================================================================
# Notes
# =============================================================================
# - All OPTIONAL variables can be left empty if you don't need those features
# - Twitch token may expire; run 'uv run python auth.py' to refresh
# - First YouTube upload will open browser for OAuth authorization
# - Never share this file or commit it to version control
