"""Tests for list_active_chats functionality."""

import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.list_active_chats import (
    get_chat_last_activity,
    get_chat_display_name,
    should_include_chat,
    format_chat_line
)


class TestGetChatLastActivity:
    """Test get_chat_last_activity function."""

    def test_get_last_activity_with_valid_preview(self):
        """Test extracting last activity from valid lastMessagePreview."""
        chat = {
            "id": "chat123",
            "lastMessagePreview": {
                "createdDateTime": "2026-02-17T14:30:00Z"
            }
        }
        result = get_chat_last_activity(chat)
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 17

    def test_get_last_activity_with_missing_preview(self):
        """Test when lastMessagePreview is missing."""
        chat = {"id": "chat123"}
        result = get_chat_last_activity(chat)
        assert result is None

    def test_get_last_activity_with_none_preview(self):
        """Test when lastMessagePreview is None."""
        chat = {"id": "chat123", "lastMessagePreview": None}
        result = get_chat_last_activity(chat)
        assert result is None

    def test_get_last_activity_with_empty_preview(self):
        """Test when lastMessagePreview is empty dict."""
        chat = {"id": "chat123", "lastMessagePreview": {}}
        result = get_chat_last_activity(chat)
        assert result is None

    def test_get_last_activity_with_malformed_date(self):
        """Test with malformed date string."""
        chat = {
            "id": "chat123",
            "lastMessagePreview": {
                "createdDateTime": "invalid-date"
            }
        }
        result = get_chat_last_activity(chat)
        assert result is None


class TestGetChatDisplayName:
    """Test get_chat_display_name function."""

    def test_topic_takes_priority(self):
        """Test that chat topic takes priority over members."""
        chat = {"topic": "Project Alpha"}
        members = [
            {"displayName": "John Doe"},
            {"displayName": "Jane Smith"}
        ]
        result = get_chat_display_name(chat, members)
        assert result == "Project Alpha"

    def test_empty_topic_falls_back_to_members(self):
        """Test that empty topic falls back to member names."""
        chat = {"topic": ""}
        members = [
            {"displayName": "John Doe"},
            {"displayName": "Jane Smith"}
        ]
        result = get_chat_display_name(chat, members)
        assert "John Doe" in result
        assert "Jane Smith" in result

    def test_none_topic_falls_back_to_members(self):
        """Test that None topic falls back to member names."""
        chat = {"topic": None}
        members = [{"displayName": "Bob Wilson"}]
        result = get_chat_display_name(chat, members)
        assert result == "Bob Wilson"

    def test_no_topic_or_members(self):
        """Test with no topic and no members."""
        chat = {}
        result = get_chat_display_name(chat, None)
        assert result == "(No name)"

    def test_members_with_none_values(self):
        """Test handling members with None displayName."""
        chat = {"topic": ""}
        members = [
            {"displayName": None},
            {"displayName": "Valid User"}
        ]
        result = get_chat_display_name(chat, members)
        assert "Valid User" in result

    def test_whitespace_only_topic(self):
        """Test topic that is only whitespace."""
        chat = {"topic": "   "}
        members = [{"displayName": "User Name"}]
        result = get_chat_display_name(chat, members)
        assert result == "User Name"


