"""
Pydantic models for API request/response schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportFormat(str, Enum):
    JSON = "json"
    TXT = "txt"


class ActionType(str, Enum):
    EXPORT_CHAT = "export_chat"
    LIST_CHATS = "list_chats"
    LIST_ACTIVE_CHATS = "list_active_chats"


# ── Auth ──────────────────────────────────────────────────────────────────

class AuthStatusResponse(BaseModel):
    authenticated: bool
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_id: Optional[str] = None


class DeviceCodeResponse(BaseModel):
    user_code: str
    verification_uri: str
    message: str
    flow_id: str


class DeviceCodePollRequest(BaseModel):
    flow_id: str


class DeviceCodePollResponse(BaseModel):
    status: str  # "pending", "success", "error"
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    error: Optional[str] = None


class ForceLoginRequest(BaseModel):
    pass


# ── Run / Job ─────────────────────────────────────────────────────────────

class ExportChatRequest(BaseModel):
    chat_id: str
    since: str
    until: Optional[str] = None
    format: ExportFormat = ExportFormat.JSON
    exclude_system_messages: bool = False
    only_mine: bool = False


class ListChatsRequest(BaseModel):
    chat_type: str = "oneOnOne"
    max_participants: Optional[int] = 2
    topic_include: Optional[List[str]] = None
    topic_exclude: Optional[List[str]] = None
    participants: Optional[List[str]] = None


class ListActiveChatsRequest(BaseModel):
    min_activity_days: int = 365
    max_meeting_participants: int = 10


class RunResponse(BaseModel):
    run_id: str
    action: ActionType
    status: RunStatus
    created_at: str


class RunStatusResponse(BaseModel):
    run_id: str
    action: ActionType
    status: RunStatus
    progress: int = 0  # 0-100
    progress_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class RunHistoryItem(BaseModel):
    run_id: str
    action: ActionType
    status: RunStatus
    created_at: str
    completed_at: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class RunHistoryResponse(BaseModel):
    runs: List[RunHistoryItem]
    total: int


# ── Results ───────────────────────────────────────────────────────────────

class ChatListItem(BaseModel):
    chat_id: str
    chat_type: str
    topic: Optional[str] = None
    display_name: str
    member_count: Optional[int] = None
    last_activity: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    created: str
    sender: str
    body_text: str
    attachments: int = 0


class ResultSummary(BaseModel):
    total_messages: Optional[int] = None
    total_chats: Optional[int] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    top_senders: Optional[List[Dict[str, Any]]] = None
    items: Optional[List[Dict[str, Any]]] = None  # top 50 for grid


class ResultsResponse(BaseModel):
    run_id: str
    summary: ResultSummary
    grid_data: List[Dict[str, Any]]
    grid_total: int
