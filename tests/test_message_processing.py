"""Tests for message processing functionality."""

import pytest
from datetime import datetime, timezone
from cli.teams_chat_export import process_message


class TestMessageProcessing:
    """Test message processing function."""
    
    def test_process_simple_message(self):
        """Test processing a simple message."""
        raw_message = {
            "id": "msg123",
            "createdDateTime": "2025-06-01T10:00:00Z",
            "lastModifiedDateTime": "2025-06-01T10:00:00Z",
            "from": {
                "user": {
                    "id": "user123",
                    "displayName": "Test User"
                }
            },
            "body": {
                "content": "<div>Hello, world!</div>",
                "contentType": "html"
            },
            "attachments": []
        }
        
        result = process_message(raw_message)
        
        assert result["id"] == "msg123"
        assert result["createdDateTime"] == "2025-06-01T10:00:00Z"
        assert result["from"]["id"] == "user123"
        assert result["from"]["displayName"] == "Test User"
        assert "Hello, world!" in result["body_text"]
        assert result["body_html"] == "<div>Hello, world!</div>"
        assert result["attachments"] == []
    
    def test_process_message_with_attachments(self):
        """Test processing message with attachments."""
        raw_message = {
            "id": "msg123",
            "createdDateTime": "2025-06-01T10:00:00Z",
            "lastModifiedDateTime": "2025-06-01T10:00:00Z",
            "from": {
                "user": {
                    "id": "user123",
                    "displayName": "Test User"
                }
            },
            "body": {
                "content": "<div>Check this file</div>",
                "contentType": "html"
            },
            "attachments": [
                {
                    "name": "document.pdf",
                    "contentType": "application/pdf",
                    "contentUrl": "https://example.com/file.pdf"
                },
                {
                    "name": "image.png",
                    "contentType": "image/png"
                }
            ]
        }
        
        result = process_message(raw_message)
        
        assert len(result["attachments"]) == 2
        assert result["attachments"][0]["name"] == "document.pdf"
        assert result["attachments"][0]["type"] == "application/pdf"
        assert result["attachments"][0]["contentUrl"] == "https://example.com/file.pdf"
        assert result["attachments"][1]["name"] == "image.png"
        assert "contentUrl" not in result["attachments"][1]
    
    def test_process_message_missing_from(self):
        """Test processing message with missing from field."""
        raw_message = {
            "id": "msg123",
            "createdDateTime": "2025-06-01T10:00:00Z",
            "lastModifiedDateTime": "2025-06-01T10:00:00Z",
            "body": {
                "content": "<div>System message</div>",
                "contentType": "html"
            },
            "attachments": []
        }
        
        result = process_message(raw_message)
        
        assert result["from"]["id"] == ""
        assert result["from"]["displayName"] == "Unknown"
    
    def test_process_message_empty_body(self):
        """Test processing message with empty body."""
        raw_message = {
            "id": "msg123",
            "createdDateTime": "2025-06-01T10:00:00Z",
            "lastModifiedDateTime": "2025-06-01T10:00:00Z",
            "from": {
                "user": {
                    "id": "user123",
                    "displayName": "Test User"
                }
            },
            "body": {},
            "attachments": []
        }
        
        result = process_message(raw_message)
        
        assert result["body_text"] == ""
        assert result["body_html"] == ""
    
    def test_process_message_complex_html(self):
        """Test processing message with complex HTML."""
        raw_message = {
            "id": "msg123",
            "createdDateTime": "2025-06-01T10:00:00Z",
            "lastModifiedDateTime": "2025-06-01T10:00:00Z",
            "from": {
                "user": {
                    "id": "user123",
                    "displayName": "Test User"
                }
            },
            "body": {
                "content": """
                <div>
                    <div><strong>Important:</strong> Meeting at 3pm</div>
                    <ul>
                        <li>Bring laptop</li>
                        <li>Review slides</li>
                    </ul>
                </div>
                """,
                "contentType": "html"
            },
            "attachments": []
        }
        
        result = process_message(raw_message)
        
        assert "Important" in result["body_text"]
        assert "Meeting at 3pm" in result["body_text"]
        assert "Bring laptop" in result["body_text"]
        assert "Review slides" in result["body_text"]

