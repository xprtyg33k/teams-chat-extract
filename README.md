# Microsoft Teams Chat Export Tool

A Python command-line tool to export Microsoft Teams chat messages (1:1 and group chats) for a specified date range using Microsoft Graph API with device code flow authentication.

## Overview

This tool allows you to:
- Export Teams chat messages (1:1 and group chats only, not channels)
- Filter messages by date range
- Find chats by participants or specific chat ID
- Export in JSON or human-readable TXT format
- Filter to show only your own messages
- Handle pagination and rate limiting automatically

## Features

- ✅ **Device Code Flow Authentication** - No client secrets required
- ✅ **Flexible Chat Selection** - By participants or chat ID
- ✅ **Date Range Filtering** - Precise filtering with UTC normalization
- ✅ **Multiple Output Formats** - JSON and TXT
- ✅ **Robust Error Handling** - Exponential backoff for rate limiting
- ✅ **Token Caching** - Automatic token refresh across runs
- ✅ **Pagination Support** - Handles large result sets
- ✅ **Type Hints** - Full type annotations for better code quality

## Prerequisites

### Azure App Registration

You need an Azure AD app registration with the following configuration:

1. **Authentication Type**: Public client (device code flow)
2. **Redirect URI**: Not required for device code flow
3. **API Permissions** (Delegated):
   - `Chat.Read` - Read user chat messages
   - `User.ReadBasic.All` - Read basic user profiles
   - `offline_access` - Maintain access to data
   - `openid` - Sign in
   - `profile` - View user's basic profile

4. **Admin Consent**: Required for `Chat.Read` and `User.ReadBasic.All`

### Software Requirements

- Python 3.11 or higher
- pip (Python package manager)
- Git (for cloning the repository)

## Security Model

This tool uses **delegated permissions** with **device code flow** authentication:

- ✅ **Read-only access** - No write or delete capabilities
- ✅ **User context** - Only accesses chats the authenticated user can see
- ✅ **No client secrets** - Device code flow doesn't require secrets
- ✅ **Token caching** - Encrypted token cache using MSAL
- ✅ **Principle of least privilege** - Minimal required permissions

## Setup Instructions

### Option A: Dev Container (Recommended)

