"""Tests for Graph API client."""

import pytest
import responses
from teams_chat_export import (
    GraphAPIClient,
    PermissionError,
    NotFoundError,
    MaxRetriesExceeded,
    GRAPH_API_BASE_URL
)


class TestGraphAPIClient:
    """Test Graph API client functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return GraphAPIClient("test_token", verbose=False)
    
    @responses.activate
    def test_make_request_success(self, client):
        """Test successful API request."""
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me",
            json={"id": "user123", "displayName": "Test User"},
            status=200
        )
        
        result = client._make_request("/me")
        assert result["id"] == "user123"
        assert result["displayName"] == "Test User"
    
    @responses.activate
    def test_make_request_404(self, client):
        """Test 404 not found error."""
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/chats/invalid",
            status=404
        )
        
        with pytest.raises(NotFoundError):
            client._make_request("/chats/invalid")
    
    @responses.activate
    def test_make_request_403(self, client):
        """Test 403 permission error."""
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me/chats",
            json={
                "error": {
                    "message": "Insufficient privileges"
                }
            },
            status=403
        )
        
        with pytest.raises(PermissionError) as exc_info:
            client._make_request("/me/chats")
        assert "Insufficient privileges" in str(exc_info.value)
    
    @responses.activate
    def test_make_request_429_retry(self, client):
        """Test rate limiting with retry."""
        # First request: rate limited
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me/chats",
            status=429,
            headers={"Retry-After": "1"}
        )
        # Second request: success
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me/chats",
            json={"value": []},
            status=200
        )
        
        result = client._make_request("/me/chats")
        assert result == {"value": []}
        assert len(responses.calls) == 2
    
    @responses.activate
    def test_pagination(self, client):
        """Test pagination handling."""
        # First page
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me/chats",
            json={
                "value": [{"id": "chat1"}, {"id": "chat2"}],
                "@odata.nextLink": f"{GRAPH_API_BASE_URL}/me/chats?$skip=2"
            },
            status=200
        )
        # Second page
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me/chats",
            json={
                "value": [{"id": "chat3"}]
            },
            status=200
        )
        
        items = list(client._paginate("/me/chats"))
        assert len(items) == 3
        assert items[0]["id"] == "chat1"
        assert items[1]["id"] == "chat2"
        assert items[2]["id"] == "chat3"
    
    @responses.activate
    def test_get_my_chats(self, client):
        """Test getting user's chats."""
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/me/chats",
            json={
                "value": [
                    {"id": "chat1", "chatType": "oneOnOne"},
                    {"id": "chat2", "chatType": "group"}
                ]
            },
            status=200
        )
        
        chats = client.get_my_chats()
        assert len(chats) == 2
        assert chats[0]["id"] == "chat1"
        assert chats[1]["chatType"] == "group"
    
    @responses.activate
    def test_get_chat_members(self, client):
        """Test getting chat members."""
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/chats/chat123/members",
            json={
                "value": [
                    {"userId": "user1", "displayName": "User 1"},
                    {"userId": "user2", "displayName": "User 2"}
                ]
            },
            status=200
        )
        
        members = client.get_chat_members("chat123")
        assert len(members) == 2
        assert members[0]["userId"] == "user1"
    
    @responses.activate
    def test_search_users_by_email(self, client):
        """Test searching users by email."""
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users",
            json={
                "value": [
                    {
                        "id": "user123",
                        "displayName": "Test User",
                        "userPrincipalName": "test@example.com"
                    }
                ]
            },
            status=200
        )
        
        users = client.search_users("test@example.com")
        assert len(users) == 1
        assert users[0]["userPrincipalName"] == "test@example.com"

