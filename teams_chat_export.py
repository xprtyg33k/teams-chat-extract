#!/usr/bin/env python3
"""
Microsoft Teams Chat Export Tool

Export Teams chat messages (1:1 and group chats) for a specified date range.
Uses Microsoft Graph API with device code flow authentication.
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote, unquote

import msal
import requests
from bs4 import BeautifulSoup
import html2text

# Constants
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_CACHE_FILE = ".token_cache.bin"
SCOPES = [
    "Chat.Read",
    "User.ReadBasic.All"
]
MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE = 2  # seconds

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_NO_MATCHES = 2


class TeamsExportError(Exception):
    """Base exception for Teams export errors."""
    pass


class AuthenticationError(TeamsExportError):
    """Authentication failed."""
    pass


class PermissionError(TeamsExportError):
    """Insufficient permissions."""
    pass


class NotFoundError(TeamsExportError):
    """Resource not found."""
    pass


class MaxRetriesExceeded(TeamsExportError):
    """Maximum retry attempts exceeded."""
    pass


def print_progress(message: str, verbose: bool = True) -> None:
    """Print progress message to stderr."""
    if verbose:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] {message}", file=sys.stderr)


def parse_date(date_str: str) -> datetime:
    """
    Parse date string to UTC datetime.
    
    Accepts:
    - YYYY-MM-DD → 00:00:00 UTC
    - YYYY-MM-DDTHH:MM:SS → UTC
    - YYYY-MM-DDTHH:MM:SSZ → UTC
    - ISO 8601 format
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object in UTC
        
    Raises:
        ValueError: If date string is invalid
    """
    # Try ISO 8601 with timezone
    for fmt in [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d"
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Ensure UTC timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    # Try parsing as ISO 8601 with timezone offset
    try:
        dt = datetime.fromisoformat(date_str)
        # Convert to UTC
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    
    raise ValueError(
        f"Invalid date format: {date_str}. "
        f"Expected YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, or ISO 8601 format."
    )


def load_token_cache() -> msal.SerializableTokenCache:
    """Load token cache from file."""
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, 'r') as f:
            cache.deserialize(f.read())
    return cache


def save_token_cache(cache: msal.SerializableTokenCache) -> None:
    """Save token cache to file."""
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, 'w') as f:
            f.write(cache.serialize())


def authenticate(tenant_id: str, client_id: str, verbose: bool = True) -> str:
    """
    Authenticate using MSAL device code flow.

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Application (client) ID
        verbose: Print progress messages

    Returns:
        Access token string

    Raises:
        AuthenticationError: If authentication fails
    """
    print_progress("Initializing authentication...", verbose)

    try:
        # Load token cache
        cache = load_token_cache()

        # Create MSAL public client application
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
            token_cache=cache
        )

        # Try to acquire token silently (using cached refresh token)
        accounts = app.get_accounts()
        if accounts:
            print_progress("Attempting silent token acquisition...", verbose)
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                print_progress("Authentication successful (cached token)", verbose)
                save_token_cache(cache)
                return result["access_token"]

        # Fall back to device code flow
        print_progress("Starting device code flow...", verbose)
        flow = app.initiate_device_flow(scopes=SCOPES)

        if "user_code" not in flow:
            raise AuthenticationError(
                "Failed to create device flow. Check tenant ID and client ID."
            )

        # Display device code instructions
        print("\n" + "=" * 70, file=sys.stderr)
        print("AUTHENTICATION REQUIRED", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(flow["message"], file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)

        # Wait for user to authenticate
        result = app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            error_desc = result.get("error_description", "Unknown error")
            raise AuthenticationError(f"Authentication failed: {error_desc}")

        print_progress("Authentication successful", verbose)
        save_token_cache(cache)
        return result["access_token"]

    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise
        raise AuthenticationError(f"Authentication error: {str(e)}")


class GraphAPIClient:
    """Microsoft Graph API client with pagination and retry logic."""

    def __init__(self, access_token: str, verbose: bool = True):
        """
        Initialize Graph API client.

        Args:
            access_token: OAuth access token
            verbose: Print progress messages
        """
        self.base_url = GRAPH_API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.max_retries = MAX_RETRIES
        self.verbose = verbose

    def _normalize_chat_id(self, chat_id: str) -> str:
        """
        Normalize and URL-encode chat ID for API requests.

        Detects if the chat ID is already URL-encoded and decodes it first,
        then re-encodes it properly. Provides user feedback if decoding was needed.

        Args:
            chat_id: Raw or URL-encoded chat ID

        Returns:
            Properly URL-encoded chat ID
        """
        # Check if the chat ID appears to be already URL-encoded
        # by looking for percent-encoded characters
        if '%' in chat_id:
            # Decode it first
            decoded = unquote(chat_id)
            if decoded != chat_id:
                print_progress(
                    f"Note: Chat ID was URL-encoded. Using decoded value for proper encoding.\n"
                    f"      In future, provide the unencoded chat ID from the Teams URL.",
                    self.verbose
                )
                chat_id = decoded

        # Now encode it properly for the API
        return quote(chat_id, safe='')

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and rate limiting.

        Args:
            url: Full URL or path relative to base_url
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            PermissionError: If insufficient permissions (403)
            NotFoundError: If resource not found (404)
            MaxRetriesExceeded: If max retries exceeded
        """
        # Construct full URL if needed
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    return response.json()

                elif response.status_code in [429, 503, 504]:
                    # Rate limited or service unavailable
                    retry_after = int(response.headers.get("Retry-After", 0))
                    backoff = max(retry_after, DEFAULT_BACKOFF_BASE ** attempt)
                    jitter = random.uniform(0, 1)
                    sleep_time = backoff + jitter

                    print_progress(
                        f"Rate limited (HTTP {response.status_code}). "
                        f"Retrying in {sleep_time:.1f}s... (attempt {attempt + 1}/{self.max_retries})",
                        self.verbose
                    )
                    time.sleep(sleep_time)
                    continue

                elif response.status_code == 403:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("error", {}).get("message", "Insufficient permissions")
                    raise PermissionError(
                        f"Access denied: {error_msg}. "
                        f"Ensure the app has Chat.Read and User.ReadBasic.All permissions."
                    )

                elif response.status_code == 404:
                    error_details = ""
                    try:
                        error_json = response.json()
                        error_details = f"\nAPI Error: {error_json.get('error', {}).get('message', 'No details')}"
                    except:
                        pass
                    raise NotFoundError(f"Resource not found: {url}{error_details}")

                else:
                    response.raise_for_status()

            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise MaxRetriesExceeded(f"Max retries exceeded: {str(e)}")

                backoff = DEFAULT_BACKOFF_BASE ** attempt
                print_progress(
                    f"Request error: {str(e)}. Retrying in {backoff}s... "
                    f"(attempt {attempt + 1}/{self.max_retries})",
                    self.verbose
                )
                time.sleep(backoff)

        raise MaxRetriesExceeded("Max retries exceeded")

    def _paginate(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        on_page: Optional[Callable[[int], None]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Handle pagination for Graph API responses.

        Args:
            url: Initial URL
            params: Query parameters (only used for first request)
            on_page: Optional callback invoked for each page with the number
                of items returned in that page.

        Yields:
            Individual items from paginated response
        """
        current_url = url
        current_params = params

        while current_url:
            response = self._make_request(current_url, current_params)

            # Yield items from current page
            items = response.get("value", [])

            # Notify caller about page size, if requested
            if on_page is not None:
                try:
                    on_page(len(items))
                except Exception as callback_error:
                    # Progress callbacks should never break pagination; log and continue.
                    print_progress(
                        f"Warning: on_page callback failed: {callback_error}",
                        self.verbose,
                    )

            for item in items:
                yield item

            # Get next page URL
            current_url = response.get("@odata.nextLink")
            current_params = None  # nextLink contains full URL with params

    def get_my_chats(self, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all chats for the authenticated user.

        Args:
            filter_query: OData $filter query string

        Returns:
            List of chat objects
        """
        print_progress("Retrieving chats...", self.verbose)

        params = {}
        if filter_query:
            params["$filter"] = filter_query

        chats = list(self._paginate("/me/chats", params))
        print_progress(f"Retrieved {len(chats)} chats", self.verbose)
        return chats

    def get_chat_by_id(self, chat_id: str) -> Dict[str, Any]:
        """
        Get specific chat by ID.

        Args:
            chat_id: Chat ID

        Returns:
            Chat object
        """
        print_progress(f"Retrieving chat {chat_id}...", self.verbose)
        # Normalize and URL-encode the chat ID
        encoded_chat_id = self._normalize_chat_id(chat_id)
        return self._make_request(f"/chats/{encoded_chat_id}")

    def get_chat_members(self, chat_id: str) -> List[Dict[str, Any]]:
        """
        Get members of a chat.

        Args:
            chat_id: Chat ID

        Returns:
            List of member objects
        """
        # Normalize and URL-encode the chat ID
        encoded_chat_id = self._normalize_chat_id(chat_id)
        members = list(self._paginate(f"/chats/{encoded_chat_id}/members"))
        return members

    def get_chat_messages(
        self,
        chat_id: str,
        filter_query: Optional[str] = None,
        orderby: Optional[str] = None,
        on_page: Optional[Callable[[int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a chat.

        Args:
            chat_id: Chat ID
            filter_query: OData $filter query string
            orderby: OData $orderby query string (required when using $filter)
            on_page: Optional callback invoked for each page with the number
                of messages returned in that page.

        Returns:
            List of message objects

        Note:
            According to Microsoft Graph API documentation, when using $filter,
            you must also provide $orderby on the same property. For example:
            - filter_query="lastModifiedDateTime gt 2025-01-01T00:00:00Z"
            - orderby="lastModifiedDateTime desc"
        """
        params = {}
        if filter_query:
            params["$filter"] = filter_query
        if orderby:
            params["$orderby"] = orderby

        # Normalize and URL-encode the chat ID
        encoded_chat_id = self._normalize_chat_id(chat_id)
        messages = list(
            self._paginate(f"/chats/{encoded_chat_id}/messages", params, on_page=on_page)
        )
        return messages

    def search_users(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for users by display name or email.

        Args:
            query: Search query (display name or email)

        Returns:
            List of user objects
        """
        # Check if query looks like an email
        if "@" in query:
            # Search by userPrincipalName
            filter_query = f"userPrincipalName eq '{query}'"
        else:
            # Search by display name (startswith for better performance)
            filter_query = f"startswith(displayName, '{query}')"

        params = {
            "$filter": filter_query,
            "$select": "id,displayName,userPrincipalName"
        }

        users = list(self._paginate("/users", params))
        return users

    def get_my_profile(self) -> Dict[str, Any]:
        """
        Get authenticated user's profile.

        Returns:
            User profile object
        """
        return self._make_request("/me")


def html_to_text(html: str) -> str:
    """
    Convert HTML to plain text.

    Args:
        html: HTML string

    Returns:
        Plain text string
    """
    if not html:
        return ""

    try:
        # Use html2text for conversion
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.body_width = 0  # Don't wrap lines
        text = h.handle(html)
        return text.strip()
    except Exception:
        # Fallback to BeautifulSoup
        try:
            soup = BeautifulSoup(html, "lxml")
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            # Last resort: return HTML as-is
            return html


def get_user_by_identifier(
    client: GraphAPIClient,
    identifier: str
) -> Dict[str, Any]:
    """
    Resolve display name or email to user object.

    Args:
        client: Graph API client
        identifier: Display name or email (UPN)

    Returns:
        User object with id, displayName, userPrincipalName

    Raises:
        NotFoundError: If user not found
        TeamsExportError: If multiple matches found
    """
    print_progress(f"Resolving user: {identifier}", client.verbose)

    users = client.search_users(identifier)

    if not users:
        raise NotFoundError(f"User not found: {identifier}")

    # If multiple matches, try exact match
    if len(users) > 1:
        # Try exact match on display name
        exact_matches = [
            u for u in users
            if u.get("displayName", "").lower() == identifier.lower()
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]

        # Try exact match on UPN
        exact_matches = [
            u for u in users
            if u.get("userPrincipalName", "").lower() == identifier.lower()
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]

        # Still ambiguous
        suggestions = "\n".join([
            f"  - {u.get('displayName')} ({u.get('userPrincipalName')})"
            for u in users[:5]
        ])
        raise TeamsExportError(
            f"Multiple users found for '{identifier}'. Please be more specific.\n"
            f"Suggestions:\n{suggestions}"
        )

    return users[0]


def find_chats_by_participants(
    client: GraphAPIClient,
    participant_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    Find chats where all specified participants are members.

    Args:
        client: Graph API client
        participant_ids: List of user IDs

    Returns:
        List of matching chats with members
    """
    print_progress(
        f"Finding chats with {len(participant_ids)} participants...",
        client.verbose
    )

    # Get all chats
    all_chats = client.get_my_chats()

    matching_chats = []
    participant_set = set(participant_ids)

    for chat in all_chats:
        chat_id = chat["id"]

        # Get chat members
        members = client.get_chat_members(chat_id)
        member_ids = {m.get("userId") for m in members if m.get("userId")}

        # Check if all participants are in this chat
        if participant_set.issubset(member_ids):
            chat["members"] = members
            matching_chats.append(chat)

    print_progress(f"Found {len(matching_chats)} matching chats", client.verbose)
    return matching_chats


def get_chat_messages_filtered(
    client: GraphAPIClient,
    chat_id: str,
    since: datetime,
    until: datetime,
    only_mine: bool = False,
    my_user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve messages for a chat with date filtering.

    Args:
        client: Graph API client
        chat_id: Chat ID
        since: Start date (inclusive)
        until: End date (exclusive)
        only_mine: Only include messages from authenticated user
        my_user_id: Authenticated user's ID (required if only_mine=True)

    Returns:
        List of filtered message objects
    """
    print_progress(f"Retrieving messages for chat {chat_id}...", client.verbose)

    # Use server-side filtering on lastModifiedDateTime to reduce data transfer
    # Note: Graph API requires $orderby when using $filter on the same property
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    until_str = until.strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_query = f"lastModifiedDateTime gt {since_str} and lastModifiedDateTime lt {until_str}"
    orderby = "lastModifiedDateTime desc"

    # Track and report pagination progress
    total_messages = 0

    def on_page(page_count: int) -> None:
        nonlocal total_messages
        total_messages += page_count
        print_progress(
            f"Retrieved {total_messages} messages so far...",
            client.verbose,
        )

    # Get messages with server-side filter, required orderby, and page-level progress
    messages = client.get_chat_messages(
        chat_id,
        filter_query,
        orderby,
        on_page=on_page,
    )

    # Apply precise client-side filtering on createdDateTime
    filtered_messages = []
    for msg in messages:
        created_str = msg.get("createdDateTime")
        if not created_str:
            continue

        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

        # Check date range (since inclusive, until exclusive)
        if not (since <= created_dt < until):
            continue

        # Check author if only_mine is True
        if only_mine and my_user_id:
            from_user = msg.get("from", {}).get("user", {})
            if from_user.get("id") != my_user_id:
                continue

        filtered_messages.append(msg)

    # Sort by createdDateTime ascending
    filtered_messages.sort(key=lambda m: m.get("createdDateTime", ""))

    print_progress(
        f"Retrieved {len(filtered_messages)} messages in date range",
        client.verbose
    )
    return filtered_messages


def process_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform raw Graph API message to export format.

    Args:
        msg: Raw message from Graph API

    Returns:
        Processed message dictionary
    """
    body = msg.get("body", {})
    body_html = body.get("content", "")
    body_text = html_to_text(body_html)

    # Process attachments
    attachments = []
    for att in msg.get("attachments", []):
        attachment_info = {
            "name": att.get("name", ""),
            "type": att.get("contentType", ""),
        }
        if "contentUrl" in att:
            attachment_info["contentUrl"] = att["contentUrl"]
        attachments.append(attachment_info)

    # Extract sender info
    from_info = msg.get("from", {})
    user_info = from_info.get("user") if from_info else None
    # Ensure user_info is a dict; handle None or missing user object
    if not isinstance(user_info, dict):
        user_info = {}

    return {
        "id": msg.get("id", ""),
        "createdDateTime": msg.get("createdDateTime", ""),
        "lastModifiedDateTime": msg.get("lastModifiedDateTime", ""),
        "from": {
            "id": user_info.get("id", ""),
            "displayName": user_info.get("displayName", "Unknown")
        },
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments
    }


def export_to_json(data: Dict[str, Any], output_path: Optional[str] = None) -> None:
    """
    Export data to JSON format.

    Args:
        data: Data to export
        output_path: Output file path (None for stdout)
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print_progress(f"Exported to {output_path}", True)
    else:
        print(json_str)


def export_to_txt(data: Dict[str, Any], output_path: Optional[str] = None) -> None:
    """
    Export data to human-readable text format.

    Args:
        data: Data to export
        output_path: Output file path (None for stdout)
    """
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("TEAMS CHAT EXPORT")
    lines.append("=" * 80)
    lines.append("")

    # Metadata
    lines.append(f"Chat ID:        {data.get('chat_id', 'N/A')}")
    lines.append(f"Chat Type:      {data.get('chat_type', 'N/A')}")

    # Participants
    participants = data.get("participants", [])
    if participants:
        lines.append(f"Participants:   {participants[0].get('displayName', 'Unknown')} "
                    f"({participants[0].get('userPrincipalName', 'N/A')})")
        for p in participants[1:]:
            lines.append(f"                {p.get('displayName', 'Unknown')} "
                        f"({p.get('userPrincipalName', 'N/A')})")

    lines.append(f"Date Range:     {data.get('date_range_start', 'N/A')} to "
                f"{data.get('date_range_end', 'N/A')}")
    lines.append(f"Exported:       {data.get('exported_at_utc', 'N/A')}")
    lines.append(f"Message Count:  {data.get('message_count', 0)}")
    lines.append("")

    # Messages
    lines.append("=" * 80)
    lines.append("MESSAGES")
    lines.append("=" * 80)
    lines.append("")

    messages = data.get("messages", [])
    for i, msg in enumerate(messages):
        # Parse and format timestamp
        created = msg.get("createdDateTime", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            timestamp = created

        # Message header
        from_name = msg.get("from", {}).get("displayName", "Unknown")
        lines.append(f"[{timestamp}] {from_name}:")

        # Message body
        body_text = msg.get("body_text", "")
        for line in body_text.split("\n"):
            lines.append(line)

        # Attachments
        attachments = msg.get("attachments", [])
        if attachments:
            lines.append("")
            att_names = ", ".join([
                f"{a.get('name', 'unnamed')} ({a.get('type', 'unknown')})"
                for a in attachments
            ])
            lines.append(f"[Attachments: {att_names}]")

        # Separator between messages
        if i < len(messages) - 1:
            lines.append("")
            lines.append("-" * 80)
            lines.append("")

    # Write output
    output_text = "\n".join(lines)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print_progress(f"Exported to {output_path}", True)
    else:
        print(output_text)


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Export Microsoft Teams chat messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export by participants (Windows PowerShell)
  python teams_chat_export.py `
    --tenant-id "12345678-1234-1234-1234-123456789abc" `
    --client-id "87654321-4321-4321-4321-cba987654321" `
    --since "2025-06-01" `
    --until "2025-11-15" `
    --participants "Alice Smith" "bob@contoso.com" `
    --format json `
    --output ./out/chat.json

  # Export by chat ID (macOS/Linux)
  python3 teams_chat_export.py \\
    --tenant-id "12345678-1234-1234-1234-123456789abc" \\
    --client-id "87654321-4321-4321-4321-cba987654321" \\
    --since "2025-06-01" \\
    --until "2025-11-15" \\
    --chat-id "19:abc123@thread.v2" \\
    --format txt \\
    --output ./out/chat.txt
        """
    )

    # Required arguments
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Azure AD Tenant ID (UUID)"
    )
    parser.add_argument(
        "--client-id",
        required=True,
        help="Application (Client) ID (UUID)"
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Start date (YYYY-MM-DD, inclusive)"
    )
    parser.add_argument(
        "--until",
        required=True,
        help="End date (YYYY-MM-DD, exclusive)"
    )

    # Chat selection (mutually exclusive)
    chat_group = parser.add_mutually_exclusive_group(required=True)
    chat_group.add_argument(
        "--participants",
        nargs="+",
        help="Display names or emails of participants"
    )
    chat_group.add_argument(
        "--chat-id",
        help="Specific chat ID (format: 19:...@thread.v2)"
    )

    # Optional arguments
    parser.add_argument(
        "--only-mine",
        action="store_true",
        help="Only include messages from authenticated user"
    )
    parser.add_argument(
        "--format",
        choices=["json", "txt"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout or ./output.{format})"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose logging (default: True)"
    )

    args = parser.parse_args()

    try:
        # Parse dates
        try:
            since = parse_date(args.since)
            until = parse_date(args.until)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_ERROR

        # Validate date range
        if since >= until:
            print("Error: --since must be before --until", file=sys.stderr)
            return EXIT_ERROR

        # Authenticate
        try:
            access_token = authenticate(args.tenant_id, args.client_id, args.verbose)
        except AuthenticationError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            return EXIT_ERROR

        # Create Graph API client
        client = GraphAPIClient(access_token, args.verbose)

        # Get authenticated user's profile
        my_profile = client.get_my_profile()
        my_user_id = my_profile.get("id")

        print_progress(
            f"Authenticated as: {my_profile.get('displayName')} "
            f"({my_profile.get('userPrincipalName')})",
            args.verbose
        )

        # Determine which chat(s) to export
        chats_to_export = []

        if args.chat_id:
            # Export specific chat by ID
            try:
                chat = client.get_chat_by_id(args.chat_id)
                members = client.get_chat_members(args.chat_id)
                chat["members"] = members
                chats_to_export.append(chat)
            except NotFoundError:
                print(f"Error: Chat not found: {args.chat_id}", file=sys.stderr)
                return EXIT_NO_MATCHES

        else:
            # Export by participants
            # Resolve participant identifiers to user IDs
            participant_ids = []
            for identifier in args.participants:
                try:
                    user = get_user_by_identifier(client, identifier)
                    participant_ids.append(user["id"])
                    print_progress(
                        f"Resolved '{identifier}' to {user.get('displayName')} "
                        f"({user.get('userPrincipalName')})",
                        args.verbose
                    )
                except (NotFoundError, TeamsExportError) as e:
                    print(f"Error: {e}", file=sys.stderr)
                    return EXIT_ERROR

            # Add authenticated user to participant list
            if my_user_id not in participant_ids:
                participant_ids.append(my_user_id)

            # Find matching chats
            chats_to_export = find_chats_by_participants(client, participant_ids)

            if not chats_to_export:
                print(
                    f"Error: No chats found with participants: {', '.join(args.participants)}",
                    file=sys.stderr
                )
                return EXIT_NO_MATCHES

        # Export each chat
        for chat in chats_to_export:
            chat_id = chat["id"]
            chat_type = chat.get("chatType", "unknown")

            print_progress(f"\nExporting chat: {chat_id} (type: {chat_type})", args.verbose)

            # Get messages
            messages = get_chat_messages_filtered(
                client,
                chat_id,
                since,
                until,
                args.only_mine,
                my_user_id
            )

            if not messages:
                print_progress("No messages in date range", args.verbose)
                continue

            # Process messages
            processed_messages = [process_message(msg) for msg in messages]

            # Get participant details
            members = chat.get("members", [])
            participants = []
            for member in members:
                participants.append({
                    "id": member.get("userId", ""),
                    "displayName": member.get("displayName", "Unknown"),
                    "userPrincipalName": member.get("email", "")
                })

            # Build export data
            export_data = {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "participants": participants,
                "date_range_start": since.isoformat(),
                "date_range_end": until.isoformat(),
                "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                "message_count": len(processed_messages),
                "messages": processed_messages
            }

            # Determine output path
            output_path = args.output
            if not output_path and len(chats_to_export) == 1:
                # Single chat, use default filename
                output_path = f"./output.{args.format}"
            elif not output_path:
                # Multiple chats, use chat ID in filename
                output_path = f"./out/chat_{chat_id[:8]}.{args.format}"

            # Export
            if args.format == "json":
                export_to_json(export_data, output_path)
            else:
                export_to_txt(export_data, output_path)

            print_progress(
                f"Successfully exported {len(processed_messages)} messages",
                args.verbose
            )

        return EXIT_SUCCESS

    except PermissionError as e:
        print(f"Permission error: {e}", file=sys.stderr)
        return EXIT_ERROR

    except MaxRetriesExceeded as e:
        print(f"Network error: {e}", file=sys.stderr)
        return EXIT_ERROR

    except TeamsExportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return EXIT_ERROR

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