1. **Prerequisites**: Install [Docker](https://www.docker.com/) and [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

2. **Open in Container**:
   ```bash
   git clone <repository-url>
   cd extract-teams-chat
   code .
   ```

3. **Reopen in Container**: When prompted, click "Reopen in Container" or press `F1` and select "Dev Containers: Reopen in Container"

4. **Dependencies are installed automatically** during container build

### Option B: Local Virtual Environment

#### Windows (PowerShell)

```powershell
# Clone repository
git clone <repository-url>
cd extract-teams-chat

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

#### macOS/Linux (bash/zsh)

```bash
# Clone repository
git clone <repository-url>
cd extract-teams-chat

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Command-Line Syntax

```bash
python teams_chat_export.py \
  --tenant-id <TENANT_ID> \
  --client-id <CLIENT_ID> \
  --since <START_DATE> \
  --until <END_DATE> \
  (--participants <NAME_OR_EMAIL> [...] | --chat-id <CHAT_ID>) \
  [--only-mine] \
  [--format {json|txt}] \
  [--output <PATH>] \
  [--verbose]
```

### Required Arguments

- `--tenant-id` - Azure AD Tenant ID (UUID format)
- `--client-id` - Application (Client) ID (UUID format)
- `--since` - Start date (YYYY-MM-DD, inclusive)
- `--until` - End date (YYYY-MM-DD, exclusive)

### Chat Selection (Mutually Exclusive)

- `--participants` - One or more display names or email addresses
- `--chat-id` - Specific chat ID (format: `19:...@thread.v2`)

### Optional Arguments

- `--only-mine` - Include only messages from authenticated user
- `--format` - Output format: `json` (default) or `txt`
- `--output` - Output file path (default: stdout or `./output.{format}`)
- `--verbose` - Enable verbose logging (default: True)

## Examples

### Example 1: Export 1:1 Chat by Participants (Windows PowerShell)

```powershell
python .\teams_chat_export.py `
  --tenant-id "12345678-1234-1234-1234-123456789abc" `
  --client-id "87654321-4321-4321-4321-cba987654321" `
  --since "2025-06-01" `
  --until "2025-11-15" `
  --participants "Alice Smith" "bob@contoso.com" `
  --format json `
  --output .\out\chat.json
```

### Example 2: Export Group Chat by Chat ID (macOS/Linux)

```bash
python3 ./teams_chat_export.py \
  --tenant-id "12345678-1234-1234-1234-123456789abc" \
  --client-id "87654321-4321-4321-4321-cba987654321" \
  --since "2025-06-01" \
  --until "2025-11-15" \
  --chat-id "19:abc123def456@thread.v2" \
  --format txt \
  --output ./out/chat.txt
```

### Example 3: Export Only Your Messages

```bash
python teams_chat_export.py \
  --tenant-id "12345678-1234-1234-1234-123456789abc" \
  --client-id "87654321-4321-4321-4321-cba987654321" \
  --since "2025-06-01" \
  --until "2025-11-15" \
  --participants "colleague@contoso.com" \
  --only-mine \
  --format json \
  --output ./out/my_messages.json
```

### Example 4: Export to stdout (for piping)

```bash
python teams_chat_export.py \
  --tenant-id "12345678-1234-1234-1234-123456789abc" \
  --client-id "87654321-4321-4321-4321-cba987654321" \
  --since "2025-06-01" \
  --until "2025-11-15" \
  --chat-id "19:abc123@thread.v2" \
  --format json | jq '.messages[] | .body_text'
```

## Output Format Specifications

### JSON Format

```json
{
  "chat_id": "19:abc123@thread.v2",
  "chat_type": "group",
  "participants": [
    {
      "id": "user-id-1",
      "displayName": "Alice Smith",
      "userPrincipalName": "alice@contoso.com"
    },
    {
      "id": "user-id-2",
      "displayName": "Bob Jones",
      "userPrincipalName": "bob@contoso.com"
    }
  ],
  "date_range_start": "2025-06-01T00:00:00+00:00",
  "date_range_end": "2025-11-15T00:00:00+00:00",
  "exported_at_utc": "2025-11-24T10:30:00+00:00",
  "message_count": 42,
  "messages": [
    {
      "id": "msg-id-1",
      "createdDateTime": "2025-06-01T09:15:00Z",
      "lastModifiedDateTime": "2025-06-01T09:15:00Z",
      "from": {
        "id": "user-id-1",
        "displayName": "Alice Smith"
      },
      "body_text": "Hello team!",
      "body_html": "<div>Hello team!</div>",
      "attachments": []
    }
  ]
}
```

### TXT Format

```
================================================================================
TEAMS CHAT EXPORT
================================================================================

Chat ID:        19:abc123@thread.v2
Chat Type:      group
Participants:   Alice Smith (alice@contoso.com)
                Bob Jones (bob@contoso.com)
Date Range:     2025-06-01T00:00:00+00:00 to 2025-11-15T00:00:00+00:00
Exported:       2025-11-24T10:30:00+00:00
Message Count:  42

================================================================================
MESSAGES
================================================================================

[2025-06-01 09:15:00 UTC] Alice Smith:
Hello team!

--------------------------------------------------------------------------------

[2025-06-01 09:20:00 UTC] Bob Jones:
Hi Alice! How are you?

[Attachments: document.pdf (application/pdf)]

--------------------------------------------------------------------------------
```

## Troubleshooting

### Authentication Errors

**Problem**: "Authentication failed: invalid_client"

**Solution**: Verify your Tenant ID and Client ID are correct. Ensure the app registration is configured for public client (device code flow).

---

**Problem**: "User cancelled device code flow"

**Solution**: Complete the authentication process by visiting the URL shown and entering the code within the time limit.

---

### Permission Errors

**Problem**: "Access denied: Insufficient privileges"

**Solution**:
1. Ensure the app has `Chat.Read` and `User.ReadBasic.All` permissions
2. Verify admin consent has been granted
3. Check that the permissions are **delegated** (not application permissions)

---

### No Chats Found

**Problem**: "No chats found with participants: ..."

**Solutions**:
1. Verify participant names/emails are correct
2. Ensure you have a chat with those participants
3. Try using email addresses instead of display names
4. Check if the chat exists in your Teams client

---

**Problem**: "Chat not found: 19:..."

**Solutions**:
1. Verify the chat ID is correct
2. Ensure you have access to the chat
3. Check if the chat still exists

---

### Rate Limiting

**Problem**: "Rate limited. Retrying in X seconds..."

**Solution**: This is normal. The tool automatically handles rate limiting with exponential backoff. Wait for the retry to complete.

---

### Date Range Issues

**Problem**: "No messages in date range"

**Solutions**:
1. Verify the date range is correct
2. Check that messages exist in that time period
3. Remember `--since` is inclusive, `--until` is exclusive
4. Ensure dates are in UTC or specify timezone

---

## Known Limitations

1. **Channels Not Supported**: This tool only exports 1:1 and group chats, not Teams channels
2. **Delegated Access Only**: Requires user authentication; cannot run unattended with app-only permissions
3. **Graph API Filtering**: Limited server-side filtering on messages requires client-side processing
4. **Participant Resolution**: Ambiguous display names may require manual disambiguation
5. **Large Chats**: Very large chats (thousands of messages) may take time to retrieve
6. **Attachment Content**: Only metadata is exported, not actual file content
7. **Message Edits**: Only the current version of edited messages is exported
8. **Deleted Messages**: Deleted messages are not included in exports

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=teams_chat_export --cov-report=html

# Run specific test file
pytest tests/test_date_parsing.py -v
```

### Linting and Formatting

```bash
# Lint code
python -m ruff check teams_chat_export.py tests/

# Format code
python -m black teams_chat_export.py tests/
```

### Using Makefile

```bash
# Setup environment
make setup

# Run tests
make test

# Lint code
make lint

# Format code
make format

# Clean up
make clean
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                          │
│              (argparse, input validation)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼─────────┐   ┌────────▼──────────┐
│  Authentication  │   │   Configuration   │
│   (MSAL + Cache) │   │  (Tenant/Client)  │
└────────┬─────────┘   └───────────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│           Microsoft Graph API Client                      │
│  • Pagination Handler                                     │
│  • Rate Limiting (Exponential Backoff + Jitter)          │
│  • Error Handling & Retry Logic                          │
└────────┬──────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────┐
│Chats │  │Messages│
│API   │  │API     │
└───┬──┘  └──┬─────┘
    │        │
┌───▼────────▼──────────────────────────────────────────────┐
│              Business Logic Layer                         │
│  • Participant Resolution                                 │
│  • Chat Discovery                                         │
│  • Message Filtering                                      │
│  • HTML → Plain Text Conversion                          │
└────────┬──────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼───┐
│ JSON  │ │ TXT  │
│Export │ │Export│
└───────┘ └──────┘
```

## Dependencies

- `msal` - Microsoft Authentication Library
- `requests` - HTTP client
- `html2text` - HTML to plain text conversion
- `beautifulsoup4` - HTML parsing (fallback)
- `lxml` - XML/HTML parser
- `pytest` - Testing framework
- `pytest-cov` - Test coverage
- `responses` - HTTP mocking for tests

## License

[Specify your license here]

## Contributing

[Specify contribution guidelines here]

## Support

For issues, questions, or contributions, please [open an issue](link-to-issues) on the repository.

## Acknowledgments

- Microsoft Graph API documentation
- MSAL Python library
- Python community

