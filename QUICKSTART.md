# Quick Start Guide

## Prerequisites
- Python 3.8+
- Microsoft Teams account
- Azure AD application registered (see [README.md](README.md) for setup)

## 1. Environment Setup

Create a `.env` file in the project root with your Azure AD credentials:

```
TEAMS_CLIENT_ID=your_client_id_here
TEAMS_TENANT_ID=your_tenant_id_here
```

Or set environment variables:
```bash
set TEAMS_CLIENT_ID=your_client_id_here
set TEAMS_TENANT_ID=your_tenant_id_here
```

## 2. Basic Usage - Export a Chat

### List Available Chats First
```bash
python list_chats.py
```

This shows all chats you have access to with their IDs.

### Export a Single Chat
```bash
python teams_chat_export.py --chat-id "chatid@thread.v2" --until "2026-02-17"
```

### Export Multiple Chats
```bash
python teams_chat_export.py --chat-ids "chat1@thread.v2" "chat2@thread.v2" --until "2026-02-17"
```

## 3. Common Options

| Option | Purpose | Example |
|--------|---------|---------|
| `--chat-id` | Export single chat | `--chat-id "abc123@thread.v2"` |
| `--chat-ids` | Export multiple chats | `--chat-ids "chat1@thread.v2" "chat2@thread.v2"` |
| `--until` | Export up to date (optional) | `--until "2026-02-17"` |
| `--exclude-system-messages` | Skip Teams system messages | `--exclude-system-messages` |
| `--output-format` | Format: json, csv, or html | `--output-format json` |
| `--force-login` | Bypass cached credentials | `--force-login` |

## 4. Filter Active Chats by Activity

```bash
python list_active_chats.py --days-back 30 --min-messages 10
```

Find chats with activity in the last 30 days and at least 10 messages.

## 5. Advanced: Export with Filters

```bash
python teams_chat_export.py \
  --chat-id "chatid@thread.v2" \
  --until "2026-02-17" \
  --exclude-system-messages \
  --output-format json \
  --output-dir ./exports
```

## 6. Troubleshooting

**"Invalid credentials" error:**
- Verify `.env` file exists and has correct `TEAMS_CLIENT_ID` and `TEAMS_TENANT_ID`
- Or use `--force-login` to re-authenticate: `python teams_chat_export.py --chat-id "..." --force-login`

**"Chat not found" error:**
- Run `python list_chats.py` to find the correct chat ID
- Chat IDs end with `@thread.v2`

**Token expired:**
- Use `--force-login` flag to refresh authentication

## Next Steps

See [README.md](README.md) for detailed configuration and advanced features.

