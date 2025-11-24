#!/usr/bin/env python3
"""
Diagnostic script to list all your Teams chats and their IDs.
This helps identify the correct chat ID format for the export tool.
"""

import argparse
import sys
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

def main():
    """List all chats with their IDs and participants."""

    parser = argparse.ArgumentParser(
        description="List all your Teams chats with IDs and members",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output",
        "-o",
        default="All_my_chats.txt",
        help="Output file path (default: All_my_chats.txt)"
    )
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
    parser.add_argument(
        "--console-only",
        action="store_true",
        help="Only output to console, don't write to file"
    )

    args = parser.parse_args()

    print("Authenticating...")
    try:
        access_token = authenticate(args.tenant_id, args.client_id, verbose=True)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    print("\nRetrieving your chats (streaming results as they arrive)...")
    print(f"{'='*80}\n")

    client = GraphAPIClient(access_token, verbose=False)

    # Open output file if needed
    output_file = None
    if not args.console_only:
        try:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_file = open(output_path, 'w', encoding='utf-8')
            header = f"{'='*80}\nTeams Chats List\n{'='*80}\n\n"
            output_file.write(header)
            print(f"Writing to: {output_path.absolute()}\n")
        except Exception as e:
            print(f"Warning: Could not open output file: {e}", file=sys.stderr)
            output_file = None

    chat_count = 0

    try:
        # Use the internal _paginate method to stream results
        for chat in client._paginate("/me/chats"):
            chat_count += 1
            chat_id = chat.get('id', 'N/A')

            # Get members (this is the slow part, but we do it per-chat as we go)
            members = None
            try:
                members = client.get_chat_members(chat_id)
            except Exception as e:
                print(f"  Warning: Could not get members for chat {chat_id}: {e}")

            # Format and output immediately
            chat_info = format_chat_info(chat_count, chat, members)
            print(chat_info)

            if output_file:
                output_file.write(chat_info + "\n")
                output_file.flush()  # Ensure it's written immediately

        # Footer
        footer = f"\n{'='*80}\n"
        footer += f"Total chats found: {chat_count}\n"
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

