# /shoutout - Deep Streamer Shoutout

Give a streamer a personalized shoutout with full profile deep-dive.

## Usage

```
/shoutout <username>
```

## Instructions

When invoked with a username:

1. **Call `deep_shoutout(username)`** - This single MCP tool will:
   - Fetch their full profile (bio, broadcaster type, panels, view count)
   - Get channel info (current game, stream title)
   - Get their recent clips
   - Send a personalized chat message with the `«claude»` prefix
   - Show their clip on stream (auto-hides after 15 seconds)
   - Return ALL gathered data

2. **Summarize the streamer to the user** based on the returned data:
   - Mention their broadcaster status (Partner/Affiliate/regular user)
   - What games they stream
   - Interesting bits from their bio
   - Their panels (if any) - these often contain info about their setup, schedule, etc.
   - Recent clip titles and view counts
   - Account age and total channel views

3. **Keep it conversational** - Don't just dump data. Synthesize it into a natural summary like:
   > "Shouted out DarkRedDove! They're Harkin Dove (he/him), streams game adventures M/W/SA/SU at 9:30 PM EST. Bio says they do 'passionate howling' about games. Their top clip 'Peak Grandfather' has 500 views. Showing it on stream now!"

## Fuzzy Matching

If the username doesn't match exactly:
1. Call `twitch_get_recent_messages()` to get recent chat
2. Fuzzy match the provided name against recent chatters
3. Use the matched username for the shoutout

## Example

User: `/shoutout nahn`

Claude:
1. Checks recent chat, finds "nahnegnal"
2. Calls `deep_shoutout("nahnegnal")`
3. Reports back: "Shouted out nahnegnal! They're an affiliate who streams retro games..."
