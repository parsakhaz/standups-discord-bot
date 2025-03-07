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
            'reminder_time': '10:30',
            'deadline_time': '11:00',
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
    
    logger.info(f"Scheduled reminders at {config['reminder_time']} and follow-ups at {config['deadline_time']} {config['timezone']}")

async def send_standup_reminder():
    """Send the initial standup reminder and create a thread"""
    try:
        # Get the channel
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {STANDUP_CHANNEL_ID}")
            return
        
        # Create today's date string
        today_str = datetime.datetime.now().strftime("%m/%d/%Y")
        
        # Send reminder message
        message = await channel.send(f"🔔 **Fill in your standups before {config['deadline_time']}!**")
        
        # Create thread for today's standups
        thread = await message.create_thread(name=f"{today_str} Standup")
        
        # Post template in thread
        await thread.send(f"**Standup Template:**\n\n{config['standup_format']}\n\n*Reply in this thread with your update!*")
        
        # Reset today's responses for the new day
        reset_daily_tracking()
        
        logger.info(f"Created standup thread for {today_str}")
        
    except Exception as e:
        logger.error(f"Error sending standup reminder: {e}")

async def send_followup_notification():
    """Send follow-up notification mentioning users who haven't responded"""
    try:
        # Get the channel
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {STANDUP_CHANNEL_ID}")
            return
        
        # Get today's thread
        today_str = datetime.datetime.now().strftime("%m/%d/%Y")
        thread = None
        
        # Find the thread for today
        async for thread_channel in channel.archived_threads(limit=5):
            if today_str in thread_channel.name:
                thread = thread_channel
                break
                
        if not thread:
            # Check active threads
            for thread_channel in channel.threads:
                if today_str in thread_channel.name:
                    thread = thread_channel
                    break
        
        if not thread:
            logger.error(f"Could not find today's thread")
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
            await thread.send(f"⏰ **Reminder!** The following team members still need to submit their standups: {mentions}")
            logger.info(f"Sent follow-up notification to {len(missing_users)} users")
        else:
            await thread.send("✅ Great job team! Everyone has submitted their standup for today!")
            logger.info("All users have submitted their standups")
            
    except Exception as e:
        logger.error(f"Error sending follow-up notification: {e}")

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
        # Get today's thread
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("Could not find the standup channel.")
            return
            
        today_str = datetime.datetime.now().strftime("%m/%d/%Y")
        thread = None
        
        # Find the thread for today
        async for thread_channel in channel.archived_threads(limit=5):
            if today_str in thread_channel.name:
                thread = thread_channel
                break
                
        if not thread:
            # Check active threads
            for thread_channel in channel.threads:
                if today_str in thread_channel.name:
                    thread = thread_channel
                    break
        
        if not thread:
            await interaction.followup.send("Could not find today's standup thread.")
            return
        
        # Get all messages from the thread
        messages = []
        async for message in thread.history(limit=100):
            if message.author != bot.user and not message.content.startswith("**Standup Template:**"):
                messages.append(message)
        
        if not messages:
            await interaction.followup.send("No standup updates were found for today.")
            return
        
        # Build the recap
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
        today = datetime.datetime.now()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        date_range = []
        
        # Generate all dates this week up to today
        current_date = start_of_week
        while current_date <= today:
            date_range.append(current_date.strftime("%m/%d/%Y"))
            current_date += datetime.timedelta(days=1)
        
        # Initialize recap
        recap = "# Weekly Standup Recap\n\n"
        total_updates = 0
        
        # Process each day
        for date_str in date_range:
            thread = None
            
            # Find the thread for this date
            async for thread_channel in channel.archived_threads(limit=20):
                if date_str in thread_channel.name:
                    thread = thread_channel
                    break
                    
            if not thread:
                # Check active threads
                for thread_channel in channel.threads:
                    if date_str in thread_channel.name:
                        thread = thread_channel
                        break
            
            if not thread:
                recap += f"## {date_str}\nNo standups found for this day.\n\n"
                continue
            
            # Get messages for this day
            day_messages = []
            async for message in thread.history(limit=100):
                if message.author != bot.user and not message.content.startswith("**Standup Template:**"):
                    day_messages.append(message)
            
            if not day_messages:
                recap += f"## {date_str}\nNo standup updates were submitted.\n\n"
                continue
            
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

