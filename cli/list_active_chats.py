#!/usr/bin/env python3
"""
List all active Teams chats with last activity date, sorted by most recent.

Displays:
- Chat name (topic or participants)
- Chat type (group, meeting, oneOnOne)
- Group name (if available)
- Date of last activity

Output is saved to "All-Active-Chats-By-Last-Active-Date-As-Of-DDMMYYYY.txt"
"""

import argparse
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from .teams_chat_export import authenticate, GraphAPIClient, load_env_file

# Fix Windows console encoding issues with Unicode characters
# Only do this in main context, not when imported as a module
if sys.platform == 'win32' and __name__ == '__main__':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_chat_last_activity(chat: Dict[str, Any]) -> Optional[datetime]:
    """
    Get the date of the last message in a chat from chat metadata.
    
    Args:
        chat: Chat object from Graph API
        
    Returns:
        datetime of last message, or None if unable to determine
    """
    try:
        # Try to get from lastMessagePreview first
        if 'lastMessagePreview' in chat and chat['lastMessagePreview']:
            preview = chat['lastMessagePreview']
            if isinstance(preview, dict):
                created_date_str = preview.get('createdDateTime')
                if created_date_str:
                    return datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
    except Exception as e:
        # Silently skip errors
        pass
    
    return None


def get_chat_display_name(chat: Dict[str, Any], members: Optional[List[Dict[str, Any]]]) -> str:
    """
    Get a display name for the chat.
    
    Priority:
    1. Chat topic (for group chats)
    2. Participant names (for 1:1 chats)
    
    Args:
        chat: Chat object from Graph API
        members: List of members, or None if unable to retrieve
        
    Returns:
        Display name string
    """
    # Try topic first (handle None values)
    topic = chat.get('topic')
    if topic:
        topic = topic.strip() if isinstance(topic, str) else str(topic)
        if topic:
            return topic
    
    # Try to build from members
    if members:
        member_names = [str(m.get('displayName', 'Unknown')) if m.get('displayName') else 'Unknown' for m in members]
        member_names = [name for name in member_names if name and name != 'None']
        return ', '.join(member_names) if member_names else '(No name)'
    
    return '(No name)'


def should_include_chat(chat: Dict[str, Any], members: Optional[List[Dict[str, Any]]], 
                        last_activity: Optional[datetime], filters: Dict[str, Any]) -> bool:
    """
    Determine if a chat should be included based on filters.
    
    Args:
        chat: Chat object
        members: List of members
        last_activity: Last activity date
        filters: Filter criteria dictionary
        
    Returns:
        True if chat should be included, False otherwise
    """
    chat_type = chat.get('chatType', 'unknown')
    
    # Exclude channels
    if chat_type == 'channel':
        return False
    
    # Check participant count limit for meetings
    if chat_type == 'meeting' and members:
        if filters['max_meeting_participants'] and len(members) > filters['max_meeting_participants']:
            return False
    
    # Check last activity date cutoff
    if last_activity and filters['min_activity_days']:
        cutoff_date = datetime.now(last_activity.tzinfo or datetime.now().astimezone().tzinfo) - timedelta(days=filters['min_activity_days'])
        if last_activity < cutoff_date:
            return False
    
    return True


def format_chat_line(chat_name: str, chat_type: str, last_activity: Optional[datetime], 
                     group_name: Optional[str] = None) -> str:
    """
    Format a single chat line for output.
    
    Args:
        chat_name: Name of the chat
        chat_type: Type of chat (group, meeting, oneOnOne)
        last_activity: Date of last activity, or None
        group_name: Group name if available
        
    Returns:
        Formatted string
    """
    # Format the last activity date
    if last_activity:
        last_activity_str = last_activity.strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_activity_str = "Unknown"
    
    # Build the line
    line = f"{chat_name}"
    
    if group_name:
        line += f" [Group: {group_name}]"
    
    line += f" | Type: {chat_type} | Last Active: {last_activity_str}"
    
    return line


