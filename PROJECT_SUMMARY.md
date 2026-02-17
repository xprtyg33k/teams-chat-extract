# Project Summary: Extract Teams Chat

## Overview

A Python utility suite for exporting Microsoft Teams chat messages to multiple formats (JSON, CSV, HTML) with flexible filtering and authentication options.

**Current Version:** 1.0.0  
**Last Updated:** February 17, 2026

## Capabilities

### Core Features

| Feature | Status | Details |
|---------|--------|---------|
| Export single chat | ✅ Complete | Via `--chat-id` parameter |
| Export multiple chats | ✅ Complete | Via `--chat-ids` parameter (space-separated) |
| Date filtering | ✅ Complete | Optional `--until` parameter (YYYY-MM-DD format) |
| System message filtering | ✅ Complete | `--exclude-system-messages` flag |
| JSON output | ✅ Complete | Default format with metadata |
| CSV output | ✅ Complete | Flat structure for spreadsheet import |
| HTML output | ✅ Complete | Self-contained, styled chat interface |
| Chat discovery | ✅ Complete | `list_chats.py` with optional filtering |
| Activity detection | ✅ Complete | `list_active_chats.py` with date/message filters |
| Token caching | ✅ Complete | Automatic token persistence and reuse |
| Force re-authentication | ✅ Complete | `--force-login` flag bypasses cache |
| Environment variables | ✅ Complete | Support for `.env` and system environment vars |

### Scripts Included

1. **`teams_chat_export.py`** (Main export tool)
   - Single/multiple chat export
   - Date range filtering
   - Output format selection
   - System message filtering
   - Token management

2. **`list_chats.py`** (Chat discovery)
   - List all accessible chats
   - Optional text filtering
   - Display chat IDs in copyable format
   - Sort options

3. **`list_active_chats.py`** (Activity filter)
   - Filter chats by last activity date
   - Minimum message threshold filtering
   - JSON or text output
   - Detailed activity metrics

4. **`auth_manager.py`** (Authentication)
   - Azure AD token acquisition
   - Token caching (file-based)
   - Automatic token refresh
   - Device code flow support

5. **`teams_api_client.py`** (API wrapper)
   - Graph API integration
   - Chat message retrieval
   - Error handling and retries
   - Pagination support

## Configuration

### Required Settings

```
TEAMS_CLIENT_ID: Azure AD application ID
TEAMS_TENANT_ID: Azure AD tenant ID
```

### Configuration Methods (in priority order)

1. `.env` file in project root
2. Windows environment variables
3. Command-line arguments

### Example `.env`

```
TEAMS_CLIENT_ID=0e2ae6dc-ea8b-40b0-8001-61e902fe42a0
TEAMS_TENANT_ID=5a8e2b45-25f8-40ea-a914-b466436e9417
```

## Command Reference

### Export Chat

```bash
# Basic export
python teams_chat_export.py --chat-id "chatid@thread.v2"

# With date limit (optional)
python teams_chat_export.py --chat-id "chatid@thread.v2" --until "2026-02-17"

# Exclude system messages
python teams_chat_export.py --chat-id "chatid@thread.v2" --exclude-system-messages

# Custom output format
python teams_chat_export.py --chat-id "chatid@thread.v2" --output-format csv

# Multiple chats
python teams_chat_export.py --chat-ids "chat1@thread.v2" "chat2@thread.v2"

# Force re-authentication
python teams_chat_export.py --chat-id "chatid@thread.v2" --force-login
```

### Discover Chats

```bash
# List all chats
python list_chats.py

# Filter by text
python list_chats.py --filter "project"

# Display chat IDs
python list_chats.py --display-ids
```

### Find Active Chats

```bash
# Active in last 7 days (default)
python list_active_chats.py

# Active in last 30 days
python list_active_chats.py --days-back 30

# With minimum message count
python list_active_chats.py --days-back 30 --min-messages 10

# JSON output
python list_active_chats.py --output-format json
```

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Comprehensive guide with setup, usage, and troubleshooting |
| `QUICKSTART.md` | 5-minute getting started guide |
| `PROJECT_SUMMARY.md` | This file - features, configuration, and command reference |

## Recent Updates (v1.0.0)

✅ Added `--exclude-system-messages` flag  
✅ Added `--force-login` flag for re-authentication  
✅ Made `--until` parameter optional  
✅ Created `list_active_chats.py` utility  
✅ Enhanced `list_chats.py` with filtering  
✅ Added environment variable support  
✅ Improved error messages and validation  

## Known Limitations

- Only text-based messages supported (no file attachments)
- Requires Azure AD application registration
- Token cache is user-specific and local to machine
- System messages are included by default (use `--exclude-system-messages` to filter)

## Requirements

See `requirements.txt` for Python package dependencies.

Key packages:
- `azure-identity` - Azure AD authentication
- `msgraph-core` - Microsoft Graph API client
- `python-dotenv` - Environment variable management

## Support

For issues or questions:
1. Check [QUICKSTART.md](QUICKSTART.md) for quick solutions
2. Review [README.md](README.md) troubleshooting section
3. Verify `.env` file configuration
4. Try `--force-login` to reset authentication

