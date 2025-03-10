# Standup Discord Bot

A Discord bot that manages daily standup meetings in a dedicated channel, sending reminders and tracking responses.

## Features

- **Daily Reminders**: Automatic notifications at configurable times to remind team members about standups
- **Follow-up Reminders**: Mentions users who haven't submitted updates by the deadline
- **User Management**: Commands to add and remove users from the notification list
- **Flexible Configuration**: Customizable reminder times, deadlines, and timezone settings
- **Report Generation**: Generate daily and weekly summaries of all standups
- **Standup Templates**: Provides a customizable format for standup updates
- **Status Tracking**: Automatically tracks which team members have responded

## Requirements

- Python 3.8 or higher
- Discord Bot Token
- Discord server with permission to add bots and create threads
- (Optional) ntfy.sh for monitoring notifications

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/standup-discord-bot.git
cd standup-discord-bot
```

### 2. Create a Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (macOS/Linux)
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory with the following:

```
# Discord Bot Token
DISCORD_TOKEN=your_discord_bot_token_here

# Channel ID where standups will be posted
STANDUP_CHANNEL_ID=your_channel_id_here

# Guild/Server ID 
GUILD_ID=your_guild_id_here

# NTFY topic for monitoring (optional)
NTFY_TOPIC=your_ntfy_topic_here
```

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and add a bot
3. Enable the following intents:
   - Message Content Intent
   - Server Members Intent
   - Presence Intent
4. Generate an invite link with the following permissions:
   - Read Messages/View Channels
   - Send Messages
   - Manage Messages
   - Read Message History
5. Invite the bot to your server using the generated link
https://discord.com/oauth2/authorize?client_id=1347472081788342324&permissions=328565204992&scope=bot

## Starting the Bot

```bash
python standup-bot.py
```

## Docker Setup (Alternative)

You can also run the bot in Docker:

```bash
# Build the Docker image
docker build -t standup-bot .

# Run the container
docker run -d --name standup-bot \
  --env-file .env \
  --restart unless-stopped \
  standup-bot
```

## Usage

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/notify <username>` | Add a user to standup notification list | `/notify @JaneDoe` |
| `/remove <username>` | Remove a user from notification list | `/remove @JaneDoe` |
| `/list-users` | List all users on notification list | `/list-users` |
| `/daily-recap` | Generate report of today's standups | `/daily-recap` |
| `/weekly-recap` | Generate weekly summary report | `/weekly-recap` |
| `/set-reminder-time <time>` | Set daily reminder time (24h format) | `/set-reminder-time 10:30` |
| `/set-deadline <time>` | Set deadline and followup time | `/set-deadline 11:00` |
| `/set-timezone <tz>` | Set the timezone for the bot | `/set-timezone America/New_York` |
| `/set-standup-format <format>` | Set the standup template | `/set-standup-format **Yesterday:**\n- \n\n**Today:**\n- ` |
| `/test-reminder` | Test the reminder feature (admin) | `/test-reminder` |
| `/test-second-reminder` | Test the second reminder feature (admin) | `/test-second-reminder` |
| `/test-followup` | Test the followup feature (admin) | `/test-followup` |
| `/sync` | Sync slash commands with Discord (admin) | `/sync` |

### Workflow

1. **Initial Setup**:
   - Configure the bot with your desired timezone and times
   - Add team members to the notification list

2. **Daily Operation**:
   - Bot sends standup reminder at configured time (default: 9:30 AM) with template
   - Bot sends a second reminder at 10:15 AM to users who haven't responded yet
   - Team members post updates in the channel
   - Bot sends final followup at deadline time (default: 11:00 AM)

3. **Reporting**:
   - Generate daily or weekly recaps as needed

## Monitoring

The bot includes a monitoring script that ensures it's always running.
See [monitoring.md](monitoring.md) for setup instructions.

## Configuration

The bot stores configuration in JSON files:

- `db/config.json` - Bot settings (times, timezone, template)
- `db/users.json` - List of users to notify

Default settings:
- First reminder time: 9:30 AM local time (24-hour format)
- Second reminder time: 10:15 AM local time (fixed)
- Deadline time: 11:00 AM local time (24-hour format)
- Timezone: America/Los_Angeles
- Weekdays only: Yes

## Customizing the Standup Format

You can customize the standup template with the `/set-standup-format` command.

Default format:
```
**Yesterday:**
- 

**Today:**
- 

**Blockers:**
- None
```

## Troubleshooting

### Bot Doesn't Respond
- Verify that all required intents are enabled in the Discord Developer Portal
- Check that your bot has the necessary permissions in your server
- Ensure your `.env` file contains valid tokens and IDs

### Commands Not Working
- Make sure the bot is properly set up with application commands
- Wait a few minutes after bot startup for commands to register
- Check the bot logs for any errors

### Scheduling Issues
- Verify the timezone setting matches your team's timezone
- Remember that the bot uses 24-hour format for times

## Getting Channel and Guild IDs

To get the necessary IDs for the `.env` file:

1. **Enable Developer Mode in Discord**:
   - Open Discord
   - Go to User Settings > Advanced
   - Toggle on "Developer Mode"

2. **Get Guild/Server ID**:
   - Right-click on your server icon
   - Select "Copy ID"

3. **Get Channel ID**:
   - Right-click on the channel you want to use for standups
   - Select "Copy ID"

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes in each version.