"""Tests for API routes (FastAPI endpoints)."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from server import app
from api.models import ActionType, RunStatus


@pytest.fixture
def client():
    return TestClient(app)


# ── Auth routes ───────────────────────────────────────────────────────────


class TestAuthStatus:
    def test_returns_unauthenticated(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.get_auth_status.return_value = {"authenticated": False}
            resp = client.get("/api/auth/status")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False

    def test_returns_authenticated_user(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.get_auth_status.return_value = {
                "authenticated": True,
                "user_name": "Alice",
                "user_email": "alice@example.com",
                "user_id": "u1",
            }
            resp = client.get("/api/auth/status")
        body = resp.json()
        assert body["authenticated"] is True
        assert body["user_name"] == "Alice"
        assert body["user_email"] == "alice@example.com"


class TestAuthDeviceCode:
    def test_start_device_code_flow(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.start_device_code_flow.return_value = {
                "user_code": "ABC123",
                "verification_uri": "https://microsoft.com/devicelogin",
                "message": "Go to …",
                "flow_id": "flow1",
            }
            resp = client.post("/api/auth/device-code")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_code"] == "ABC123"
        assert body["flow_id"] == "flow1"

    def test_start_device_code_flow_error(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.start_device_code_flow.side_effect = RuntimeError("bad creds")
            resp = client.post("/api/auth/device-code")
        assert resp.status_code == 500
        assert "bad creds" in resp.json()["detail"]


class TestAuthDeviceCodePoll:
    def test_poll_pending(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.poll_device_code_flow.return_value = {"status": "pending"}
            resp = client.post(
                "/api/auth/device-code/poll", json={"flow_id": "f1"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_poll_success(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.poll_device_code_flow.return_value = {
                "status": "success",
                "user_name": "Bob",
                "user_email": "bob@example.com",
            }
            resp = client.post(
                "/api/auth/device-code/poll", json={"flow_id": "f1"}
            )
        body = resp.json()
        assert body["status"] == "success"
        assert body["user_name"] == "Bob"

    def test_poll_missing_flow_id(self, client):
        resp = client.post("/api/auth/device-code/poll", json={})
        assert resp.status_code == 422


class TestAuthForceLogin:
    def test_force_login(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.force_login.return_value = {
                "user_code": "XYZ",
                "verification_uri": "https://microsoft.com/devicelogin",
                "message": "Go to …",
                "flow_id": "flow2",
            }
            resp = client.post("/api/auth/force-login")
        assert resp.status_code == 200
        assert resp.json()["flow_id"] == "flow2"

    def test_force_login_error(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.force_login.side_effect = RuntimeError("fail")
            resp = client.post("/api/auth/force-login")
        assert resp.status_code == 500


class TestAuthLogout:
    def test_logout(self, client):
        with patch("api.routes.auth_manager") as mock:
            resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ── Run routes ────────────────────────────────────────────────────────────


class TestRunExportChat:
    def test_unauthenticated(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.get_access_token.side_effect = RuntimeError("Not authenticated")
            resp = client.post(
                "/api/runs/export-chat",
                json={"chat_id": "c1", "since": "2025-01-01"},
            )
        assert resp.status_code == 401

    def test_start_export_single(self, client):
        with patch("api.routes.auth_manager") as auth_mock, \
             patch("api.routes.run_manager") as run_mock:
            auth_mock.get_access_token.return_value = "tok"
            run_mock.start_export_chat.return_value = "run1"
            run_mock.get_run_status.return_value = {
                "action": ActionType.EXPORT_CHAT,
                "status": RunStatus.PENDING,
                "created_at": "2025-06-01T00:00:00Z",
            }
            resp = client.post(
                "/api/runs/export-chat",
                json={"chat_id": "c1", "since": "2025-01-01"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == "run1"
        assert body["action"] == "export_chat"
        assert body["status"] == "pending"
        # Verify chat_ids list was built from chat_id
        call_kwargs = run_mock.start_export_chat.call_args[1]
        assert call_kwargs["chat_ids"] == ["c1"]

    def test_start_export_multiple(self, client):
        with patch("api.routes.auth_manager") as auth_mock, \
             patch("api.routes.run_manager") as run_mock:
            auth_mock.get_access_token.return_value = "tok"
            run_mock.start_export_chat.return_value = "run2"
            run_mock.get_run_status.return_value = {
                "action": ActionType.EXPORT_CHAT,
                "status": RunStatus.PENDING,
                "created_at": "2025-06-01T00:00:00Z",
            }
            resp = client.post(
                "/api/runs/export-chat",
                json={"chat_ids": ["c1", "c2", "c3"], "since": "2025-01-01"},
            )
        assert resp.status_code == 200
        call_kwargs = run_mock.start_export_chat.call_args[1]
        assert call_kwargs["chat_ids"] == ["c1", "c2", "c3"]

    def test_start_export_deduplicates(self, client):
        """chat_id already in chat_ids is not duplicated."""
        with patch("api.routes.auth_manager") as auth_mock, \
             patch("api.routes.run_manager") as run_mock:
            auth_mock.get_access_token.return_value = "tok"
            run_mock.start_export_chat.return_value = "run3"
            run_mock.get_run_status.return_value = {
                "action": ActionType.EXPORT_CHAT,
                "status": RunStatus.PENDING,
                "created_at": "2025-06-01T00:00:00Z",
            }
            resp = client.post(
                "/api/runs/export-chat",
                json={"chat_id": "c1", "chat_ids": ["c1", "c2"], "since": "2025-01-01"},
            )
        assert resp.status_code == 200
        call_kwargs = run_mock.start_export_chat.call_args[1]
        assert call_kwargs["chat_ids"] == ["c1", "c2"]

    def test_validation_missing_chat_ids(self, client):
        resp = client.post("/api/runs/export-chat", json={"since": "2025-01-01"})
        assert resp.status_code == 422

    def test_validation_missing_since(self, client):
        resp = client.post("/api/runs/export-chat", json={"chat_id": "c1"})
        assert resp.status_code == 422


class TestRunListChats:
    def test_unauthenticated(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.get_access_token.side_effect = RuntimeError("Not authenticated")
            resp = client.post("/api/runs/list-chats", json={})
        assert resp.status_code == 401

    def test_start_list_chats(self, client):
        with patch("api.routes.auth_manager") as auth_mock, \
             patch("api.routes.run_manager") as run_mock:
            auth_mock.get_access_token.return_value = "tok"
            run_mock.start_list_chats.return_value = "run2"
            run_mock.get_run_status.return_value = {
                "action": ActionType.LIST_CHATS,
                "status": RunStatus.PENDING,
                "created_at": "2025-06-01T00:00:00Z",
            }
            resp = client.post("/api/runs/list-chats", json={})
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run2"


class TestRunListActiveChats:
    def test_unauthenticated(self, client):
        with patch("api.routes.auth_manager") as mock:
            mock.get_access_token.side_effect = RuntimeError("Not authenticated")
            resp = client.post("/api/runs/list-active-chats", json={})
        assert resp.status_code == 401

    def test_start_list_active_chats(self, client):
        with patch("api.routes.auth_manager") as auth_mock, \
             patch("api.routes.run_manager") as run_mock:
            auth_mock.get_access_token.return_value = "tok"
            run_mock.start_list_active_chats.return_value = "run3"
            run_mock.get_run_status.return_value = {
                "action": ActionType.LIST_ACTIVE_CHATS,
                "status": RunStatus.PENDING,
                "created_at": "2025-06-01T00:00:00Z",
            }
            resp = client.post("/api/runs/list-active-chats", json={})
        assert resp.status_code == 200
        assert resp.json()["action"] == "list_active_chats"


class TestRunStatus:
    def test_status_found(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_run_status.return_value = {
                "action": ActionType.EXPORT_CHAT,
                "status": RunStatus.RUNNING,
                "progress": 50,
                "progress_message": "Downloading…",
                "created_at": "2025-06-01T00:00:00Z",
            }
            resp = client.get("/api/runs/abc123/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["progress"] == 50
        assert body["status"] == "running"

    def test_status_not_found(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_run_status.return_value = None
            resp = client.get("/api/runs/missing/status")
        assert resp.status_code == 404


class TestRunDownload:
    def test_download_not_found(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_result_file_path.return_value = None
            resp = client.get("/api/runs/abc/download")
        assert resp.status_code == 404

    def test_download_success(self, client, tmp_path):
        result_file = tmp_path / "result.json"
        result_file.write_text('{"ok": true}')
        with patch("api.routes.run_manager") as mock:
            mock.get_result_file_path.return_value = result_file
            resp = client.get("/api/runs/abc/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"


class TestRunResults:
    def test_results_found(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_result_grid_data.return_value = {
                "summary": {"total_messages": 5},
                "grid_data": [{"id": "m1"}],
                "grid_total": 5,
            }
            resp = client.get("/api/runs/abc/results")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == "abc"
        assert body["grid_total"] == 5

    def test_results_not_found(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_result_grid_data.return_value = None
            resp = client.get("/api/runs/nope/results")
        assert resp.status_code == 404


class TestRunHistory:
    def test_empty_history(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_all_runs.return_value = []
            resp = client.get("/api/runs/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["runs"] == []
        assert body["total"] == 0

    def test_history_with_items(self, client):
        with patch("api.routes.run_manager") as mock:
            mock.get_all_runs.return_value = [
                {
                    "run_id": "r1",
                    "action": ActionType.EXPORT_CHAT,
                    "status": RunStatus.COMPLETED,
                    "created_at": "2025-06-01T00:00:00Z",
                    "completed_at": "2025-06-01T00:01:00Z",
                    "summary": {"total_messages": 10},
                },
            ]
            resp = client.get("/api/runs/history")
        body = resp.json()
        assert body["total"] == 1
        assert body["runs"][0]["run_id"] == "r1"