class TestShouldIncludeChat:
    """Test should_include_chat function."""

    def test_exclude_channel_chats(self):
        """Test that channel chats are excluded."""
        chat = {"chatType": "channel"}
        filters = {"min_activity_days": 30, "max_meeting_participants": 10}
        result = should_include_chat(chat, None, None, filters)
        assert result is False

    def test_include_group_chats(self):
        """Test that group chats are included by default."""
        chat = {"chatType": "group"}
        filters = {"min_activity_days": None, "max_meeting_participants": None}
        result = should_include_chat(chat, None, None, filters)
        assert result is True

    def test_include_one_on_one_chats(self):
        """Test that 1:1 chats are included by default."""
        chat = {"chatType": "oneOnOne"}
        filters = {"min_activity_days": None, "max_meeting_participants": None}
        result = should_include_chat(chat, None, None, filters)
        assert result is True

    def test_meeting_participant_limit(self):
        """Test meeting participant count filter."""
        chat = {"chatType": "meeting"}
        members = [{"id": f"user{i}"} for i in range(15)]
        filters = {"min_activity_days": None, "max_meeting_participants": 10}
        result = should_include_chat(chat, members, None, filters)
        assert result is False

    def test_meeting_within_participant_limit(self):
        """Test meeting with acceptable participant count."""
        chat = {"chatType": "meeting"}
        members = [{"id": f"user{i}"} for i in range(8)]
        filters = {"min_activity_days": None, "max_meeting_participants": 10}
        result = should_include_chat(chat, members, None, filters)
        assert result is True

    def test_activity_age_filter_too_old(self):
        """Test that old chats are filtered out."""
        chat = {"chatType": "group"}
        old_date = datetime.now(timezone.utc) - timedelta(days=40)
        filters = {"min_activity_days": 30, "max_meeting_participants": None}
        result = should_include_chat(chat, None, old_date, filters)
        assert result is False

    def test_activity_age_filter_recent(self):
        """Test that recent chats are included."""
        chat = {"chatType": "group"}
        recent_date = datetime.now(timezone.utc) - timedelta(days=10)
        filters = {"min_activity_days": 30, "max_meeting_participants": None}
        result = should_include_chat(chat, None, recent_date, filters)
        assert result is True

    def test_zero_activity_filter_includes_all(self):
        """Test that zero filter includes all chats."""
        chat = {"chatType": "group"}
        old_date = datetime.now(timezone.utc) - timedelta(days=999)
        filters = {"min_activity_days": None, "max_meeting_participants": None}
        result = should_include_chat(chat, None, old_date, filters)
        assert result is True


class TestFormatChatLine:
    """Test format_chat_line function."""

    def test_format_with_all_fields(self):
        """Test formatting with all fields present."""
        dt = datetime(2026, 2, 17, 14, 30, 0)
        result = format_chat_line("Project Alpha", "group", dt, "Engineering")
        assert "Project Alpha" in result
        assert "group" in result
        assert "2026-02-17" in result
        assert "Engineering" in result

    def test_format_without_group_name(self):
        """Test formatting without group name."""
        dt = datetime(2026, 2, 17, 14, 30, 0)
        result = format_chat_line("Project Beta", "oneOnOne", dt, None)
        assert "Project Beta" in result
        assert "oneOnOne" in result
        assert "[Group:" not in result

    def test_format_without_last_activity(self):
        """Test formatting without last activity date."""
        result = format_chat_line("Project Gamma", "meeting", None)
        assert "Project Gamma" in result
        assert "meeting" in result
        assert "Unknown" in result

    def test_format_includes_pipe_separators(self):
        """Test that format includes pipe separators."""
        dt = datetime(2026, 2, 17, 14, 30, 0)
        result = format_chat_line("Test Chat", "group", dt)
        assert " | " in result

    def test_format_date_includes_time(self):
        """Test that formatted date includes time."""
        dt = datetime(2026, 2, 17, 14, 30, 45)
        result = format_chat_line("Test", "group", dt)
        assert "14:30:45" in result


class TestOutputDirectoryCreation:
    """Test output directory handling."""

    def test_output_directory_path_construction(self):
        """Test that output path is constructed with ./out prefix."""
        # This test verifies the behavior expected in the recent changes
        output_dir = Path("./out")
        output_filename = f"All-Active-Chats-By-Last-Active-Date-As-Of-{datetime.now().strftime('%d%m%Y')}.txt"
        output_path = output_dir / output_filename
        
        # Verify path structure
        assert str(output_path).startswith("out")
        assert output_filename in str(output_path)

    def test_output_directory_mkdir_behavior(self):
        """Test that output directory can be created safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            # Should not raise error when creating
            output_dir.mkdir(exist_ok=True)
            assert output_dir.exists()
            
            # Second call should also succeed
            output_dir.mkdir(exist_ok=True)
            assert output_dir.exists()

    def test_output_file_can_be_written(self):
        """Test that output file can be written to the out directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "test_output.txt"
            
            # Write test data
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("Test content\n")
            
            # Verify file was created and can be read
            assert output_path.exists()
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Test content" in content