def print_status(message: str):
    """Print a status message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def print_progress(message: str):
    """Print progress message on a single line (using carriage return)."""
    print(f"\r{message}", end="", flush=True)


def main():
    """Main function."""
    
    parser = argparse.ArgumentParser(
        description="List all active Teams chats sorted by last activity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default filters (exclude chats inactive for >1 year and meetings >10 participants)
  python list_active_chats.py
  
  # Include all chats regardless of age
  python list_active_chats.py --min-activity-days 0
  
  # Only include recent chats (last 30 days)
  python list_active_chats.py --min-activity-days 30
  
  # Only include chats active in last 6 months
  python list_active_chats.py --min-activity-days 180
  
  # Allow meetings with up to 50 participants
  python list_active_chats.py --max-meeting-participants 50
        """
    )
    
    parser.add_argument(
        "--min-activity-days",
        type=int,
        default=365,
        help="Minimum days since last activity (default: 365 days / 1 year). Set to 0 to include all."
    )
    parser.add_argument(
        "--max-meeting-participants",
        type=int,
        default=10,
        help="Maximum participants for meetings to include (default: 10). Set to 0 for unlimited."
    )
    
    args = parser.parse_args()
    
    # Build filters dictionary
    filters = {
        'min_activity_days': args.min_activity_days if args.min_activity_days > 0 else None,
        'max_meeting_participants': args.max_meeting_participants if args.max_meeting_participants > 0 else None,
    }
    
    print_status("Loading environment variables...")
    
    # Load environment variables from .env file
    load_env_file()
    
    tenant_id = os.environ.get("TEAMS_TENANT_ID")
    client_id = os.environ.get("TEAMS_CLIENT_ID")
    
    # Validate required credentials
    if not tenant_id:
        print_status("ERROR: TEAMS_TENANT_ID must be set in .env file or environment")
        return 1
    if not client_id:
        print_status("ERROR: TEAMS_CLIENT_ID must be set in .env file or environment")
        return 1
    
    print_status("✓ Credentials loaded")
    print_status("Authenticating with Microsoft Graph API...")
    sys.stdout.flush()
    sys.stderr.flush()
    
    try:
        # Pass verbose=True to show device code flow
        access_token = authenticate(tenant_id, client_id, verbose=True)
    except Exception as e:
        print()
        print_status(f"ERROR: Authentication failed: {e}")
        return 1
    
    print_status("")
    print_status("✓ Authentication successful")
    print_status("Validating access token...")
    
    # Create client and validate access
    client = GraphAPIClient(access_token, verbose=False)
    
    try:
        user_profile = client.get_my_profile()
        user_name = user_profile.get('displayName', 'Unknown')
        print_status(f"✓ Access verified for user: {user_name}")
    except Exception as e:
        print_status(f"ERROR: Could not validate access token: {e}")
        return 1
    
    print_status("Access validation complete. Proceeding to retrieve chats...")
    print_status("")
    
    # Generate output filename with today's date
    today = datetime.now()
    output_filename = f"All-Active-Chats-By-Last-Active-Date-As-Of-{today.strftime('%d%m%Y')}.txt"
    output_dir = Path("./out")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / output_filename
    
    chats_data: List[Dict[str, Any]] = []
    chat_count = 0
    
    try:
        print_status("Fetching chat list from Microsoft Graph API...")
        
        # Retrieve all chats with lastMessagePreview
        params = {
            "$select": "id,chatType,topic,lastMessagePreview"
        }
        for chat in client._paginate("/me/chats", params):
            chat_id = chat.get('id', 'N/A')
            chat_type = chat.get('chatType', 'unknown')
            
            print_progress(f"  Fetching chat data: {chat_count + 1} chats retrieved")
            
            # Get members
            members = None
            try:
                members = client.get_chat_members(chat_id)
            except Exception as e:
                error_str = str(e)
                # Silently skip meeting chats with access restrictions
                if 'meeting_' in chat_id and ('InsufficientPrivileges' in error_str or 'Access denied' in error_str):
                    continue
                elif 'NotFound' in error_str or 'Resource not found' in error_str:
                    continue
                # For other errors, try to continue
            
            # Get chat display name
            chat_name = get_chat_display_name(chat, members)
            
            # Get last activity from chat metadata
            last_activity = get_chat_last_activity(chat)
            
            # Get group name if applicable (for now, we'll skip this as it requires additional API calls)
            group_name = None
            
            # Apply filters
            if not should_include_chat(chat, members, last_activity, filters):
                continue
            
            chats_data.append({
                'name': chat_name,
                'type': chat_type,
                'last_activity': last_activity,
                'group_name': group_name,
                'chat_id': chat_id
            })
            chat_count += 1
        
        print_progress("")  # Clear the progress line
        print_status(f"✓ Retrieved {chat_count} chats")
        print_status("Sorting chats by last activity date...")
        
        # Sort by last activity (most recent first), handling None values
        chats_data.sort(
            key=lambda x: x['last_activity'] if x['last_activity'] else datetime.min,
            reverse=True
        )
        
        print_status("✓ Sorting complete")
        print_status("Writing output file...")
        
        # Write to output file
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write(f"{'='*100}\n")
            f.write(f"Active Teams Chats - Sorted by Last Activity\n")
            f.write(f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Chats (after filters): {len(chats_data)}\n")
            f.write(f"\nFilters Applied:\n")
            if filters['min_activity_days']:
                f.write(f"  - Minimum activity: {filters['min_activity_days']} days ago\n")
            else:
                f.write(f"  - Minimum activity: None (all dates included)\n")
            if filters['max_meeting_participants']:
                f.write(f"  - Maximum meeting participants: {filters['max_meeting_participants']}\n")
            else:
                f.write(f"  - Maximum meeting participants: None (all sizes included)\n")
            f.write(f"  - Channels: Excluded\n")
            f.write(f"{'='*100}\n\n")
            
            # Write each chat
            for i, chat_data in enumerate(chats_data, 1):
                line = format_chat_line(
                    chat_data['name'],
                    chat_data['type'],
                    chat_data['last_activity'],
                    chat_data['group_name']
                )
                f.write(line + "\n")
                
                # Progress update
                if i % 10 == 0 or i == len(chats_data):
                    print_progress(f"  Writing output: {i}/{len(chats_data)} chats written")
            
            # Write footer
            f.write(f"\n{'='*100}\n")
            f.write(f"Chat ID reference (for use with teams_chat_export.py):\n")
            f.write(f"{'='*100}\n\n")
            
            for i, chat_data in enumerate(chats_data, 1):
                f.write(f"{i}. {chat_data['name']}\n")
                f.write(f"   Chat ID: {chat_data['chat_id']}\n\n")
        
        print_progress("")  # Clear the progress line
        print_status(f"✓ Output saved to: {output_path.absolute()}")
        
        # Also print to console
        print(f"\n{'='*100}")
        print("Active Teams Chats - Sorted by Last Activity")
        print(f"{'='*100}\n")
        
        for chat_data in chats_data:
            line = format_chat_line(
                chat_data['name'],
                chat_data['type'],
                chat_data['last_activity'],
                chat_data['group_name']
            )
            print(line)
        
        return 0
    
    except Exception as e:
        print_progress("")  # Clear the progress line
        print_status(f"ERROR: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
