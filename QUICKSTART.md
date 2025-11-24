# Quick Start Guide

Get started with the Teams Chat Export Tool in 5 minutes.

## Prerequisites

1. **Azure App Registration** with:
   - Tenant ID (UUID)
   - Client ID (UUID)
   - Delegated permissions: `Chat.Read`, `User.ReadBasic.All`, `offline_access`
   - Admin consent granted

2. **Python 3.11+** installed

## Setup (Choose One)

### Option A: Dev Container (Recommended)
```bash
# Open in VS Code
code .

# Reopen in Container (F1 → "Dev Containers: Reopen in Container")
# Dependencies install automatically
```

### Option B: Local Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Basic Usage

### Export a 1:1 Chat

```bash
python teams_chat_export.py \
  --tenant-id "YOUR_TENANT_ID" \
  --client-id "YOUR_CLIENT_ID" \
  --since "2025-06-01" \
  --until "2025-11-15" \
  --participants "colleague@company.com" \
  --format json \
  --output ./chat.json
```

### Export a Group Chat by ID

```bash
python teams_chat_export.py \
  --tenant-id "YOUR_TENANT_ID" \
  --client-id "YOUR_CLIENT_ID" \
  --since "2025-06-01" \
  --until "2025-11-15" \
  --chat-id "19:abc123@thread.v2" \
  --format txt \
  --output ./chat.txt
```

## First Run

1. **Run the command** - The tool will display a device code
2. **Open the URL** shown in your browser
3. **Enter the code** displayed
4. **Sign in** with your Microsoft account
5. **Grant consent** if prompted
6. **Wait** for the export to complete

## Finding Chat IDs

To get a chat ID:
1. Open Teams in a web browser
2. Navigate to the chat
3. Look at the URL: `https://teams.microsoft.com/...conversations/19:abc123@thread.v2...`
4. Copy the part that looks like `19:abc123@thread.v2`

## Common Issues

### "Authentication failed"
- Verify Tenant ID and Client ID are correct
- Ensure app is configured for device code flow

### "Access denied"
- Check that permissions are granted
- Verify admin consent is complete
- Ensure permissions are **delegated** (not application)

### "No chats found"
- Verify participant names/emails are correct
- Try using email addresses instead of display names
- Ensure you have a chat with those participants

## Output Files

- **JSON**: Structured data with full metadata
- **TXT**: Human-readable conversation format

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for implementation details
- Run tests: `pytest tests/ -v`

## Support

For issues or questions, refer to the Troubleshooting section in [README.md](README.md).

## Quick Reference

### All Arguments

```
Required:
  --tenant-id <UUID>        Azure AD Tenant ID
  --client-id <UUID>        Application (Client) ID
  --since <YYYY-MM-DD>      Start date (inclusive)
  --until <YYYY-MM-DD>      End date (exclusive)

Chat Selection (one required):
  --participants <name/email> [...]   Find chats by participants
  --chat-id <chat_id>                 Export specific chat

Optional:
  --only-mine               Only include your messages
  --format {json|txt}       Output format (default: json)
  --output <path>           Output file path
  --verbose                 Verbose logging (default: True)
```

### Exit Codes

- `0` - Success
- `1` - Error (authentication, API, invalid input)
- `2` - No matches found

## Example Output

### JSON
```json
{
  "chat_id": "19:abc123@thread.v2",
  "chat_type": "oneOnOne",
  "participants": [...],
  "message_count": 42,
  "messages": [...]
}
```

### TXT
```
================================================================================
TEAMS CHAT EXPORT
================================================================================

Chat ID:        19:abc123@thread.v2
Chat Type:      oneOnOne
Participants:   Alice Smith (alice@contoso.com)
...
```

---

**Ready to export?** Run your first command and start exporting Teams chats!

