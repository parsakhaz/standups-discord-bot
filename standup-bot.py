import os
import asyncio
import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import datetime
import json
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('StandupBot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
STANDUP_CHANNEL_ID = int(os.getenv('STANDUP_CHANNEL_ID'))
GUILD_ID = int(os.getenv('GUILD_ID'))

# Bot configuration with all intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global variables for configuration
CONFIG_FILE = 'db/config.json'
USER_FILE = 'db/users.json'

# Ensure our directories exist
os.makedirs('db', exist_ok=True)

# Load or create configuration
def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Default configuration
        config = {
            'reminder_time': '09:30',  # 9:30 AM in 24-hour format
            'deadline_time': '11:00',  # 11:00 AM in 24-hour format
            'timezone': 'America/Los_Angeles',
            'weekdays_only': True,
            'standup_format': "**Yesterday:**\n- \n\n**Today:**\n- \n\n**Blockers:**\n- "
        }
        save_config(config)
        return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Load or create user list
def load_users():
    try:
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Empty user list
        users = []
        save_users(users)
        return users

def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# Global variables
scheduler = AsyncIOScheduler()
config = load_config()
standup_users = load_users()
today_responses = {}  # Track responses for the day

@bot.event
async def on_ready():
    """When the bot starts up"""
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    setup_scheduler()
    logger.info("Bot is ready")

def setup_scheduler():
    # Clear existing jobs
    scheduler.remove_all_jobs()
    
    # Get timezone
    tz = pytz.timezone(config['timezone'])
    
    # Parse reminder and deadline times
    reminder_hour, reminder_minute = map(int, config['reminder_time'].split(':'))
    deadline_hour, deadline_minute = map(int, config['deadline_time'].split(':'))
    
    # Schedule initial reminder
    scheduler.add_job(
        send_standup_reminder,
        CronTrigger(hour=reminder_hour, minute=reminder_minute, day_of_week='mon-fri' if config['weekdays_only'] else '*', timezone=tz),
        id='standup_reminder',
        replace_existing=True
    )
    
    # Schedule second reminder at 10:15 AM
    scheduler.add_job(
        send_second_reminder,
        CronTrigger(hour=10, minute=15, day_of_week='mon-fri' if config['weekdays_only'] else '*', timezone=tz),
        id='second_reminder',
        replace_existing=True
    )
    
    # Schedule follow-up notification
    scheduler.add_job(
        send_followup_notification,
        CronTrigger(hour=deadline_hour, minute=deadline_minute, day_of_week='mon-fri' if config['weekdays_only'] else '*', timezone=tz),
        id='standup_followup',
        replace_existing=True
    )
    
    # Schedule daily reset at midnight
    scheduler.add_job(
        reset_daily_tracking,
        CronTrigger(hour=0, minute=0, timezone=tz),
        id='daily_reset',
        replace_existing=True
    )
    
    logger.info(f"Scheduled first reminder at {config['reminder_time']} AM, second reminder at 10:15 AM, and follow-ups at {config['deadline_time']} AM {config['timezone']}")

async def ensure_standup_channel():
    """Verify the standup channel exists and return it"""
    channel = bot.get_channel(STANDUP_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find channel with ID {STANDUP_CHANNEL_ID}")
    return channel

async def send_standup_reminder():
    """Send the standup reminder in the standups channel"""
    try:
        # Get the standup channel
        channel = await ensure_standup_channel()
        if not channel:
            return
            
        # Reset today's responses for the new day
        reset_daily_tracking()
        
        # Get guild to fetch members
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Could not find guild with ID {GUILD_ID}")
            return
            
        # Create mention string for all users
        mentions = []
        for user_id in standup_users:
            try:
                member = await guild.fetch_member(int(user_id))
                if member:
                    mentions.append(member.mention)
            except Exception as e:
                logger.error(f"Error fetching member {user_id}: {e}")
                
        mention_str = " ".join(mentions) if mentions else "everyone"
        
        # Create today's date string
        today_str = datetime.datetime.now().strftime("%m/%d/%Y")
        
        # Send reminder message in the channel
        await channel.send(f"📝 **Daily Standup for {today_str}**\n\n🔔 **Good morning {mention_str}!** Please fill in your standups before {config['deadline_time']} AM!\n\n**Standup Template:**\n\n{config['standup_format']}\n\n*Reply with your update starting with \"Standup:\"*")
        
        logger.info(f"Sent standup reminder to {len(mentions)} users")
        
    except Exception as e:
        logger.error(f"Error sending standup reminder: {e}")

async def send_followup_notification():
    """Send follow-up notification mentioning users who haven't responded"""
    try:
        # Get the standup channel
        channel = await ensure_standup_channel()
        if not channel:
            return
        
        # Get guild to fetch members
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Could not find guild with ID {GUILD_ID}")
            return
            
        # Get members who haven't responded
        missing_users = []
        for user_id in standup_users:
            if user_id not in today_responses:
                try:
                    member = await guild.fetch_member(int(user_id))
                    if member:
                        missing_users.append(member)
                except discord.NotFound:
                    logger.warning(f"User ID {user_id} not found in the server")
                except Exception as e:
                    logger.error(f"Error fetching member {user_id}: {e}")
        
        if missing_users:
            # Create mention string
            mentions = " ".join([member.mention for member in missing_users])
            
            # Send follow-up message
            await channel.send(f"⏰ **Reminder!** The following team members still need to submit their standups: {mentions}")
            logger.info(f"Sent follow-up notification to {len(missing_users)} users")
        else:
            await channel.send("✅ Great job team! Everyone has submitted their standup for today!")
            logger.info("All users have submitted their standups")
            
    except Exception as e:
        logger.error(f"Error sending follow-up notification: {e}")

async def send_second_reminder():
    """Send a second reminder to users who haven't responded yet"""
    try:
        # Get the standup channel
        channel = await ensure_standup_channel()
        if not channel:
            return
        
        # Get guild to fetch members
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Could not find guild with ID {GUILD_ID}")
            return
            
        # Get members who haven't responded
        missing_users = []
        for user_id in standup_users:
            if user_id not in today_responses:
                try:
                    member = await guild.fetch_member(int(user_id))
                    if member:
                        missing_users.append(member)
                except discord.NotFound:
                    logger.warning(f"User ID {user_id} not found in the server")
                except Exception as e:
                    logger.error(f"Error fetching member {user_id}: {e}")
        
        if missing_users:
            # Create mention string
            mentions = " ".join([member.mention for member in missing_users])
            
            # Send second reminder message
            await channel.send(f"⏰ **Second Reminder!** The following team members still need to submit their standups (due by 11:00 AM): {mentions}")
            logger.info(f"Sent second reminder to {len(missing_users)} users")
            
    except Exception as e:
        logger.error(f"Error sending second reminder: {e}")

def reset_daily_tracking():
    """Reset tracking of responses for a new day"""
    global today_responses
    today_responses = {}
    logger.info("Reset daily tracking of standup responses")

@bot.tree.command(name="notify", description="Add a user to the standup notification list")
async def notify_command(interaction: discord.Interaction, user: discord.Member):
    """Add a user to the standup notification list"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
        
    user_id = str(user.id)
    
    if user_id in standup_users:
        await interaction.response.send_message(f"{user.display_name} is already on the standup list.", ephemeral=True)
        return
    
    standup_users.append(user_id)
    save_users(standup_users)
    
    await interaction.response.send_message(f"Added {user.mention} to the standup notification list.", ephemeral=False)
    logger.info(f"Added user {user.display_name} ({user_id}) to standup list")

@bot.tree.command(name="remove", description="Remove a user from the standup notification list")
async def remove_command(interaction: discord.Interaction, user: discord.Member):
    """Remove a user from the standup notification list"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
        
    user_id = str(user.id)
    
    if user_id not in standup_users:
        await interaction.response.send_message(f"{user.display_name} is not on the standup list.", ephemeral=True)
        return
    
    standup_users.remove(user_id)
    save_users(standup_users)
    
    await interaction.response.send_message(f"Removed {user.mention} from the standup notification list.", ephemeral=False)
    logger.info(f"Removed user {user.display_name} ({user_id}) from standup list")

@bot.tree.command(name="list-users", description="List all users on the standup notification list")
async def list_users_command(interaction: discord.Interaction):
    """List all users on the standup notification list"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if not standup_users:
        await interaction.response.send_message("No users are currently on the standup notification list.", ephemeral=True)
        return
    
    guild = interaction.guild
    user_list = []
    
    for user_id in standup_users:
        try:
            member = await guild.fetch_member(int(user_id))
            if member:
                user_list.append(f"• {member.mention} ({member.display_name})")
        except:
            user_list.append(f"• Unknown User (ID: {user_id})")
    
    await interaction.response.send_message(f"**Standup Notification List:**\n" + "\n".join(user_list), ephemeral=False)

@bot.tree.command(name="set-reminder-time", description="Set the time for the daily standup reminder")
async def set_reminder_time_command(interaction: discord.Interaction, time: str):
    """Set the time for the daily standup reminder (format: HH:MM)"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Validate time format
    try:
        hour, minute = map(int, time.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Invalid time values")
    except:
        await interaction.response.send_message("Invalid time format. Please use HH:MM (24-hour format).", ephemeral=True)
        return
    
    # Update config
    config['reminder_time'] = time
    save_config(config)
    
    # Reconfigure scheduler
    setup_scheduler()
    
    await interaction.response.send_message(f"Standup reminder time set to {time} {config['timezone']}.", ephemeral=False)
    logger.info(f"Reminder time updated to {time}")

@bot.tree.command(name="set-deadline", description="Set the time for the follow-up standup notification")
async def set_deadline_command(interaction: discord.Interaction, time: str):
    """Set the time for the follow-up standup notification (format: HH:MM)"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Validate time format
    try:
        hour, minute = map(int, time.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Invalid time values")
    except:
        await interaction.response.send_message("Invalid time format. Please use HH:MM (24-hour format).", ephemeral=True)
        return
    
    # Update config
    config['deadline_time'] = time
    save_config(config)
    
    # Reconfigure scheduler
    setup_scheduler()
    
    await interaction.response.send_message(f"Standup deadline and follow-up time set to {time} {config['timezone']}.", ephemeral=False)
    logger.info(f"Deadline time updated to {time}")

@bot.tree.command(name="set-timezone", description="Set the timezone for the bot")
async def set_timezone_command(interaction: discord.Interaction, timezone: str):
    """Set the timezone for scheduling (e.g., America/Los_Angeles)"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Validate timezone
    try:
        pytz.timezone(timezone)
    except:
        await interaction.response.send_message("Invalid timezone. Please use a valid timezone identifier (e.g., America/Los_Angeles).", ephemeral=True)
        return
    
    # Update config
    config['timezone'] = timezone
    save_config(config)
    
    # Reconfigure scheduler
    setup_scheduler()
    
    await interaction.response.send_message(f"Timezone set to {timezone}.", ephemeral=False)
    logger.info(f"Timezone updated to {timezone}")

@bot.tree.command(name="daily-recap", description="Generate a report of today's standups")
async def daily_recap_command(interaction: discord.Interaction):
    """Generate a report of today's standups"""
    await interaction.response.defer(ephemeral=False)
    
    try:
        # Get the standup channel
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("Could not find the standup channel.")
            return
            
        # Get today's date
        today = datetime.datetime.now(pytz.timezone(config['timezone'])).date()
        today_start = datetime.datetime.combine(today, datetime.time.min, tzinfo=pytz.timezone(config['timezone']))
        today_end = datetime.datetime.combine(today, datetime.time.max, tzinfo=pytz.timezone(config['timezone']))
        
        # Get all messages from the standup channel for today
        messages = []
        async for message in channel.history(limit=200, after=today_start, before=today_end):
            if message.author != bot.user:  # Include all user messages, not just those with "Standup:" prefix
                messages.append(message)
        
        if not messages:
            await interaction.followup.send("No standup updates were found for today.")
            return
        
        # Build the recap
        today_str = today.strftime("%m/%d/%Y")
        recap = f"# Standup Recap for {today_str}\n\n"
        
        for message in reversed(messages):  # Oldest first
            # Format the user's message
            recap += f"## {message.author.display_name}\n"
            recap += f"{message.content}\n\n"
            
            # Add a separator
            recap += "---\n\n"
        
        # Send the recap
        if len(recap) > 2000:
            # Split into chunks if too long
            chunks = [recap[i:i+1990] for i in range(0, len(recap), 1990)]
            for i, chunk in enumerate(chunks):
                await interaction.followup.send(f"{chunk}\n\n*Part {i+1}/{len(chunks)}*")
        else:
            await interaction.followup.send(recap)
            
        logger.info(f"Generated daily recap with {len(messages)} updates")
        
    except Exception as e:
        await interaction.followup.send(f"Error generating recap: {str(e)}")
        logger.error(f"Error generating daily recap: {e}")

@bot.tree.command(name="weekly-recap", description="Generate a report of this week's standups")
async def weekly_recap_command(interaction: discord.Interaction):
    """Generate a report of this week's standups"""
    await interaction.response.defer(ephemeral=False)
    
    try:
        # Get standup channel
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("Could not find the standup channel.")
            return
        
        # Calculate date range for this week (Monday to today)
        current_tz = pytz.timezone(config['timezone'])
        today = datetime.datetime.now(current_tz)
        start_of_week = today - datetime.timedelta(days=today.weekday())
        start_of_week = datetime.datetime.combine(start_of_week.date(), datetime.time.min, tzinfo=current_tz)
        
        # Get all messages from the standup channel for this week
        messages_by_date = {}
        
        async for message in channel.history(limit=1000, after=start_of_week):
            if message.author != bot.user:  # Include all user messages, not just those with "Standup:" prefix
                msg_date = message.created_at.astimezone(current_tz)
                date_str = msg_date.strftime("%m/%d/%Y")
                
                if date_str not in messages_by_date:
                    messages_by_date[date_str] = []
                    
                messages_by_date[date_str].append(message)
        
        if not messages_by_date:
            await interaction.followup.send("No standup updates were found for this week.")
            return
        
        # Build the recap
        recap = "# Weekly Standup Recap\n\n"
        total_updates = 0
        
        # Process each day
        for date_str in sorted(messages_by_date.keys()):
            day_messages = messages_by_date[date_str]
            
            # Add day header
            recap += f"## {date_str} ({len(day_messages)} updates)\n\n"
            total_updates += len(day_messages)
            
            # Add each update
            for message in reversed(day_messages):  # Oldest first
                recap += f"### {message.author.display_name}\n"
                recap += f"{message.content}\n\n"
            
            # Add day separator
            recap += "---\n\n"
        
        # Add summary
        recap = f"# Weekly Standup Recap ({total_updates} total updates)\n\n" + recap[recap.find("\n\n")+2:]
        
        # Send the recap in chunks if needed
        if len(recap) > 2000:
            chunks = [recap[i:i+1990] for i in range(0, len(recap), 1990)]
            for i, chunk in enumerate(chunks):
                await interaction.followup.send(f"{chunk}\n\n*Part {i+1}/{len(chunks)}*")
        else:
            await interaction.followup.send(recap)
            
        logger.info(f"Generated weekly recap with {total_updates} updates")
        
    except Exception as e:
        await interaction.followup.send(f"Error generating weekly recap: {str(e)}")
        logger.error(f"Error generating weekly recap: {e}")

@bot.tree.command(name="set-standup-format", description="Set the standup format template")
async def set_standup_format_command(interaction: discord.Interaction, format: str):
    """Set the standup format template"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Update config
    config['standup_format'] = format
    save_config(config)
    
    await interaction.response.send_message(f"Standup format template updated!", ephemeral=False)
    logger.info(f"Standup format template updated")

@bot.tree.command(name="test-reminder", description="Test the standup reminder (admin only)")
async def test_reminder_command(interaction: discord.Interaction):
    """Test the standup reminder functionality"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
        return
    
    await interaction.response.send_message("Sending a test standup reminder...", ephemeral=True)
    
    try:
        await send_standup_reminder()
        logger.info("Test reminder sent successfully")
    except Exception as e:
        logger.error(f"Error sending test reminder: {e}")
        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="test-followup", description="Test the followup notification (admin only)")
async def test_followup_command(interaction: discord.Interaction):
    """Test the followup notification functionality"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
        return
    
    await interaction.response.send_message("Sending a test followup notification...", ephemeral=True)
    
    try:
        await send_followup_notification()
        logger.info("Test followup sent successfully")
    except Exception as e:
        logger.error(f"Error sending test followup: {e}")
        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="test-second-reminder", description="Test the second reminder notification (admin only)")
async def test_second_reminder_command(interaction: discord.Interaction):
    """Test the second reminder functionality"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
        return
    
    await interaction.response.send_message("Sending a test second reminder...", ephemeral=True)
    
    try:
        await send_second_reminder()
        logger.info("Test second reminder sent successfully")
    except Exception as e:
        logger.error(f"Error sending test second reminder: {e}")
        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="sync", description="Sync slash commands to the server (admin only)")
async def sync_command(interaction: discord.Interaction):
    """Sync slash commands with the server"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"Synced {len(synced)} command(s) successfully!", ephemeral=True)
        logger.info(f"Commands synced by {interaction.user.display_name}")
    except Exception as e:
        await interaction.followup.send(f"Failed to sync commands: {str(e)}", ephemeral=True)
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if message is in the standup channel (track all messages, not just those with "Standup:" prefix)
    if message.channel.id == STANDUP_CHANNEL_ID:
        # Mark this user as having responded
        today_responses[str(message.author.id)] = {
            'timestamp': datetime.datetime.now().timestamp(),
            'content': message.content
        }
        logger.info(f"Recorded standup update from {message.author.display_name}")
        
        # Add a reaction to acknowledge
        await message.add_reaction("✅")

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)