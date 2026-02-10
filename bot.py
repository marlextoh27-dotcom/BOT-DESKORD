import discord
from discord.ext import commands
import asyncio
import os
import json
import re
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = ('MTQxMzE5ODQ3MjMwNzI3Nzg3NA.GezhGz.N5fHFbX-KjMW-gjJLLNm_p67klHHT5t3IEIAK0')
# Legacy single-channel support (for backward compatibility)
SOURCE_CHANNEL_ID = int(os.getenv('SOURCE_CHANNEL_ID', '0'))
DESTINATION_CHANNEL_ID = int(os.getenv('DESTINATION_CHANNEL_ID', '0'))

def update_env_file(key, value):
    """Update or add a key-value pair in the .env file"""
    env_file_path = '.env'
    
    # Read existing .env file
    env_vars = {}
    if os.path.exists(env_file_path):
        with open(env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_vars[k.strip()] = v.strip()
    
    # Update the value
    env_vars[key] = str(value)
    
    # Write back to .env file
    with open(env_file_path, 'w') as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

def reload_config():
    """Reload configuration from .env file"""
    global SOURCE_CHANNEL_ID, DESTINATION_CHANNEL_ID
    load_dotenv(override=True)
    SOURCE_CHANNEL_ID = int(os.getenv('SOURCE_CHANNEL_ID', '0'))
    DESTINATION_CHANNEL_ID = int(os.getenv('DESTINATION_CHANNEL_ID', '0'))

# Filter configuration
FILTER_FILE = 'filter_words.json'

# Channel pairs configuration
CHANNEL_PAIRS_FILE = 'channel_pairs.json'

# Message deduplication - keep track of recently processed messages
processed_messages = {}  # message_id: timestamp
MESSAGE_CACHE_DURATION = 300  # 5 minutes cache

def load_filters():
    """Load filter words from JSON file"""
    try:
        with open(FILTER_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_filters(filters):
    """Save filter words to JSON file"""
    with open(FILTER_FILE, 'w') as f:
        json.dump(filters, f, indent=2)

def load_channel_pairs():
    """Load channel pairs from JSON file"""
    try:
        with open(CHANNEL_PAIRS_FILE, 'r') as f:
            pairs = json.load(f)
            return pairs
    except (FileNotFoundError, json.JSONDecodeError):
        # If no pairs file exists, check legacy environment variables
        if SOURCE_CHANNEL_ID != 0 and DESTINATION_CHANNEL_ID != 0:
            return [{"source": SOURCE_CHANNEL_ID, "destination": DESTINATION_CHANNEL_ID, "name": "Legacy Pair"}]
        return []

def save_channel_pairs(pairs):
    """Save channel pairs to JSON file"""
    with open(CHANNEL_PAIRS_FILE, 'w') as f:
        json.dump(pairs, f, indent=2)

def add_channel_pair(source_id, destination_id, name=None):
    """Add a new channel pair"""
    pairs = load_channel_pairs()
    
    # Check if this exact pair already exists
    for pair in pairs:
        if pair['source'] == source_id and pair['destination'] == destination_id:
            return False, "This source-destination pair already exists"
    
    # Generate name if not provided
    if not name:
        name = f"Pair {len(pairs) + 1}"
    
    new_pair = {
        "source": source_id,
        "destination": destination_id,
        "name": name
    }
    
    pairs.append(new_pair)
    save_channel_pairs(pairs)
    return True, f"Added channel pair: {name}"

def remove_channel_pair(source_id, destination_id):
    """Remove a channel pair"""
    pairs = load_channel_pairs()
    
    for i, pair in enumerate(pairs):
        if pair['source'] == source_id and pair['destination'] == destination_id:
            removed_pair = pairs.pop(i)
            save_channel_pairs(pairs)
            return True, f"Removed channel pair: {removed_pair['name']}"
    
    return False, "Channel pair not found"

def get_destination_channels(source_channel_id):
    """Get all destination channels for a given source channel"""
    pairs = load_channel_pairs()
    destinations = []
    
    for pair in pairs:
        if pair['source'] == source_channel_id:
            destinations.append(pair['destination'])
    
    return destinations

def strip_discord_links(text):
    """Remove discord.gg links and timestamps from message content"""
    if not text:
        return text
    
    # Remove discord.gg links with optional additional text after them
    text = re.sub(r'discord\.gg/\S+(?:\s*\|\s*[^\n]*)?', '', text, flags=re.IGNORECASE)
    
    # Remove standalone discord invites like "discord.gg/abc123"
    text = re.sub(r'https?://discord\.gg/\S+', '', text, flags=re.IGNORECASE)
    
    # Clean up extra whitespace and newlines
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text)  # Multiple newlines to double
    text = re.sub(r'^\s+|\s+$', '', text)  # Trim start/end whitespace
    
    return text

def should_forward_message(message_content, filters):
    """Check if message should be forwarded (doesn't contain blocked words)"""
    if not filters or not message_content:
        return True  # If no filters set, forward everything
    
    message_lower = message_content.lower()
    for filter_word in filters:
        if filter_word.lower() in message_lower:
            return False  # Block message if it contains a filtered word
    return True  # Forward message if it doesn't contain any filtered words

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Show which guilds the bot is in
    for guild in bot.guilds:
        print(f"  - {guild.name} (ID: {guild.id})")
    
    # Validate configuration
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN not found in environment variables")
        return
    
    if SOURCE_CHANNEL_ID == 0:
        print("❌ WARNING: SOURCE_CHANNEL_ID not configured")
    else:
        source_channel = bot.get_channel(SOURCE_CHANNEL_ID)
        if source_channel:
            if isinstance(source_channel, discord.TextChannel):
                print(f"✅ Source channel found: #{source_channel.name} in {source_channel.guild.name}")
            else:
                print(f"✅ Source channel found (private channel)")
        else:
            print(f"❌ WARNING: Could not find source channel with ID {SOURCE_CHANNEL_ID}")
            print("   This usually means:")
            print("   1. The bot is not in the server containing this channel")
            print("   2. The bot doesn't have permission to see this channel")
            print("   3. The channel ID is incorrect")
            print("   Use '!debug' command in a server to see available channels")
    
    if DESTINATION_CHANNEL_ID == 0:
        print("❌ WARNING: DESTINATION_CHANNEL_ID not configured")
    else:
        destination_channel = bot.get_channel(DESTINATION_CHANNEL_ID)
        if destination_channel:
            if isinstance(destination_channel, discord.TextChannel):
                print(f"✅ Destination channel found: #{destination_channel.name} in {destination_channel.guild.name}")
            else:
                print(f"✅ Destination channel found (private channel)")
        else:
            print(f"❌ WARNING: Could not find destination channel with ID {DESTINATION_CHANNEL_ID}")
            print("   Use '!debug' command in a server to see available channels")
    
    # Show filter status
    filters = load_filters()
    if filters:
        print(f"✅ Message filters configured: {len(filters)} blocked word(s)")
        for i, filter_word in enumerate(filters[:3], 1):
            print(f"   {i}. '{filter_word}' (BLOCKED)")
        if len(filters) > 3:
            print(f"   ... and {len(filters) - 3} more")
    else:
        print("⚠️  No message filters configured (all messages will be forwarded)")

def cleanup_message_cache():
    """Remove old message IDs from cache"""
    current_time = time.time()
    expired_messages = [msg_id for msg_id, timestamp in processed_messages.items() 
                       if current_time - timestamp > MESSAGE_CACHE_DURATION]
    for msg_id in expired_messages:
        del processed_messages[msg_id]

@bot.event
async def on_message(message):
    # Allow webhook messages and users, but block regular bots (except our own bot for commands)
    is_webhook = hasattr(message, 'webhook_id') or (message.author.bot and message.author.discriminator == '0000')
    is_our_bot = message.author.id == bot.user.id
    
    if message.author.bot and not is_webhook and not is_our_bot:
        # Block regular bots but allow webhooks and our own bot
        return
    
    # Check if this message is from any configured source channels
    destination_channels = get_destination_channels(message.channel.id)
    
    if destination_channels:
        # Don't forward our own messages to avoid loops
        if message.author.id == bot.user.id:
            return
        
        # Clean up old cache entries
        cleanup_message_cache()
        
        # Check if we've already processed this message recently
        current_time = time.time()
        if message.id in processed_messages:
            # Skip if we processed this message recently
            time_diff = current_time - processed_messages[message.id]
            print(f"⏭️ Skipping duplicate message from {message.author.display_name} (processed {time_diff:.1f}s ago)")
            return
        
        # Mark this message as processed
        processed_messages[message.id] = current_time
        
        # Log what type of message we're processing
        if is_webhook:
            print(f"📡 Processing webhook message from {message.author.display_name} (ID: {message.id})")
        else:
            print(f"👤 Processing user message from {message.author.display_name} (ID: {message.id})")
            
        filters = load_filters()
        if should_forward_message(message.content, filters):
            # Forward to all destination channels for this source
            for dest_channel_id in destination_channels:
                await forward_message_to_channel(message, dest_channel_id)
        else:
            print(f"🚫 Message from {message.author} contains blocked word, filtering out...")
    
    # Process commands
    await bot.process_commands(message)

def extract_embed_text(embed):
    """Convert embed content to readable plain text"""
    text_parts = []
    
    # Add title
    if embed.title:
        text_parts.append(f"**{embed.title}**")
    
    # Add description
    if embed.description:
        clean_desc = strip_discord_links(embed.description)
        if clean_desc.strip():
            text_parts.append(clean_desc)
    
    # Add fields
    for field in embed.fields:
        field_text = f"**{field.name}**"
        clean_value = strip_discord_links(field.value)
        if clean_value.strip():
            field_text += f"\n{clean_value}"
            text_parts.append(field_text)
    
    # Add footer (if not a discord link)
    if embed.footer and embed.footer.text:
        footer_text = embed.footer.text
        if not re.search(r'discord\.gg/', footer_text, re.IGNORECASE):
            text_parts.append(f"*{footer_text}*")
    
    return "\n\n".join(text_parts)

async def forward_message_to_channel(message, destination_channel_id):
    """Forward a message to a specific destination channel as plain text"""
    try:
        destination_channel = bot.get_channel(destination_channel_id)
        if not destination_channel:
            print(f"❌ Error: Could not find destination channel with ID {destination_channel_id}")
            return
        
        # Build the message content parts
        content_parts = []
        
        # Add author info at the start
        author_header = f"**{message.author.display_name}:**"
        
        # Handle regular message content
        if message.content:
            clean_content = strip_discord_links(message.content)
            if clean_content.strip():
                content_parts.append(f"{author_header} {clean_content}")
            else:
                content_parts.append(author_header)  # Just add author name if content was all discord links
        
        # Extract text from embeds and add as plain text
        if message.embeds:
            # If we haven't added author header yet, add it now
            if not content_parts:
                content_parts.append(author_header)
            
            for embed in message.embeds:
                embed_text = extract_embed_text(embed)
                if embed_text.strip():
                    content_parts.append(embed_text)
        
        # Handle attachments as text descriptions
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    content_parts.append(f"📷 **Image:** {attachment.filename}")
                else:
                    content_parts.append(f"📎 **File:** {attachment.filename}")
        
        # Combine all content
        final_text = "\n\n".join(content_parts) if content_parts else None
        
        # Send as simple text message
        if final_text and final_text.strip():
            # Split long messages to avoid Discord's 2000 character limit
            if len(final_text) > 1900:
                chunks = [final_text[i:i+1900] for i in range(0, len(final_text), 1900)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await destination_channel.send(chunk)
                    else:
                        await destination_channel.send(f"...continued:\n{chunk}")
            else:
                await destination_channel.send(final_text)
                
            print(f"✅ Forwarded message from {message.author} in #{message.channel.name} to #{destination_channel.name}")
            
    except Exception as e:
        print(f"❌ Error forwarding message to channel {destination_channel_id}: {e}")

# Legacy function for backward compatibility
async def forward_message(message):
    """Legacy function - forwards to the old single destination channel"""
    try:
        if DESTINATION_CHANNEL_ID != 0:
            await forward_message_to_channel(message, DESTINATION_CHANNEL_ID)
        else:
            print(f"⚠️  No destination channel configured for legacy forward")
            
    except Exception as e:
        print(f"❌ Error in legacy forward_message: {e}")

@bot.command(name='setup')
@commands.has_permissions(administrator=True)
async def setup_forwarding(ctx, source_channel_input: str = None, destination_channel_input: str = None):
    """Setup command for administrators to configure forwarding"""
    if not source_channel_input or not destination_channel_input:
        await ctx.send("❌ **Usage:** `!setup #source_channel #destination_channel`\n"
                      "Or use channel IDs: `!setup 123456789 987654321`\n"
                      "Example: `!setup #general #announcements`\n\n"
                      "💡 **Tip:** After setup, use `!addfilter <word>` to block specific words from being forwarded.")
        return
    
    # Try to get channels from mentions or IDs
    source_channel = None
    destination_channel = None
    
    # Handle source channel
    if source_channel_input.startswith('<#') and source_channel_input.endswith('>'):
        # Channel mention format
        channel_id = source_channel_input[2:-1]
        source_channel = bot.get_channel(int(channel_id))
    elif source_channel_input.isdigit():
        # Raw ID
        source_channel = bot.get_channel(int(source_channel_input))
    
    # Handle destination channel  
    if destination_channel_input.startswith('<#') and destination_channel_input.endswith('>'):
        # Channel mention format
        channel_id = destination_channel_input[2:-1]
        destination_channel = bot.get_channel(int(channel_id))
    elif destination_channel_input.isdigit():
        # Raw ID
        destination_channel = bot.get_channel(int(destination_channel_input))
    
    # Validate channels
    if not source_channel:
        await ctx.send(f"❌ **Source channel not found!**\n"
                      f"Could not find channel: `{source_channel_input}`\n"
                      f"Use `!debug` to see available channels.")
        return
    
    if not destination_channel:
        await ctx.send(f"❌ **Destination channel not found!**\n"
                      f"Could not find channel: `{destination_channel_input}`\n"
                      f"Make sure the bot is in that server and has access to the channel.")
        return
    
    # Success - show configuration
    await ctx.send(f"⚙️ **Configuration Instructions:**\n"
                  f"Add these to your .env file:\n"
                  f"```\nSOURCE_CHANNEL_ID={source_channel.id}\n"
                  f"DESTINATION_CHANNEL_ID={destination_channel.id}\n```\n"
                  f"**Source:** #{source_channel.name} ({source_channel.guild.name})\n"
                  f"**Destination:** #{destination_channel.name} ({destination_channel.guild.name})\n\n"
                  f"Then restart the bot for changes to take effect.\n\n"
                  f"🚀 **Or use:** `!quicksetup {source_channel.id} {destination_channel.id}` for instant setup!")

@bot.command(name='quicksetup')
@commands.has_permissions(administrator=True)
async def quick_setup(ctx, source_channel_input: str = None, destination_channel_input: str = None, *, pair_name: str = None):
    """Instantly add a new source-destination channel pair"""
    if not source_channel_input or not destination_channel_input:
        await ctx.send("❌ **Usage:** `!quicksetup #source_channel #destination_channel [pair_name]`\n"
                      "Or use channel IDs: `!quicksetup 123456789 987654321 \"My Pair\"`\n"
                      "Example: `!quicksetup #general #announcements \"General News\"`\n\n"
                      "🚀 **This command adds a new channel pair instantly!**")
        return
    
    # Try to get channels from mentions or IDs
    source_channel = None
    destination_channel = None
    
    # Handle source channel
    if source_channel_input.startswith('<#') and source_channel_input.endswith('>'):
        # Channel mention format
        channel_id = source_channel_input[2:-1]
        source_channel = bot.get_channel(int(channel_id))
    elif source_channel_input.isdigit():
        # Raw ID
        source_channel = bot.get_channel(int(source_channel_input))
    
    # Handle destination channel  
    if destination_channel_input.startswith('<#') and destination_channel_input.endswith('>'):
        # Channel mention format
        channel_id = destination_channel_input[2:-1]
        destination_channel = bot.get_channel(int(destination_channel_input))
    elif destination_channel_input.isdigit():
        # Raw ID
        destination_channel = bot.get_channel(int(destination_channel_input))
    
    # Validate channels
    if not source_channel:
        await ctx.send(f"❌ **Source channel not found!**\n"
                      f"Could not find channel: `{source_channel_input}`\n"
                      f"Use `!debug` to see available channels.")
        return
    
    if not destination_channel:
        await ctx.send(f"❌ **Destination channel not found!**\n"
                      f"Could not find channel: `{destination_channel_input}`\n"
                      f"Make sure the bot is in that server and has access to the channel.")
        return
    
    # Add new channel pair
    try:
        # Generate pair name if not provided
        if not pair_name:
            pair_name = f"{source_channel.guild.name[:15]} → {destination_channel.guild.name[:15]}"
        
        success, message = add_channel_pair(source_channel.id, destination_channel.id, pair_name)
        
        if success:
            # Success message
            await ctx.send(f"🎉 **New Channel Pair Added!**\n\n"
                          f"✅ **Source:** #{source_channel.name} ({source_channel.guild.name})\n"
                          f"✅ **Destination:** #{destination_channel.name} ({destination_channel.guild.name})\n"
                          f"📝 **Name:** {pair_name}\n\n"
                          f"🚀 **Active immediately!** Messages will be copied now.\n"
                          f"💡 Use `!listpairs` to see all pairs, `!addfilter <word>` to block words.")
            
            print(f"🆕 New channel pair added via quicksetup:")
            print(f"   {pair_name}: #{source_channel.name} ({source_channel.id}) → #{destination_channel.name} ({destination_channel.id})")
        else:
            await ctx.send(f"❌ **Could not add channel pair:** {message}")
        
    except Exception as e:
        await ctx.send(f"❌ **Error adding channel pair:** {e}\n"
                      f"Please check bot permissions and try again.")
        print(f"Error in quicksetup: {e}")

@bot.command(name='addpair')
@commands.has_permissions(administrator=True)
async def add_pair_command(ctx, source_channel_input: str = None, destination_channel_input: str = None, *, pair_name: str = None):
    """Add a new source-destination channel pair"""
    if not source_channel_input or not destination_channel_input:
        await ctx.send("❌ **Usage:** `!addpair #source_channel #destination_channel [pair_name]`\n"
                      "Or use channel IDs: `!addpair 123456789 987654321 \"My Pair\"`\n"
                      "Example: `!addpair #alerts #notifications \"Alert System\"`")
        return
    
    # Try to get channels from mentions or IDs
    source_channel = None
    destination_channel = None
    
    # Handle source channel
    if source_channel_input.startswith('<#') and source_channel_input.endswith('>'):
        channel_id = source_channel_input[2:-1]
        source_channel = bot.get_channel(int(channel_id))
    elif source_channel_input.isdigit():
        source_channel = bot.get_channel(int(source_channel_input))
    
    # Handle destination channel
    if destination_channel_input.startswith('<#') and destination_channel_input.endswith('>'):
        channel_id = destination_channel_input[2:-1]
        destination_channel = bot.get_channel(int(destination_channel_input))
    elif destination_channel_input.isdigit():
        destination_channel = bot.get_channel(int(destination_channel_input))
    
    # Validate channels
    if not source_channel:
        await ctx.send(f"❌ **Source channel not found:** `{source_channel_input}`\n"
                      f"Use `!debug` to see available channels.")
        return
    
    if not destination_channel:
        await ctx.send(f"❌ **Destination channel not found:** `{destination_channel_input}`")
        return
    
    # Generate pair name if not provided
    if not pair_name:
        pair_name = f"{source_channel.name} → {destination_channel.name}"
    
    # Add the channel pair
    success, message = add_channel_pair(source_channel.id, destination_channel.id, pair_name)
    
    if success:
        await ctx.send(f"✅ **Channel pair added successfully!**\n"
                      f"**Source:** #{source_channel.name} ({source_channel.guild.name})\n"
                      f"**Destination:** #{destination_channel.name} ({destination_channel.guild.name})\n"
                      f"**Name:** {pair_name}")
        print(f"➕ Added channel pair: {pair_name}")
    else:
        await ctx.send(f"❌ **Error:** {message}")

@bot.command(name='removepair')
@commands.has_permissions(administrator=True)
async def remove_pair_command(ctx, source_channel_input: str = None, destination_channel_input: str = None):
    """Remove a source-destination channel pair"""
    if not source_channel_input or not destination_channel_input:
        await ctx.send("❌ **Usage:** `!removepair #source_channel #destination_channel`\n"
                      "Or use channel IDs: `!removepair 123456789 987654321`\n"
                      "Use `!listpairs` to see all current pairs.")
        return
    
    # Try to get channels from mentions or IDs
    source_channel_id = None
    destination_channel_id = None
    
    # Handle source channel
    if source_channel_input.startswith('<#') and source_channel_input.endswith('>'):
        source_channel_id = int(source_channel_input[2:-1])
    elif source_channel_input.isdigit():
        source_channel_id = int(source_channel_input)
    else:
        await ctx.send(f"❌ **Invalid source channel:** `{source_channel_input}`")
        return
    
    # Handle destination channel
    if destination_channel_input.startswith('<#') and destination_channel_input.endswith('>'):
        destination_channel_id = int(destination_channel_input[2:-1])
    elif destination_channel_input.isdigit():
        destination_channel_id = int(destination_channel_input)
    else:
        await ctx.send(f"❌ **Invalid destination channel:** `{destination_channel_input}`")
        return
    
    # Remove the channel pair
    success, message = remove_channel_pair(source_channel_id, destination_channel_id)
    
    if success:
        await ctx.send(f"✅ **Channel pair removed successfully!**\n{message}")
        print(f"➖ Removed channel pair: {message}")
    else:
        await ctx.send(f"❌ **Error:** {message}")

@bot.command(name='check')
async def check_bot(ctx):
    """Simple command to check if the bot is online and responding"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"✅ **Bot is Online!**\n📡 **Ping:** `{latency}ms`\n🕒 **Status:** Active and Monitoring")

@bot.command(name='listpairs')
@commands.has_permissions(administrator=True)
async def list_pairs_command(ctx):
    """List all configured channel pairs"""
    pairs = load_channel_pairs()
    
    if not pairs:
        await ctx.send("📝 **No channel pairs configured yet!**\n\n"
                      "Use `!quicksetup #source #destination` to add your first pair.")
        return
    
    # Build the list message
    pairs_msg = f"📋 **Configured Channel Pairs ({len(pairs)} total):**\n\n"
    
    for i, pair in enumerate(pairs, 1):
        # Get channel info
        source_channel = bot.get_channel(pair['source'])
        dest_channel = bot.get_channel(pair['destination'])
        
        # Format source channel info
        if source_channel:
            source_info = f"#{source_channel.name} ({source_channel.guild.name})"
        else:
            source_info = f"Unknown Channel ({pair['source']})"
        
        # Format destination channel info  
        if dest_channel:
            dest_info = f"#{dest_channel.name} ({dest_channel.guild.name})"
        else:
            dest_info = f"Unknown Channel ({pair['destination']})"
        
        pairs_msg += f"**{i}. {pair['name']}**\n"
        pairs_msg += f"   📤 **Source:** {source_info}\n"
        pairs_msg += f"   📥 **Destination:** {dest_info}\n"
        pairs_msg += f"   🆔 **IDs:** `{pair['source']}` → `{pair['destination']}`\n\n"
    
    pairs_msg += "💡 **Commands:**\n"
    pairs_msg += "• `!addpair #source #dest \"name\"` - Add new pair\n"
    pairs_msg += "• `!removepair #source #dest` - Remove pair\n"
    pairs_msg += "• `!quicksetup #source #dest` - Quick add pair"
    
    # Split message if too long
    if len(pairs_msg) > 1900:
        # Send in chunks
        chunks = [pairs_msg[i:i+1900] for i in range(0, len(pairs_msg), 1900)]
        for i, chunk in enumerate(chunks):
            if i == 0:
                await ctx.send(chunk)
            else:
                await ctx.send(f"...continued:\n{chunk}")
    else:
        await ctx.send(pairs_msg)

@bot.command(name='status')
@commands.has_permissions(administrator=True)
async def status(ctx):
    """Check bot configuration status"""
    status_msg = "**🤖 Bot Configuration Status:**\n"
    status_msg += f"✅ Bot Token: {'Configured' if BOT_TOKEN else '❌ Missing'}\n\n"
    
    # Show channel pairs
    pairs = load_channel_pairs()
    if pairs:
        status_msg += f"📋 **Channel Pairs:** {len(pairs)} configured\n"
        for i, pair in enumerate(pairs[:3], 1):  # Show first 3 pairs
            source_channel = bot.get_channel(pair['source'])
            dest_channel = bot.get_channel(pair['destination'])
            
            if source_channel and dest_channel:
                status_msg += f"   {i}. {pair['name']}: #{source_channel.name} → #{dest_channel.name}\n"
            else:
                status_msg += f"   {i}. {pair['name']}: (Some channels not found)\n"
        
        if len(pairs) > 3:
            status_msg += f"   ... and {len(pairs) - 3} more pairs\n"
        
        status_msg += f"   💡 Use `!listpairs` to see all pairs\n"
    else:
        status_msg += "❌ **Channel Pairs:** None configured\n"
        status_msg += "   💡 Use `!quicksetup #source #dest` to add pairs\n"
    
    status_msg += "\n"
    
    # Show filter status
    filters = load_filters()
    if filters:
        status_msg += f"✅ **Message Filters:** {len(filters)} blocked word(s)\n"
        filter_preview = ", ".join(filters[:3])
        if len(filters) > 3:
            filter_preview += f" (+{len(filters) - 3} more)"
        status_msg += f"   🚫 Blocked: {filter_preview}\n"
    else:
        status_msg += "⚠️  **Message Filters:** None (all messages forwarded)\n"
    
    status_msg += "\n**🚀 Commands:**\n"
    status_msg += "• `!quicksetup #src #dest` - Add channel pair\n"
    status_msg += "• `!listpairs` - View all pairs\n"
    status_msg += "• `!addfilter word` - Block words\n"
    
    await ctx.send(status_msg)

@bot.command(name='test')
@commands.has_permissions(administrator=True)
async def test_forward(ctx):
    """Test the forwarding functionality"""
    if DESTINATION_CHANNEL_ID == 0:
        await ctx.send("❌ Destination channel not configured!")
        return
    
    destination_channel = bot.get_channel(DESTINATION_CHANNEL_ID)
    if not destination_channel:
        await ctx.send(f"❌ Could not find destination channel with ID {DESTINATION_CHANNEL_ID}!")
        return
    
    # Create a test message-like object
    class TestMessage:
        def __init__(self, author, content, channel):
            self.author = author
            self.content = content
            self.channel = channel
            self.embeds = []
            self.attachments = []
    
    test_msg = TestMessage(ctx.author, "🧪 This is a test message from the forwarding bot!", ctx.channel)
    await forward_message(test_msg)
    await ctx.send(f"✅ Test message sent to #{destination_channel.name}!")

@bot.command(name='debug')
@commands.has_permissions(administrator=True)
async def debug_channels(ctx):
    """Show available channels in this server for debugging"""
    guild = ctx.guild
    if not guild:
        await ctx.send("❌ This command must be used in a server!")
        return
    
    channels_info = f"**🔍 Available channels in {guild.name}:**\n"
    text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
    
    for channel in text_channels[:10]:  # Limit to 10 channels to avoid message length issues
        channels_info += f"#{channel.name} - ID: `{channel.id}`\n"
    
    if len(text_channels) > 10:
        channels_info += f"\n... and {len(text_channels) - 10} more channels"
    
    channels_info += f"\n**Current source channel ID:** `{SOURCE_CHANNEL_ID}`"
    
    if SOURCE_CHANNEL_ID != 0:
        if any(ch.id == SOURCE_CHANNEL_ID for ch in text_channels):
            channels_info += " ✅ (Found in this server)"
        else:
            channels_info += " ❌ (Not found in this server)"
    
    await ctx.send(channels_info)

@bot.command(name='addfilter')
@commands.has_permissions(administrator=True)
async def add_filter(ctx, *, filter_word: str = None):
    """Add a word or phrase to the blocked words list"""
    if not filter_word:
        await ctx.send("❌ **Usage:** `!addfilter <word or phrase>`\n"
                      "Example: `!addfilter spam` or `!addfilter bad word`\n"
                      "ℹ️  Messages containing these words will be **blocked** from forwarding.")
        return
    
    filters = load_filters()
    
    # Check if filter already exists (case insensitive)
    if any(f.lower() == filter_word.lower() for f in filters):
        await ctx.send(f"⚠️  Filter '{filter_word}' already exists!")
        return
    
    filters.append(filter_word)
    save_filters(filters)
    
    await ctx.send(f"✅ Added blocked word: '{filter_word}'\n"
                  f"🚫 Messages containing this word will now be filtered out.\n"
                  f"Total blocked words: {len(filters)}")

@bot.command(name='removefilter')
@commands.has_permissions(administrator=True)
async def remove_filter(ctx, *, filter_word: str = None):
    """Remove a word or phrase from the blocked words list"""
    if not filter_word:
        await ctx.send("❌ **Usage:** `!removefilter <word or phrase>`\n"
                      "Example: `!removefilter hello world`")
        return
    
    filters = load_filters()
    
    # Find and remove filter (case insensitive)
    original_count = len(filters)
    filters = [f for f in filters if f.lower() != filter_word.lower()]
    
    if len(filters) == original_count:
        await ctx.send(f"❌ Filter '{filter_word}' not found!")
        return
    
    save_filters(filters)
    await ctx.send(f"✅ Removed blocked word: '{filter_word}'\n"
                  f"✉️  Messages with this word will now be forwarded again.\n"
                  f"Remaining blocked words: {len(filters)}")

@bot.command(name='listfilters')
async def list_filters(ctx):
    """List all current blocked words/phrases"""
    filters = load_filters()
    
    if not filters:
        await ctx.send("📋 **No blocked words configured**\n"
                      "All messages will be forwarded. Use `!addfilter <word>` to block words.")
        return
    
    filter_list = "\n".join([f"{i+1}. 🚫 '{filter_word}'" for i, filter_word in enumerate(filters)])
    
    embed = discord.Embed(
        title=f"📋 Blocked Words/Phrases ({len(filters)})",
        description=filter_list,
        color=0xe74c3c
    )
    embed.set_footer(text="Messages containing these words/phrases will be BLOCKED from forwarding")
    
    await ctx.send(embed=embed)

@bot.command(name='clearfilters')
@commands.has_permissions(administrator=True)
async def clear_filters(ctx):
    """Clear all blocked words/phrases"""
    filters = load_filters()
    
    if not filters:
        await ctx.send("📋 No blocked words to clear.")
        return
    
    save_filters([])
    await ctx.send(f"✅ Cleared all {len(filters)} filter(s).\n"
                  "\u26a0️  **Warning:** All messages will now be forwarded until you add new filters.")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ **Channel not found!**\n"
                      "Make sure to use channel mentions like `#channel-name`\n"
                      "Use `!debug` to see available channels in this server.")
    elif isinstance(error, commands.BadArgument):
        if "Channel" in str(error):
            await ctx.send("❌ **Invalid channel!**\n"
                          "Please use `!setup #source-channel #destination-channel`\n"
                          "Example: `!setup #general #announcements`")
        else:
            await ctx.send(f"❌ Invalid argument: {error}")
    else:
        print(f"Command error: {error}")
        await ctx.send("❌ An error occurred while executing the command.\n"
                      "Try using `!help` for command usage.")

if __name__ == "__main__":
    if BOT_TOKEN:
        try:
            bot.run(BOT_TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n" + "="*60)
            print("❌ PRIVILEGED INTENTS ERROR")
            print("="*60)
            print("Your bot needs the 'Message Content Intent' enabled.")
            print("\nTo fix this:")
            print("1. Go to https://discord.com/developers/applications/")
            print("2. Select your bot application")
            print("3. Go to the 'Bot' section")
            print("4. Scroll down to 'Privileged Gateway Intents'")
            print("5. Enable 'Message Content Intent'")
            print("6. Save changes and restart your bot")
            print("\nThis is required for the bot to read message content for forwarding.")
            print("="*60)
        except Exception as e:
            print(f"❌ ERROR: {e}")
    else:
        print("❌ ERROR: BOT_TOKEN not found in environment variables!")
        print("Please make sure your BOT_TOKEN is configured in Replit Secrets.")