@echo off
REM OBS + Twitch MCP Server Configuration (Windows)
REM Copy this file to setenv.bat and fill in your credentials
REM NEVER commit setenv.bat to git - it contains sensitive data!

REM =============================================================================
REM REQUIRED: Twitch API Credentials
REM =============================================================================
REM Get these from https://dev.twitch.tv/console/apps
set TWITCH_CLIENT_ID=your_client_id
set TWITCH_CLIENT_SECRET=your_client_secret
set TWITCH_CHANNEL=your_twitch_username

REM OAuth token - run 'uv run python auth.py' to generate
set TWITCH_OAUTH_TOKEN=

REM =============================================================================
REM REQUIRED: OBS WebSocket Connection
REM =============================================================================
REM Enable in OBS: Tools → WebSocket Server Settings
set OBS_WEBSOCKET_HOST=localhost
set OBS_WEBSOCKET_PORT=4455
set OBS_WEBSOCKET_PASSWORD=your_password

REM =============================================================================
REM OPTIONAL: Anthropic API (for game translation)
REM =============================================================================
REM Get from https://console.anthropic.com/
set ANTHROPIC_API_KEY=

REM =============================================================================
REM OPTIONAL: YouTube API (for video uploads)
REM =============================================================================
REM Get from Google Cloud Console
set YOUTUBE_CLIENT_ID=
set YOUTUBE_CLIENT_SECRET=

REM =============================================================================
REM OPTIONAL: Recording paths
REM =============================================================================
set OBS_RECORDING_PATH=%USERPROFILE%\Videos
