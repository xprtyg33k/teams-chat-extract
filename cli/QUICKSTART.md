# CLI Quick Start

The `cli/` scripts let you run exports directly from a terminal without
starting the web server.  All commands assume you are running from the
**project root** with the virtual environment active.

## Prerequisites

- Python 3.8+
- A Microsoft Teams account
- An Azure AD app registration with `Chat.Read` and `User.ReadBasic.All`
  permissions (see main [README](../README.md#azure-ad-setup) for steps)

## 1. Configure credentials

Create a `.env` file in the project root:

```
TEAMS_CLIENT_ID=<your-app-client-id>
TEAMS_TENANT_ID=<your-tenant-id>
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Discover your chats

### List all chats

```powershell
python -m cli.list_chats
```

Displays every chat with its ID, type, topic, and members.  Copy the
`chat_id` you want to export.

### Filter chats

```powershell
# Only 1:1 chats
python -m cli.list_chats --chat-type oneOnOne

# Group chats whose topic contains "project"
python -m cli.list_chats --chat-type group --topic-include project
```

### Find recently active chats

```powershell
# Chats active in the last 365 days (default)
python -m cli.list_active_chats

# Tighten the window
python -m cli.list_active_chats --min-activity-days 90 --max-meeting-participants 5
```

## 4. Export a chat

```powershell
python -m cli.teams_chat_export `
  --chat-id "19:xxxxxxxxxxxxxxxx@thread.v2" `
  --since 2025-01-01
```

### Common options

| Flag | Default | Description |
|------|---------|-------------|
| `--chat-id` | *(required)* | Chat to export |
| `--since` | *(required)* | Start date `YYYY-MM-DD` |
| `--until` | today | End date `YYYY-MM-DD` |
| `--format` | `json` | `json` or `txt` |
| `--exclude-system-messages` | off | Skip Teams system events |
| `--only-mine` | off | Include only your messages |
| `--force-login` | off | Ignore cached token |
| `--output` | `./out/` | Directory for output file |

### Examples

```powershell
# Export a 1:1 chat for Q1 2025, JSON output
python -m cli.teams_chat_export `
  --chat-id "19:abc@thread.v2" `
  --since 2025-01-01 --until 2025-03-31

# Plain-text transcript, no system messages
python -m cli.teams_chat_export `
  --chat-id "19:abc@thread.v2" `
  --since 2025-01-01 `
  --format txt `
  --exclude-system-messages

# Force fresh login
python -m cli.teams_chat_export `
  --chat-id "19:abc@thread.v2" `
  --since 2025-01-01 `
  --force-login
```

## 5. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `TEAMS_CLIENT_ID / TEAMS_TENANT_ID not set` | Check `.env` is in the project root |
| `Chat not found` | Run `list_chats` and verify the chat ID |
| `Token expired` | Add `--force-login` |
| Blank lines in TXT export | Add `--exclude-system-messages` |
| `PermissionError` | Verify Azure AD app has `Chat.Read` |

---

For the full feature reference see the main [README](../README.md).
For the browser-based interface see the root [QUICKSTART](../QUICKSTART.md).
