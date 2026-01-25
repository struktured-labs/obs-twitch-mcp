---
layout: default
title: Getting Started
---

# Getting Started

This guide walks you through setting up OBS + Twitch MCP Server from scratch. No programming experience required - if you can copy-paste commands and edit a text file, you're good.

**Time needed:** About 15-20 minutes

---

## What You'll Need

Before starting, make sure you have:

- [ ] **OBS Studio** installed ([obsproject.com](https://obsproject.com))
- [ ] A **Twitch account** (for API access)
- [ ] **Python 3.11 or newer** ([python.org](https://python.org) or your package manager)
- [ ] **Claude Code** or another MCP client ([claude.ai/claude-code](https://claude.ai/claude-code))

---

## Step 1: Install uv (Python Package Manager)

`uv` is a fast Python package manager. It's like npm for Python.

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installing, restart your terminal.

---

## Step 2: Clone the Repository

```bash
# Clone the repo
git clone https://github.com/struktured-labs/obs-twitch-mcp.git

# Enter the directory
cd obs-twitch-mcp

# Install dependencies (this may take a minute)
uv sync

# Install browser automation (needed for some features)
uv run playwright install chromium
```

---

## Step 3: Enable OBS WebSocket

The MCP server talks to OBS through WebSocket. You need to enable it:

1. Open **OBS Studio**
2. Go to **Tools → WebSocket Server Settings**
3. Check **Enable WebSocket server**
4. Set a password (remember it!)
5. Note the port (usually **4455**)
6. Click **OK**

---

## Step 4: Create a Twitch Developer App

You need API credentials to control Twitch:

1. Go to [dev.twitch.tv/console/apps](https://dev.twitch.tv/console/apps)
2. Log in with your Twitch account
3. Click **Register Your Application**
4. Fill in:
   - **Name:** Something like "My Stream Controller"
   - **OAuth Redirect URLs:** `http://localhost:17563`
   - **Category:** Chat Bot
5. Click **Create**
6. Click **Manage** on your new app
7. Copy your **Client ID**
8. Click **New Secret** and copy your **Client Secret**

---

## Step 5: Set Up Credentials

```bash
# Copy the example config
cp setenv.example.sh setenv.sh

# Open it in a text editor
nano setenv.sh  # or: code setenv.sh, notepad setenv.sh, etc.
```

Fill in your values:

```bash
# Twitch credentials (from Step 4)
export TWITCH_CLIENT_ID="your_client_id_here"
export TWITCH_CLIENT_SECRET="your_client_secret_here"
export TWITCH_CHANNEL="your_twitch_username"

# OBS credentials (from Step 3)
export OBS_WEBSOCKET_PASSWORD="your_obs_password"
export OBS_WEBSOCKET_PORT="4455"

# Leave TWITCH_OAUTH_TOKEN empty for now - we'll generate it
export TWITCH_OAUTH_TOKEN=""
```

Save and close the file.

---

## Step 6: Generate Twitch OAuth Token

Now run the authentication script:

```bash
# Load your credentials
source setenv.sh

# Run the auth script
uv run python auth.py
```

This will:
1. Open your browser
2. Ask you to log in to Twitch
3. Ask you to authorize the app
4. Save your token automatically

After it's done, your `setenv.sh` will have the `TWITCH_OAUTH_TOKEN` filled in.

---

## Step 7: Configure Claude Code

Add the MCP server to Claude Code's config. Edit `~/.claude/settings.json`:

**Linux/macOS:**
```json
{
  "mcpServers": {
    "obs-twitch": {
      "command": "bash",
      "args": [
        "-c",
        "source /full/path/to/obs-twitch-mcp/setenv.sh && uv run --directory /full/path/to/obs-twitch-mcp python -m src.server"
      ]
    }
  }
}
```

**Windows:**

First, create `setenv.bat` in the obs-twitch-mcp folder:
```batch
@echo off
set TWITCH_CLIENT_ID=your_client_id
set TWITCH_CLIENT_SECRET=your_client_secret
set TWITCH_OAUTH_TOKEN=oauth:your_token
set TWITCH_CHANNEL=your_channel
set OBS_WEBSOCKET_PASSWORD=your_password
set OBS_WEBSOCKET_PORT=4455
```

Then in `settings.json`:
```json
{
  "mcpServers": {
    "obs-twitch": {
      "command": "cmd",
      "args": ["/c", "setenv.bat && uv run python -m src.server"],
      "cwd": "C:\\full\\path\\to\\obs-twitch-mcp"
    }
  }
}
```

**Important:** Replace `/full/path/to/obs-twitch-mcp` with the actual path where you cloned the repo!

---

## Step 8: Test It!

1. Make sure **OBS is running**
2. Start Claude Code:
   ```bash
   claude
   ```
3. Try these commands:
   - "List my OBS scenes"
   - "What scene am I on?"
   - "Switch to [scene name]"

If you see your scenes listed, everything is working!

---

## Troubleshooting

### "Connection refused" or can't connect to OBS

- Make sure OBS is running
- Check WebSocket is enabled (Tools → WebSocket Server Settings)
- Verify the port matches (usually 4455)
- Check the password is correct

### "Unauthorized" or Twitch errors

- Your token may have expired
- Run `uv run python auth.py` again
- Make sure `TWITCH_CHANNEL` is your username (lowercase)

### MCP server not found

- Restart Claude Code after editing settings.json
- Check the path in settings.json is correct
- Try running manually: `source setenv.sh && uv run python -m src.server`

### "Module not found" errors

```bash
# Make sure you're in the right directory
cd /path/to/obs-twitch-mcp

# Reinstall dependencies
uv sync
```

---

## Next Steps

Now that you're set up:

- **[Translation Guide](translation.md)** - Set up real-time Japanese game translation
- **[Automation Guide](automation.md)** - Auto-welcome viewers, scheduled messages
- **[Tool Reference](tool-reference.md)** - See all 118 available tools

---

## Optional: Translation Setup

If you want to use the translation features, you'll also need:

1. **Anthropic API Key** from [console.anthropic.com](https://console.anthropic.com)
2. Add to your `setenv.sh`:
   ```bash
   export ANTHROPIC_API_KEY="your_api_key_here"
   ```

See the [Translation Guide](translation.md) for full setup.

---

## Optional: YouTube Upload Setup

For uploading directly to YouTube:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project
3. Enable YouTube Data API v3
4. Create OAuth credentials
5. Add to `setenv.sh`:
   ```bash
   export YOUTUBE_CLIENT_ID="your_client_id"
   export YOUTUBE_CLIENT_SECRET="your_client_secret"
   ```

The first upload will open a browser for authorization.
