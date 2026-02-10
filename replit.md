# Discord Bot Project

## Overview

This is a Discord bot application built with Python and the discord.py library. The bot is designed to monitor messages from a specific Discord channel and forward them to an external webhook URL. It serves as a bridge between Discord and external services, enabling automated message forwarding and integration capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework
- **Discord.py Library**: Uses the modern discord.py library with the commands extension for structured bot development
- **Asynchronous Architecture**: Built on asyncio for handling concurrent Discord events and HTTP requests
- **Intent-based Permissions**: Configured with specific Discord intents (message_content, guilds) for targeted functionality

### Configuration Management
- **Environment Variables**: Uses python-dotenv for secure configuration management
- **JSON Filter Storage**: Persistent storage for filter words and phrases
- **Key Configuration Parameters**:
  - BOT_TOKEN: Discord bot authentication token
  - SOURCE_CHANNEL_ID: Target Discord channel for message monitoring
  - WEBHOOK_URL: External endpoint for message forwarding
  - filter_words.json: Local file storing filter keywords and phrases

### Message Processing Pipeline
- **Event-driven Architecture**: Utilizes Discord.py event handlers for real-time message processing
- **Channel-specific Monitoring**: Filters messages from a designated source channel
- **Content Filtering System**: Advanced filtering based on configurable keywords and phrases
- **HTTP Integration**: Uses aiohttp for asynchronous webhook delivery

### Error Handling and Validation
- **Startup Validation**: Comprehensive configuration checking on bot initialization
- **Channel Verification**: Validates source channel accessibility and permissions
- **Graceful Degradation**: Continues operation with warnings for missing non-critical configuration

## Bot Commands

### Administrative Commands
- **!setup #channel webhook_url**: Configure source channel and webhook URL
- **!status**: Display current bot configuration and filter status
- **!test**: Send test message to configured webhook
- **!debug**: List available channels in server for debugging

### Filter Management Commands
- **!addfilter <word/phrase>**: Add keyword or phrase to filter list
- **!removefilter <word/phrase>**: Remove keyword or phrase from filter list
- **!listfilters**: Display all configured filter words/phrases
- **!clearfilters**: Remove all filters (admin only)

### Filter System Features
- **Flexible Filtering**: Support for both single words and multi-word phrases
- **Case Insensitive**: Filters work regardless of message capitalization
- **Persistent Storage**: Filters saved to JSON file and persist across bot restarts
- **Real-time Monitoring**: Only messages containing filter words are forwarded
- **Empty Filter Handling**: When no filters are set, all messages are forwarded

## External Dependencies

### Core Dependencies
- **discord.py**: Primary Discord API wrapper for bot functionality
- **aiohttp**: Asynchronous HTTP client for webhook requests
- **python-dotenv**: Environment variable management
- **json**: Built-in JSON handling for filter storage

### Discord Platform Integration
- **Discord API**: Real-time message events and guild information
- **Discord Webhooks**: For potential bi-directional communication

### External Webhook Service
- **Custom Webhook Endpoint**: Configurable external service for message forwarding
- **HTTP POST Integration**: Standard webhook protocol for data transmission

### Development Tools
- **Environment Variables**: Secure configuration without hardcoded secrets
- **Async/Await Pattern**: Modern Python concurrency for scalable operations