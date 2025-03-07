#!/bin/bash

# Simple script to monitor standup-bot.py and restart if not running
# Sends notifications via ntfy.sh when bot is down

# Set your ntfy.sh topic from environment or use default
NTFY_TOPIC="${NTFY_TOPIC:md-standup-bot-alerts}"

# Initialize counter for consecutive failures
failures=0

while true; do
  if ! pgrep -f "python standup-bot.py" > /dev/null; then
    # Increment failure counter
    ((failures++))
    
    # Log restart attempt
    echo "[$(date)] Bot not running (failure #$failures). Attempting restart..." >> monitor_restart.log
    
    # Restart the bot
    cd "$(dirname "$0")" # Change to script directory
    python standup-bot.py &      # Start bot in background
    
    # Send notification via ntfy.sh
    curl -H "Title: Standup Bot Down Alert" \
         -H "Priority: high" \
         -H "Tags: warning,bot,restart" \
         -d "Standup Bot is down! Attempting restart #$failures at $(date). Check server." \
         https://ntfy.sh/$NTFY_TOPIC
    
    sleep 5  # Wait to ensure bot started properly
    
    # Check if restart was successful
    if ! pgrep -f "python standup-bot.py" > /dev/null; then
      # Send critical notification if restart failed
      curl -H "Title: CRITICAL: Standup Bot Restart Failed" \
           -H "Priority: urgent" \
           -H "Tags: error,bot,critical" \
           -d "Failed to restart Standup Bot after attempt #$failures. Immediate attention required!" \
           https://ntfy.sh/$NTFY_TOPIC
    else
      # Send recovery notification
      curl -H "Title: Standup Bot Recovered" \
           -H "Priority: default" \
           -H "Tags: success,bot,recovery" \
           -d "Standup Bot successfully restarted after being down (attempt #$failures)." \
           https://ntfy.sh/$NTFY_TOPIC
      
      # Reset failure counter on successful restart
      failures=0
    fi
  fi
  sleep 15  # Check every 15 seconds
done