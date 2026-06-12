"""Tests for api.auth_manager module."""

import pytest
from unittest.mock import patch, MagicMock

import api.auth_manager as am


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset module-level singletons between tests."""
    with am._lock:
        am._access_token = None
        am._user_info = None
        am._pending_flows.clear()
    yield
    with am._lock:
        am._access_token = None
        am._user_info = None
        am._pending_flows.clear()


class TestGetAuthStatus:
    def test_no_token_no_cache_returns_unauthenticated(self):
        with patch.object(am, "load_token_cache") as mock_cache:
            mock_cache.side_effect = Exception("no cache")
            result = am.get_auth_status()
        assert result == {"authenticated": False}

    def test_valid_in_memory_token(self):
        with am._lock:
            am._access_token = "good_token"
            am._user_info = {
                "displayName": "Alice",
                "mail": "alice@example.com",
                "id": "u1",
            }
        with patch.object(am, "validate_token", return_value=(True, am._user_info)):
            result = am.get_auth_status()
        assert result["authenticated"] is True
        assert result["user_name"] == "Alice"
        assert result["user_email"] == "alice@example.com"

    def test_expired_in_memory_token_falls_back_to_cache(self):
        with am._lock:
            am._access_token = "expired"

        mock_cache = MagicMock()
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = [{"username": "alice"}]
        mock_app.acquire_token_silent.return_value = {"access_token": "refreshed"}

        user_info = {"displayName": "Alice", "mail": "a@b.com", "id": "u1"}

        with patch.object(am, "validate_token") as mock_validate, \
             patch.object(am, "load_token_cache", return_value=mock_cache), \
             patch.object(am, "_build_app", return_value=mock_app), \
             patch.object(am, "save_token_cache"):
            # First call (in-memory) → expired, second (cache) → valid
            mock_validate.side_effect = [(False, None), (True, user_info)]
            result = am.get_auth_status()

        assert result["authenticated"] is True
        assert result["user_name"] == "Alice"

    def test_expired_token_no_accounts_returns_unauthenticated(self):
        with am._lock:
            am._access_token = "expired"

        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []

        with patch.object(am, "validate_token", return_value=(False, None)), \
             patch.object(am, "load_token_cache", return_value=MagicMock()), \
             patch.object(am, "_build_app", return_value=mock_app):
            result = am.get_auth_status()

        assert result["authenticated"] is False


class TestStartDeviceCodeFlow:
    def test_returns_flow_info(self):
        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = {
            "user_code": "CODE1",
            "verification_uri": "https://login.example.com",
            "message": "Go to …",
        }
        with patch.object(am, "_build_app", return_value=mock_app):
            result = am.start_device_code_flow()

        assert result["user_code"] == "CODE1"
        assert "flow_id" in result
        # Flow should be stored
        assert result["flow_id"] in am._pending_flows

    def test_raises_when_no_user_code(self):
        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = {"error": "bad config"}
        with patch.object(am, "_build_app", return_value=mock_app):
            with pytest.raises(RuntimeError, match="Failed to create device flow"):
                am.start_device_code_flow()


class TestPollDeviceCodeFlow:
    def test_unknown_flow_id(self):
        result = am.poll_device_code_flow("nonexistent")
        assert result["status"] == "error"
        assert "Unknown flow_id" in result["error"]

    def test_pending_result(self):
        mock_app = MagicMock()
        mock_app.acquire_token_by_device_flow.return_value = {
            "error": "authorization_pending"
        }
        with am._lock:
            am._pending_flows["f1"] = {
                "app": mock_app,
                "flow": {},
                "cache": MagicMock(),
            }
        result = am.poll_device_code_flow("f1")
        assert result["status"] == "pending"
        # Flow should still be stored
        assert "f1" in am._pending_flows

    def test_success_result(self):
        mock_app = MagicMock()
        mock_app.acquire_token_by_device_flow.return_value = {
            "access_token": "new_tok"
        }
        mock_cache = MagicMock()
        with am._lock:
            am._pending_flows["f2"] = {
                "app": mock_app,
                "flow": {},
                "cache": mock_cache,
            }
        user_info = {"displayName": "Bob", "mail": "bob@example.com"}
        with patch.object(am, "validate_token", return_value=(True, user_info)), \
             patch.object(am, "save_token_cache"):
            result = am.poll_device_code_flow("f2")

        assert result["status"] == "success"
        assert result["user_name"] == "Bob"
        # Flow cleaned up
        assert "f2" not in am._pending_flows
        # Token set
        assert am._access_token == "new_tok"

    def test_hard_error_cleans_up_flow(self):
        mock_app = MagicMock()
        mock_app.acquire_token_by_device_flow.return_value = {
            "error": "expired_token",
            "error_description": "The device code has expired.",
        }
        with am._lock:
            am._pending_flows["f3"] = {
                "app": mock_app,
                "flow": {},
                "cache": MagicMock(),
            }
        result = am.poll_device_code_flow("f3")
        assert result["status"] == "error"
        assert "expired" in result["error"]
        assert "f3" not in am._pending_flows


class TestForceLogin:
    def test_clears_state_and_starts_new_flow(self):
        with am._lock:
            am._access_token = "old_token"
            am._user_info = {"displayName": "Old"}

        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = {
            "user_code": "NEW",
            "verification_uri": "https://login.example.com",
            "message": "Go to …",
        }
        with patch.object(am, "clear_token_cache"), \
             patch.object(am, "_build_app", return_value=mock_app):
            result = am.force_login()

        assert am._access_token is None
        assert result["user_code"] == "NEW"


class TestGetAccessToken:
    def test_returns_in_memory_token(self):
        with am._lock:
            am._access_token = "my_token"
        assert am.get_access_token() == "my_token"

    def test_raises_when_not_authenticated(self):
        with patch.object(am, "get_auth_status", return_value={"authenticated": False}):
            with pytest.raises(RuntimeError, match="Not authenticated"):
                am.get_access_token()

    def test_refreshes_from_cache_if_needed(self):
        # No in-memory token, but get_auth_status succeeds and sets it
        def fake_status():
            with am._lock:
                am._access_token = "refreshed"
            return {"authenticated": True}

        with patch.object(am, "get_auth_status", side_effect=fake_status):
            assert am.get_access_token() == "refreshed"
