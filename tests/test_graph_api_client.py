"""Tests for Graph API client."""

import pytest
import responses
from cli.teams_chat_export import (
    GraphAPIClient,
    PermissionError,
    NotFoundError,
    MaxRetriesExceeded,
    GRAPH_API_BASE_URL,
    extract_join_meeting_id,
    parse_webvtt_transcript,
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

    @responses.activate
    def test_get_online_meeting_by_id(self, client):
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users/me/onlineMeetings/meeting123",
            json={"id": "meeting123", "joinWebUrl": "https://teams.microsoft.com/l/meetup-join/..."},
            status=200,
        )

        meeting = client.get_online_meeting_by_id("meeting123")
        assert meeting["id"] == "meeting123"

    @responses.activate
    def test_get_online_meeting_by_join_web_url(self, client):
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users/me/onlineMeetings",
            json={"value": [{"id": "meeting123"}]},
            status=200,
        )

        meeting = client.get_online_meeting_by_join_web_url(
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/thread.v2/0?context=%7b%7d"
        )
        assert meeting["id"] == "meeting123"

    @responses.activate
    def test_get_online_meeting_by_join_web_url_not_found(self, client):
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users/me/onlineMeetings",
            json={"value": []},
            status=200,
        )

        with pytest.raises(NotFoundError):
            client.get_online_meeting_by_join_web_url("https://teams.microsoft.com/l/meetup-join/missing")

    @responses.activate
    def test_list_online_meeting_transcripts(self, client):
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users/me/onlineMeetings/meeting123/transcripts",
            json={
                "value": [
                    {"id": "transcript1", "contentCorrelationId": "corr1"},
                    {"id": "transcript2", "contentCorrelationId": "corr2"},
                ]
            },
            status=200,
        )

        transcripts = client.list_online_meeting_transcripts("meeting123")
        assert len(transcripts) == 2
        assert transcripts[0]["id"] == "transcript1"

    @responses.activate
    def test_get_transcript_content(self, client):
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users/me/onlineMeetings/meeting123/transcripts/transcript1/content",
            body="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello world\n",
            content_type="text/vtt",
            status=200,
        )

        content, content_type = client.get_transcript_content("meeting123", "transcript1")
        assert "WEBVTT" in content
        assert content_type.startswith("text/vtt")

    @responses.activate
    def test_get_transcript_metadata_content(self, client):
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE_URL}/users/me/onlineMeetings/meeting123/transcripts/transcript1/metadataContent",
            json={"utterances": [{"speaker": "Alice"}]},
            status=200,
        )

        metadata = client.get_transcript_metadata_content("meeting123", "transcript1")
        assert metadata["utterances"][0]["speaker"] == "Alice"


class TestMeetingHelpers:
    def test_extract_join_meeting_id_from_query_string(self):
        join_url = (
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc%40thread.v2/0"
            "?context=%7b%7d&meetingId=123456789"
        )
        assert extract_join_meeting_id(join_url) == "123456789"

    def test_parse_webvtt_transcript(self):
        vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Alice>First line

00:00:04.000 --> 00:00:06.000
<v Bob>Second line
"""
        cues = parse_webvtt_transcript(vtt)
        assert len(cues) == 2
        assert cues[0]["speaker"] == "Alice"
        assert cues[1]["text"] == "Second line"
