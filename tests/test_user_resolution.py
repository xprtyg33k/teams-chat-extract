"""Tests for user resolution and chat discovery."""

import pytest
from unittest.mock import Mock, MagicMock
from teams_chat_export import (
    get_user_by_identifier,
    find_chats_by_participants,
    NotFoundError,
    TeamsExportError
)


class TestUserResolution:
    """Test user resolution functionality."""
    
    def test_get_user_by_identifier_single_match(self):
        """Test resolving user with single match."""
        client = Mock()
        client.verbose = False
        client.search_users.return_value = [
            {
                "id": "user123",
                "displayName": "Test User",
                "userPrincipalName": "test@example.com"
            }
        ]
        
        result = get_user_by_identifier(client, "Test User")
        
        assert result["id"] == "user123"
        assert result["displayName"] == "Test User"
        client.search_users.assert_called_once_with("Test User")
    
    def test_get_user_by_identifier_not_found(self):
        """Test resolving non-existent user."""
        client = Mock()
        client.verbose = False
        client.search_users.return_value = []
        
        with pytest.raises(NotFoundError) as exc_info:
            get_user_by_identifier(client, "Nonexistent User")
        
        assert "User not found" in str(exc_info.value)
    
    def test_get_user_by_identifier_multiple_exact_match(self):
        """Test resolving user with multiple matches but exact match exists."""
        client = Mock()
        client.verbose = False
        client.search_users.return_value = [
            {
                "id": "user123",
                "displayName": "Test User",
                "userPrincipalName": "test@example.com"
            },
            {
                "id": "user456",
                "displayName": "Test User 2",
                "userPrincipalName": "test2@example.com"
            }
        ]
        
        result = get_user_by_identifier(client, "Test User")
        
        # Should return exact match
        assert result["id"] == "user123"
        assert result["displayName"] == "Test User"
    
    def test_get_user_by_identifier_ambiguous(self):
        """Test resolving user with ambiguous matches."""
        client = Mock()
        client.verbose = False
        client.search_users.return_value = [
            {
                "id": "user123",
                "displayName": "John Smith",
                "userPrincipalName": "john.smith@example.com"
            },
            {
                "id": "user456",
                "displayName": "John Smithson",
                "userPrincipalName": "john.smithson@example.com"
            }
        ]
        
        with pytest.raises(TeamsExportError) as exc_info:
            get_user_by_identifier(client, "John")
        
        assert "Multiple users found" in str(exc_info.value)
        assert "john.smith@example.com" in str(exc_info.value)


class TestChatDiscovery:
    """Test chat discovery functionality."""
    
    def test_find_chats_by_participants_single_match(self):
        """Test finding chat with matching participants."""
        client = Mock()
        client.verbose = False
        
        # Mock get_my_chats
        client.get_my_chats.return_value = [
            {"id": "chat1", "chatType": "oneOnOne"},
            {"id": "chat2", "chatType": "group"}
        ]
        
        # Mock get_chat_members
        def mock_get_members(chat_id):
            if chat_id == "chat1":
                return [
                    {"userId": "user1", "displayName": "User 1"},
                    {"userId": "user2", "displayName": "User 2"}
                ]
            else:
                return [
                    {"userId": "user1", "displayName": "User 1"},
                    {"userId": "user3", "displayName": "User 3"}
                ]
        
        client.get_chat_members.side_effect = mock_get_members
        
        # Find chats with user1 and user2
        result = find_chats_by_participants(client, ["user1", "user2"])
        
        assert len(result) == 1
        assert result[0]["id"] == "chat1"
        assert "members" in result[0]
    
    def test_find_chats_by_participants_no_match(self):
        """Test finding chat with no matching participants."""
        client = Mock()
        client.verbose = False
        
        client.get_my_chats.return_value = [
            {"id": "chat1", "chatType": "oneOnOne"}
        ]
        
        client.get_chat_members.return_value = [
            {"userId": "user1", "displayName": "User 1"},
            {"userId": "user2", "displayName": "User 2"}
        ]
        
        # Find chats with user3 and user4 (not in any chat)
        result = find_chats_by_participants(client, ["user3", "user4"])
        
        assert len(result) == 0
    
    def test_find_chats_by_participants_multiple_matches(self):
        """Test finding multiple chats with matching participants."""
        client = Mock()
        client.verbose = False
        
        client.get_my_chats.return_value = [
            {"id": "chat1", "chatType": "group"},
            {"id": "chat2", "chatType": "group"}
        ]
        
        # Both chats have user1 and user2
        client.get_chat_members.return_value = [
            {"userId": "user1", "displayName": "User 1"},
            {"userId": "user2", "displayName": "User 2"},
            {"userId": "user3", "displayName": "User 3"}
        ]
        
        result = find_chats_by_participants(client, ["user1", "user2"])
        
        assert len(result) == 2

