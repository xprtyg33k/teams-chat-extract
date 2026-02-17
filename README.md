# Extract Teams Chat

Export Microsoft Teams chat messages to JSON, CSV, or HTML formats.

## Features

- ✅ Export single or multiple Teams chats
- ✅ Filter by date range (optional `--until` parameter)
- ✅ Exclude system messages (`--exclude-system-messages`)
- ✅ Multiple output formats: JSON, CSV, HTML
- ✅ Discover active chats (`list_active_chats.py`)
- ✅ List and filter chats (`list_chats.py`)
- ✅ Support for environment variables and `.env` files
- ✅ Token caching for faster subsequent runs
- ✅ Force re-authentication when needed (`--force-login`)

## Prerequisites

- Python 3.8+
- Microsoft Teams account
- Azure AD application with proper permissions

## Installation & Configuration

### 1. Azure AD Application Setup

Register an application in Azure AD with the following permissions:
- `Chat.Read`
- `ChatMessage.Read`
- `User.Read`

### 2. Create `.env` File

```bash
# .env
TEAMS_CLIENT_ID=your_application_id
TEAMS_TENANT_ID=your_tenant_id
```

Alternatively, set Windows environment variables:
```bash
setx TEAMS_CLIENT_ID your_application_id
setx TEAMS_TENANT_ID your_tenant_id
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Quick Start

See [QUICKSTART.md](QUICKSTART.md) for 5-minute setup.

### List Available Chats

```bash
python list_chats.py
```

**With filtering:**
```bash
python list_chats.py --filter "project" --display-ids
```

### List Active Chats

Find chats with recent activity:

```bash
python list_active_chats.py --days-back 30 --min-messages 5
```

**Options:**
- `--days-back N`: Show chats active in last N days (default: 7)
- `--min-messages N`: Only show chats with at least N messages
- `--output-format json|text`: Output format (default: text)

### Export Chats

#### Single Chat

```bash
python teams_chat_export.py --chat-id "chatid@thread.v2" --until "2026-02-17"
```

#### Multiple Chats

```bash
python teams_chat_export.py --chat-ids "chat1@thread.v2" "chat2@thread.v2" --until "2026-02-17"
```

## Arguments

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--chat-id` OR `--chat-ids` | Chat identifier(s) to export (format: `xxx@thread.v2`) |

### Optional Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--until` | Export messages up to this date (format: YYYY-MM-DD) | None (all messages) |
| `--exclude-system-messages` | Skip Teams system notifications and membership changes | False |
| `--output-format` | Format: `json`, `csv`, or `html` | json |
| `--output-dir` | Directory to save exports | `./exports` |
| `--force-login` | Force re-authentication, bypass token cache | False |

## Output Formats

### JSON
```json
{
  "messages": [
    {
      "id": "1708162800000",
      "sender": "user@example.com",
      "timestamp": "2026-02-17T14:30:00Z",
      "body": "Hello team!",
      "message_type": "text"
    }
  ]
}
```

### CSV
```
id,sender,timestamp,body,message_type
1708162800000,user@example.com,2026-02-17T14:30:00Z,Hello team!,text
```

### HTML
Self-contained HTML file with styled chat interface.

## Environment Variables

### Priority Order

1. Command-line arguments (highest priority)
2. `.env` file in project root
3. System environment variables
4. Default values (lowest priority)

### Supported Variables

```bash
TEAMS_CLIENT_ID=your_app_id
TEAMS_TENANT_ID=your_tenant_id
```

## Troubleshooting

### Authentication Issues

**Problem:** "Invalid credentials" or "Authentication failed"

**Solution:**
```bash
python teams_chat_export.py --chat-id "..." --force-login
```

This clears cached tokens and forces re-authentication.

### Chat Not Found

**Problem:** "Chat with ID 'xxx' not found"

**Solution:** Verify the chat ID format:
```bash
python list_chats.py
```

Chat IDs must end with `@thread.v2`.

### Permission Denied

**Problem:** "User does not have permission to access this chat"

**Solution:** Verify Azure AD permissions in your application registration.

### Token Expired

**Problem:** "Token has expired"

**Solution:** Use `--force-login` to refresh:
```bash
python teams_chat_export.py --chat-id "..." --force-login
```

## Project Structure

```
extract-teams-chat/
├── teams_chat_export.py      # Main export script
├── list_chats.py             # List and filter chats
├── list_active_chats.py       # Find active chats
├── auth_manager.py           # Azure AD authentication
├── teams_api_client.py       # Teams API wrapper
├── .env                      # Credentials (not in git)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── QUICKSTART.md            # Quick start guide
└── PROJECT_SUMMARY.md       # Project overview
```

## License

See LICENSE file for details.

