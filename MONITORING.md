# Standup Bot Monitoring Setup Guide

This guide outlines how to set up a lightweight monitoring system for the Standup Discord Bot with notifications via ntfy.sh.

## Overview

The monitoring script:
- Checks every 15 seconds if the bot is running
- Automatically restarts the bot if it crashes
- Sends notifications via ntfy.sh when issues occur
- Logs restart events to a file
- Uses minimal system resources

## Setup Instructions

### 1. Configure the Monitoring

First, set your ntfy.sh topic in your environment:

```bash
export NTFY_TOPIC="your-standup-bot-topic"
```

Or edit the `monitor.sh` script directly to change the default topic.

### 2. Make the Script Executable

```bash
chmod +x monitor.sh
```

### 3. Set Up Notifications

1. Install the ntfy app on your device:
   - Android: [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - iOS: [App Store](https://apps.apple.com/us/app/ntfy/id1625396347)
   - Or use the web interface at [ntfy.sh](https://ntfy.sh/)

2. Subscribe to your chosen topic in the app (the same one you set in step 1)

### 4. Start the Monitoring Script

To run the script in the background and keep it running after you disconnect:

```bash
nohup ./monitor.sh > /dev/null 2>&1 &
```

### 5. Check That Monitoring Is Active

```bash
ps aux | grep monitor.sh
```

You should see the script running.

### 6. Verify Notification Setup

Test that notifications are working by temporarily stopping the bot:

```bash
pkill -f "python standup-bot.py"
```

You should receive a notification within 15 seconds, and another notification when the bot restarts.

### 7. Monitor Logs

View restart logs with:

```bash
cat monitor_restart.log
```

## Systemd Service Setup (Recommended)

For more reliable monitoring on Linux systems, create a systemd service:

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/standup-bot.service
```

2. Add the following content:

```ini
[Unit]
Description=Standup Discord Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/standup-bot
ExecStart=/usr/bin/python3 standup-bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Create a monitor service:

```bash
sudo nano /etc/systemd/system/standup-bot-monitor.service
```

4. Add the following content:

```ini
[Unit]
Description=Standup Discord Bot Monitor
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/standup-bot
ExecStart=/bin/bash monitor.sh
Restart=always
RestartSec=10
Environment="NTFY_TOPIC=standup-bot-alerts"

[Install]
WantedBy=multi-user.target
```

5. Enable and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable standup-bot.service
sudo systemctl enable standup-bot-monitor.service
sudo systemctl start standup-bot.service
sudo systemctl start standup-bot-monitor.service
```

6. Check status:

```bash
sudo systemctl status standup-bot.service
sudo systemctl status standup-bot-monitor.service
```

## Troubleshooting

- If the script isn't detecting the bot, check that the bot process name matches exactly "python standup-bot.py"
- Make sure curl is installed: `apt-get install curl` (on Ubuntu/Debian)
- Ensure the server has internet access to reach ntfy.sh
- Check that the monitor script and standup-bot.py are in the same directory
- Verify that Discord token and other environment variables are correctly set

## Additional Notes

- The script logs only when restarts happen, to conserve disk space
- Notifications include failure count to help identify recurring issues
- To stop monitoring: `pkill -f "monitor.sh"`

## Monitoring the Monitor

For extra reliability, you can set up a secondary monitoring system to ensure your primary monitor is running:

```bash
sudo nano /etc/systemd/system/monitor-health-check.service
```

```ini
[Unit]
Description=Monitor Health Check Service
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash -c 'while true; do if ! systemctl is-active --quiet standup-bot-monitor; then curl -H "Title: CRITICAL: Monitor Down" -H "Priority: urgent" -H "Tags: error,monitor,critical" -d "The bot monitoring service itself is down! System needs immediate attention." https://ntfy.sh/standup-bot-alerts; fi; sleep 60; done'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

This creates a second service that checks if your monitoring service is running and sends notifications if it stops.