@bot.tree.command(name="test", description="Run a complete test of the bot's functionality")
async def test_command(interaction: discord.Interaction):
    """Run a complete test of the bot's functionality and display debug information"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=False)
    
    try:
        # Create an embed for the debug information
        embed = discord.Embed(
            title="🔍 Standup Bot Diagnostic Information",
            description="A complete overview of the bot's current configuration and status",
            color=discord.Color.blue()
        )
        
        # Bot version and server info
        embed.add_field(
            name="🤖 Bot Information",
            value=f"**Guild ID:** {GUILD_ID}\n"
                  f"**Standup Channel ID:** {STANDUP_CHANNEL_ID}\n"
                  f"**Discord.py Version:** {discord.__version__}\n"
                  f"**Python Version:** {sys.version.split()[0]}",
            inline=False
        )
        
        # Configuration settings
        embed.add_field(
            name="⚙️ Configuration",
            value=f"**Reminder Time:** {config['reminder_time']}\n"
                  f"**Deadline Time:** {config['deadline_time']}\n"
                  f"**Timezone:** {config['timezone']}\n"
                  f"**Weekdays Only:** {'Yes' if config['weekdays_only'] else 'No'}",
            inline=False
        )
        
        # Next scheduled events
        now = datetime.datetime.now(pytz.timezone(config['timezone']))
        next_reminder = scheduler.get_job('standup_reminder').next_run_time
        next_followup = scheduler.get_job('standup_followup').next_run_time
        next_reset = scheduler.get_job('daily_reset').next_run_time
        
        embed.add_field(
            name="📅 Scheduled Events",
            value=f"**Current Time:** {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                  f"**Next Reminder:** {next_reminder.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                  f"**Next Followup:** {next_followup.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                  f"**Next Daily Reset:** {next_reset.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            inline=False
        )
        
        # User information
        users_str = ""
        if standup_users:
            guild = bot.get_guild(GUILD_ID)
            for i, user_id in enumerate(standup_users, 1):
                user = guild.get_member(int(user_id))
                user_name = user.display_name if user else f"Unknown User ({user_id})"
                users_str += f"{i}. {user_name} - ID: {user_id}\n"
        else:
            users_str = "No users currently on the standup list."
        
        embed.add_field(
            name="👥 Standup Users",
            value=users_str,
            inline=False
        )
        
        # Response tracking for today
        responses_str = ""
        if today_responses:
            guild = bot.get_guild(GUILD_ID)
            for user_id, submitted in today_responses.items():
                user = guild.get_member(int(user_id))
                user_name = user.display_name if user else f"Unknown User ({user_id})"
                status = "✅ Submitted" if submitted else "❌ Not Submitted"
                responses_str += f"{user_name}: {status}\n"
        else:
            responses_str = "No responses tracked for today."
        
        embed.add_field(
            name="📊 Today's Responses",
            value=responses_str,
            inline=False
        )
        
        # Standup format template
        embed.add_field(
            name="📝 Standup Format",
            value=f"```\n{config['standup_format']}\n```",
            inline=False
        )
        
        # Bot permissions check
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        channel_exists = "✅" if channel else "❌"
        can_send = "✅" if channel and channel.permissions_for(interaction.guild.me).send_messages else "❌"
        can_create_threads = "✅" if channel and channel.permissions_for(interaction.guild.me).create_public_threads else "❌"
        can_mention = "✅" if channel and channel.permissions_for(interaction.guild.me).mention_everyone else "❌"
        
        embed.add_field(
            name="🔐 Permission Check",
            value=f"**Channel Exists:** {channel_exists}\n"
                  f"**Can Send Messages:** {can_send}\n"
                  f"**Can Create Threads:** {can_create_threads}\n"
                  f"**Can Mention Users:** {can_mention}",
            inline=False
        )
        
        # Add timestamp
        embed.set_footer(text=f"Generated at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        await interaction.followup.send(embed=embed)
        
        # Send a message to test basic functionality
        channel = bot.get_channel(STANDUP_CHANNEL_ID)
        if channel:
            test_message = await channel.send("🔍 **Bot Test Message**\nThis message was generated from a diagnostic test and will be deleted in a few seconds.")
            await asyncio.sleep(5)
            await test_message.delete()
        
        logger.info(f"Diagnostic test completed by {interaction.user.display_name}")
    except Exception as e:
        logger.error(f"Error during diagnostic test: {e}")
        await interaction.followup.send(f"Error during test: {str(e)}")

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if message is in a standup thread
    if isinstance(message.channel, discord.Thread):
        today_str = datetime.datetime.now().strftime("%m/%d/%Y")
        if today_str in message.channel.name and message.channel.parent_id == STANDUP_CHANNEL_ID:
            # Mark this user as having responded
            today_responses[str(message.author.id)] = {
                'timestamp': datetime.datetime.now().timestamp(),
                'content': message.content
            }
            logger.info(f"Recorded standup update from {message.author.display_name}")
            
            # Add a reaction to acknowledge
            await message.add_reaction("✅")

@bot.tree.command(name="sync", description="Sync slash commands to the server (admin only)")
async def sync_command(interaction: discord.Interaction):
    """Sync slash commands with Discord"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"Synced {len(synced)} command(s) successfully!", ephemeral=True)
        logger.info(f"Commands synced by {interaction.user.display_name}")
    except Exception as e:
        await interaction.followup.send(f"Failed to sync commands: {str(e)}", ephemeral=True)
        logger.error(f"Failed to sync commands: {e}")

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)