"""Tests for api.run_manager module."""

import json
import threading
import time
from pathlib import Path

import pytest
from unittest.mock import patch

import api.run_manager as rm
from api.models import ActionType, RunStatus


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Point run_manager at a temporary SQLite DB for each test."""
    db_file = tmp_path / "test_runs.db"
    original_db = rm.DB_PATH
    rm.DB_PATH = db_file
    rm._init_db()
    with rm._lock:
        rm._cache.clear()
    yield
    with rm._lock:
        rm._cache.clear()
    rm.DB_PATH = original_db


# ── Internal helpers ──────────────────────────────────────────────────────


class TestUpdateAndGet:
    def test_update_existing_run(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "pending",
            "progress": 0, "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        rm._update("r1", status="running", progress=50)
        info = rm._get("r1")
        assert info["status"] == "running"
        assert info["progress"] == 50

    def test_update_missing_run_is_noop(self):
        rm._update("nonexistent", status="running")
        assert rm._get("nonexistent") is None

    def test_get_returns_copy(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "pending",
            "progress": 0, "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        info = rm._get("r1")
        info["status"] = "hacked"
        assert rm._get("r1")["status"] == "pending"


class TestPersistence:
    def test_data_survives_cache_clear(self):
        """Verify SQLite persistence — data reloads after cache wipe."""
        rm._insert("r1", {
            "run_id": "r1", "action": ActionType.EXPORT_CHAT,
            "status": RunStatus.COMPLETED, "progress": 100,
            "created_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:01:00Z",
            "summary": {"total_messages": 42},
            "grid_data": [{"id": "m1"}],
            "grid_total": 42,
        })
        # Wipe cache, reload from DB
        with rm._lock:
            rm._cache.clear()
        rm._load_cache_from_db()

        info = rm._get("r1")
        assert info is not None
        assert info["status"] == RunStatus.COMPLETED
        assert info["summary"]["total_messages"] == 42
        assert info["grid_data"] == [{"id": "m1"}]

    def test_update_persists_to_db(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "pending",
            "progress": 0, "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        rm._update("r1", status="completed", progress=100)

        # Clear cache and reload
        with rm._lock:
            rm._cache.clear()
        rm._load_cache_from_db()

        info = rm._get("r1")
        assert info["status"] == "completed"
        assert info["progress"] == 100


# ── Public helpers ────────────────────────────────────────────────────────


class TestGetRunStatus:
    def test_returns_none_for_unknown(self):
        assert rm.get_run_status("nope") is None

    def test_returns_info_for_known(self):
        rm._insert("r1", {
            "run_id": "r1", "status": "running", "action": "export_chat",
            "progress": 0, "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        info = rm.get_run_status("r1")
        assert info["status"] == "running"


class TestGetAllRuns:
    def test_empty(self):
        assert rm.get_all_runs() == []

    def test_returns_all_sorted_by_created_at(self):
        rm._insert("r1", {
            "run_id": "r1",
            "action": ActionType.EXPORT_CHAT,
            "status": RunStatus.COMPLETED,
            "progress": 100,
            "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        rm._insert("r2", {
            "run_id": "r2",
            "action": ActionType.LIST_CHATS,
            "status": RunStatus.RUNNING,
            "progress": 50,
            "created_at": "2025-06-01T00:00:00Z",
            "grid_total": 0,
        })
        runs = rm.get_all_runs()
        assert len(runs) == 2
        # Most recent first
        assert runs[0]["run_id"] == "r2"
        assert runs[1]["run_id"] == "r1"


class TestGetResultFilePath:
    def test_returns_none_for_unknown_run(self):
        assert rm.get_result_file_path("nope") is None

    def test_returns_none_when_no_file(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "completed",
            "progress": 100, "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        assert rm.get_result_file_path("r1") is None

    def test_returns_none_when_file_missing(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "completed",
            "progress": 100, "created_at": "2025-01-01T00:00:00Z",
            "result_file": "/tmp/no_such_file.json",
            "grid_total": 0,
        })
        assert rm.get_result_file_path("r1") is None

    def test_returns_path_when_file_exists(self, tmp_path):
        fp = tmp_path / "result.json"
        fp.write_text("{}")
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "completed",
            "progress": 100, "created_at": "2025-01-01T00:00:00Z",
            "result_file": str(fp),
            "grid_total": 0,
        })
        assert rm.get_result_file_path("r1") == fp


class TestGetResultGridData:
    def test_returns_none_for_unknown(self):
        assert rm.get_result_grid_data("nope") is None

    def test_returns_grid_data(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "completed",
            "progress": 100, "created_at": "2025-01-01T00:00:00Z",
            "summary": {"total_messages": 5},
            "grid_data": [{"id": "m1"}],
            "grid_total": 5,
        })
        data = rm.get_result_grid_data("r1")
        assert data["grid_total"] == 5
        assert len(data["grid_data"]) == 1

    def test_defaults_when_fields_missing(self):
        rm._insert("r1", {
            "run_id": "r1", "action": "export_chat", "status": "pending",
            "progress": 0, "created_at": "2025-01-01T00:00:00Z",
            "grid_total": 0,
        })
        data = rm.get_result_grid_data("r1")
        assert data["summary"] == {}
        assert data["grid_data"] == []
        assert data["grid_total"] == 0


# ── _matches_filters ──────────────────────────────────────────────────────


class TestMatchesFilters:
    BASE_FILTERS = {
        "chat_type": "all",
        "max_participants": None,
        "topic_include": [],
        "topic_exclude": [],
        "participants": [],
    }

    def test_all_pass(self):
        chat = {"chatType": "oneOnOne"}
        assert rm._matches_filters(chat, [], self.BASE_FILTERS) is True

    def test_chat_type_filter(self):
        chat = {"chatType": "group"}
        filters = {**self.BASE_FILTERS, "chat_type": "oneOnOne"}
        assert rm._matches_filters(chat, [], filters) is False

    def test_chat_type_match(self):
        chat = {"chatType": "oneOnOne"}
        filters = {**self.BASE_FILTERS, "chat_type": "oneOnOne"}
        assert rm._matches_filters(chat, [], filters) is True

    def test_max_participants_exceeds(self):
        chat = {"chatType": "group"}
        members = [{"displayName": f"u{i}"} for i in range(5)]
        filters = {**self.BASE_FILTERS, "max_participants": 3}
        assert rm._matches_filters(chat, members, filters) is False

    def test_max_participants_within(self):
        chat = {"chatType": "group"}
        members = [{"displayName": "u1"}, {"displayName": "u2"}]
        filters = {**self.BASE_FILTERS, "max_participants": 3}
        assert rm._matches_filters(chat, members, filters) is True

    def test_topic_include_match(self):
        chat = {"chatType": "group", "topic": "Project Alpha"}
        filters = {**self.BASE_FILTERS, "topic_include": ["alpha"]}
        assert rm._matches_filters(chat, [], filters) is True

    def test_topic_include_no_match(self):
        chat = {"chatType": "group", "topic": "Project Beta"}
        filters = {**self.BASE_FILTERS, "topic_include": ["alpha"]}
        assert rm._matches_filters(chat, [], filters) is False

    def test_topic_exclude(self):
        chat = {"chatType": "group", "topic": "Secret Project"}
        filters = {**self.BASE_FILTERS, "topic_exclude": ["secret"]}
        assert rm._matches_filters(chat, [], filters) is False

    def test_participants_filter_match(self):
        chat = {"chatType": "group"}
        members = [{"email": "alice@example.com"}, {"email": "bob@example.com"}]
        filters = {**self.BASE_FILTERS, "participants": ["alice@example.com"]}
        assert rm._matches_filters(chat, members, filters) is True

    def test_participants_filter_no_match(self):
        chat = {"chatType": "group"}
        members = [{"email": "bob@example.com"}]
        filters = {**self.BASE_FILTERS, "participants": ["alice@example.com"]}
        assert rm._matches_filters(chat, members, filters) is False

    def test_topic_include_with_none_topic(self):
        chat = {"chatType": "group", "topic": None}
        filters = {**self.BASE_FILTERS, "topic_include": ["alpha"]}
        assert rm._matches_filters(chat, [], filters) is False


# ── Start functions register runs ─────────────────────────────────────────


class TestStartExportChat:
    def test_registers_run_single_chat(self):
        with patch.object(rm, "_run_export_chat"):
            with patch("threading.Thread") as mock_thread:
                mock_t = mock_thread.return_value
                run_id = rm.start_export_chat(
                    chat_ids=["c1"],
                    since="2025-01-01",
                    until=None,
                    fmt="json",
                    exclude_system_messages=False,
                    only_mine=False,
                )
        info = rm._get(run_id)
        assert info["action"] == ActionType.EXPORT_CHAT
        assert info["status"] == RunStatus.PENDING
        assert info["params"]["chat_ids"] == ["c1"]
        mock_t.start.assert_called_once()

    def test_registers_run_multiple_chats(self):
        with patch.object(rm, "_run_export_chat"):
            with patch("threading.Thread") as mock_thread:
                mock_t = mock_thread.return_value
                run_id = rm.start_export_chat(
                    chat_ids=["c1", "c2", "c3"],
                    since="2025-01-01",
                    until=None,
                    fmt="json",
                    exclude_system_messages=False,
                    only_mine=False,
                )
        info = rm._get(run_id)
        assert info["params"]["chat_ids"] == ["c1", "c2", "c3"]
        mock_t.start.assert_called_once()


class TestStartListChats:
    def test_registers_run(self):
        with patch.object(rm, "_run_list_chats"):
            with patch("threading.Thread") as mock_thread:
                mock_t = mock_thread.return_value
                run_id = rm.start_list_chats(chat_type="group")
        info = rm._get(run_id)
        assert info["action"] == ActionType.LIST_CHATS
        assert info["params"]["chat_type"] == "group"
        mock_t.start.assert_called_once()


class TestStartListActiveChats:
    def test_registers_run(self):
        with patch.object(rm, "_run_list_active_chats"):
            with patch("threading.Thread") as mock_thread:
                mock_t = mock_thread.return_value
                run_id = rm.start_list_active_chats(
                    min_activity_days=90, max_meeting_participants=5
                )
        info = rm._get(run_id)
        assert info["action"] == ActionType.LIST_ACTIVE_CHATS
        assert info["params"]["min_activity_days"] == 90
        mock_t.start.assert_called_once()
