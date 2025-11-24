#!/usr/bin/env python3
"""
Diagnostic script to list all your Teams chats and their IDs.
This helps identify the correct chat ID format for the export tool.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from teams_chat_export import authenticate, GraphAPIClient

def format_chat_info(chat_num, chat, members):
    """Format chat information as a string."""
    chat_id = chat.get('id', 'N/A')
    chat_type = chat.get('chatType', 'unknown')
    topic = chat.get('topic', '(No topic)')

    lines = []
    lines.append(f"Chat #{chat_num}")
    lines.append(f"  ID: {chat_id}")
    lines.append(f"  Type: {chat_type}")
    lines.append(f"  Topic: {topic}")

    if members:
        lines.append(f"  Members ({len(members)}):")
        for member in members:
            display_name = member.get('displayName', 'N/A')
            email = member.get('email', 'N/A')
            lines.append(f"    - {display_name} ({email})")
    else:
        lines.append(f"  Members: Error retrieving")

    lines.append("")
    return "\n".join(lines)


def matches_filters(chat, members, filters):
    """
    Check if a chat matches all active filters.

    Args:
        chat: Chat object from Graph API
        members: List of member objects
        filters: Dictionary of filter criteria

    Returns:
        True if chat matches all filters, False otherwise
    """
    # Chat type filter
    if filters['chat_types'] and filters['chat_types'] != ['all']:
        chat_type = chat.get('chatType', 'unknown')
        if chat_type not in filters['chat_types']:
            return False

    # Max participants filter
    if filters['max_participants'] is not None and members:
        if len(members) > filters['max_participants']:
            return False

    # Topic inclusion filter (OR logic)
    if filters['topic_include']:
        topic = chat.get('topic', '').lower()
        if not any(keyword.lower() in topic for keyword in filters['topic_include']):
            return False

    # Topic exclusion filter (OR logic - exclude if ANY keyword matches)
    if filters['topic_exclude']:
        topic = chat.get('topic', '').lower()
        if any(keyword.lower() in topic for keyword in filters['topic_exclude']):
            return False

    # Participant inclusion filter (OR logic)
    if filters['participants'] and members:
        member_emails = [m.get('email', '').lower() for m in members]
        if not any(email.lower() in member_emails for email in filters['participants']):
            return False

    return True


def print_filter_summary(filters):
    """Print a summary of active filters."""
    active_filters = []

    if filters['chat_types'] and filters['chat_types'] != ['all']:
        active_filters.append(f"  - Chat types: {', '.join(filters['chat_types'])}")

    if filters['max_participants'] is not None:
        active_filters.append(f"  - Max participants: {filters['max_participants']}")

    if filters['topic_include']:
        active_filters.append(f"  - Topic includes (OR): {', '.join(filters['topic_include'])}")

    if filters['topic_exclude']:
        active_filters.append(f"  - Topic excludes (OR): {', '.join(filters['topic_exclude'])}")

    if filters['participants']:
        active_filters.append(f"  - Participants (OR): {', '.join(filters['participants'])}")

    if active_filters:
        print("Active Filters:")
        for f in active_filters:
            print(f)
        print()
    else:
        print("No filters active - showing all chats\n")

def main():
    """List all chats with their IDs and participants."""

    # Generate default filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    default_filename = f"{timestamp}_all_of_my_chats_metadata.txt"
    default_path = str(Path.home() / "Documents" / default_filename)

    parser = argparse.ArgumentParser(
        description="List all your Teams chats with IDs and members (with filtering)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List only 1:1 chats (default)
  python list_chats.py

  # List all chat types
  python list_chats.py --chat-type all

  # List group chats with max 5 participants
  python list_chats.py --chat-type group --max-participants 5

  # Find chats with specific participants
  python list_chats.py --participants "alice@company.com;bob@company.com"

  # Exclude chats with certain topics
  python list_chats.py --topic-exclude "Release;NLL;Standup"

  # Combine filters
  python list_chats.py --chat-type oneOnOne --topic-include "Project;Design"
        """
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        default=default_path,
        help=f"Output file path (default: ~/Documents/{default_filename})"
    )
    parser.add_argument(
        "--console-only",
        action="store_true",
        help="Only output to console, don't write to file"
    )

    # Authentication
    parser.add_argument(
        "--tenant-id",
        default="5a8e2b45-25f8-40ea-a914-b466436e9417",
        help="Azure AD Tenant ID"
    )
    parser.add_argument(
        "--client-id",
        default="0e2ae6dc-ea8b-40b0-8001-61e902fe42a0",
        help="Application (Client) ID"
    )

    # Filtering options
    parser.add_argument(
        "--chat-type",
        default="oneOnOne",
        help="Chat type filter: all, oneOnOne, meeting, group (default: oneOnOne)"
    )
    parser.add_argument(
        "--max-participants",
        type=int,
        default=2,
        help="Maximum number of participants (default: 2)"
    )
    parser.add_argument(
        "--topic-include",
        help="Include chats with topics containing these keywords (semicolon-separated, OR logic)"
    )
    parser.add_argument(
        "--topic-exclude",
        help="Exclude chats with topics containing these keywords (semicolon-separated, OR logic)"
    )
    parser.add_argument(
        "--participants",
        help="Include chats with these participants (semicolon-separated emails, OR logic)"
    )

    args = parser.parse_args()

    # Parse filters
    filters = {
        'chat_types': [args.chat_type] if args.chat_type != 'all' else ['all'],
        'max_participants': args.max_participants,
        'topic_include': [k.strip() for k in args.topic_include.split(';')] if args.topic_include else [],
        'topic_exclude': [k.strip() for k in args.topic_exclude.split(';')] if args.topic_exclude else [],
        'participants': [p.strip() for p in args.participants.split(';')] if args.participants else []
    }

    print("Authenticating...")
    try:
        access_token = authenticate(args.tenant_id, args.client_id, verbose=True)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    print("\nRetrieving your chats (streaming results as they arrive)...")
    print(f"{'='*80}\n")

    # Show active filters
    print_filter_summary(filters)

    client = GraphAPIClient(access_token, verbose=False)

    # Open output file if needed
    output_file = None
    if not args.console_only:
        try:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_file = open(output_path, 'w', encoding='utf-8')
            header = f"{'='*80}\nTeams Chats List\n{'='*80}\n\n"

            # Write filter summary to file
            if filters['chat_types'] != ['all'] or filters['max_participants'] is not None or \
               filters['topic_include'] or filters['topic_exclude'] or filters['participants']:
                header += "Active Filters:\n"
                if filters['chat_types'] != ['all']:
                    header += f"  - Chat types: {', '.join(filters['chat_types'])}\n"
                if filters['max_participants'] is not None:
                    header += f"  - Max participants: {filters['max_participants']}\n"
                if filters['topic_include']:
                    header += f"  - Topic includes (OR): {', '.join(filters['topic_include'])}\n"
                if filters['topic_exclude']:
                    header += f"  - Topic excludes (OR): {', '.join(filters['topic_exclude'])}\n"
                if filters['participants']:
                    header += f"  - Participants (OR): {', '.join(filters['participants'])}\n"
                header += "\n"

            output_file.write(header)
            print(f"Writing to: {output_path.absolute()}\n")
        except Exception as e:
            print(f"Warning: Could not open output file: {e}", file=sys.stderr)
            output_file = None

    chat_count = 0
    filtered_count = 0

    try:
        # Use the internal _paginate method to stream results
        total_processed = 0
        for chat in client._paginate("/me/chats"):
            total_processed += 1
            chat_id = chat.get('id', 'N/A')

            # Get members (this is the slow part, but we do it per-chat as we go)
            members = None
            try:
                members = client.get_chat_members(chat_id)
            except Exception as e:
                print(f"  Warning: Could not get members for chat {chat_id}: {e}")

            # Apply filters
            if not matches_filters(chat, members, filters):
                filtered_count += 1
                continue

            # This chat passed all filters
            chat_count += 1

            # Format and output immediately
            chat_info = format_chat_info(chat_count, chat, members)
            print(chat_info)

            if output_file:
                output_file.write(chat_info + "\n")
                output_file.flush()  # Ensure it's written immediately

        # Footer
        footer = f"\n{'='*80}\n"
        footer += f"Total chats found: {chat_count}\n"
        if filtered_count > 0:
            footer += f"Chats filtered out: {filtered_count}\n"
            footer += f"Total chats processed: {total_processed}\n"
        footer += f"{'='*80}\n"
        footer += "To export a specific chat, use the ID shown above with --chat-id\n"
        footer += f"{'='*80}\n"

        print(footer)
        if output_file:
            output_file.write(footer)

    except Exception as e:
        print(f"\nError retrieving chats: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if output_file:
            output_file.close()
            print(f"\nResults saved to: {Path(args.output).absolute()}")

    return 0

if __name__ == "__main__":
    sys.exit(main())

