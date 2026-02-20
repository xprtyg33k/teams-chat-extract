"""
Background run / job manager.

Each "run" is identified by a UUID token and executed on a background thread.
Progress and results are stored in an in-memory dict that the status
and download endpoints can query.
"""

import io
import json
import os
import sys
import threading
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cli.teams_chat_export import (
    GraphAPIClient,
    get_chat_messages_filtered,
    get_user_by_identifier,
    find_chats_by_participants,
    html_to_text,
    parse_date,
    process_message,
    export_to_json,
    load_env_file,
)

from api.auth_manager import get_access_token
from api.models import ActionType, RunStatus

# ── In-memory store ───────────────────────────────────────────────────────

_lock = threading.Lock()
_runs: Dict[str, Dict[str, Any]] = {}

# Directory for result files (ephemeral, served via download endpoint)
RESULTS_DIR = Path("./api_results")
RESULTS_DIR.mkdir(exist_ok=True)


def _update(run_id: str, **kwargs: Any) -> None:
    with _lock:
        if run_id in _runs:
            _runs[run_id].update(kwargs)


def _get(run_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return dict(_runs.get(run_id, {})) if run_id in _runs else None


# ── Public helpers ────────────────────────────────────────────────────────

def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    return _get(run_id)


def get_all_runs() -> List[Dict[str, Any]]:
    with _lock:
        return [
            {
                "run_id": rid,
                "action": r["action"],
                "status": r["status"],
                "progress": r.get("progress", 0),
                "progress_message": r.get("progress_message"),
                "created_at": r["created_at"],
                "completed_at": r.get("completed_at"),
                "summary": r.get("summary"),
                "error": r.get("error"),
            }
            for rid, r in sorted(_runs.items(), key=lambda x: x[1]["created_at"], reverse=True)
        ]


def get_result_file_path(run_id: str) -> Optional[Path]:
    info = _get(run_id)
    if not info:
        return None
    fp = info.get("result_file")
    if fp and Path(fp).exists():
        return Path(fp)
    return None


def get_result_grid_data(run_id: str) -> Optional[Dict[str, Any]]:
    info = _get(run_id)
    if not info:
        return None
    return {
        "summary": info.get("summary", {}),
        "grid_data": info.get("grid_data", []),
        "grid_total": info.get("grid_total", 0),
    }


# ── Export Chat ───────────────────────────────────────────────────────────

def start_export_chat(
    chat_id: str,
    since: str,
    until: Optional[str],
    fmt: str,
    exclude_system_messages: bool,
    only_mine: bool,
) -> str:
    run_id = uuid.uuid4().hex
    with _lock:
        _runs[run_id] = {
            "action": ActionType.EXPORT_CHAT,
            "status": RunStatus.PENDING,
            "progress": 0,
            "progress_message": "Queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "params": {
                "chat_id": chat_id,
                "since": since,
                "until": until,
                "format": fmt,
                "exclude_system_messages": exclude_system_messages,
                "only_mine": only_mine,
            },
        }
    t = threading.Thread(target=_run_export_chat, args=(run_id,), daemon=True)
    t.start()
    return run_id


def _run_export_chat(run_id: str) -> None:
    try:
        _update(run_id, status=RunStatus.RUNNING, progress=5, progress_message="Authenticating…")
        token = get_access_token()
        client = GraphAPIClient(token, verbose=False)

        info = _get(run_id)
        params = info["params"]

        since_dt = parse_date(params["since"])
        until_dt = parse_date(params["until"]) if params["until"] else None

        _update(run_id, progress=10, progress_message="Fetching user profile…")
        my_profile = client.get_my_profile()
        my_user_id = my_profile.get("id")

        _update(run_id, progress=15, progress_message="Fetching chat info…")
        chat = client.get_chat_by_id(params["chat_id"])
        members = client.get_chat_members(params["chat_id"])

        # Progress callback
        msg_count = [0]

        def on_page(count: int) -> None:
            msg_count[0] += count
            _update(run_id, progress=min(20 + msg_count[0] // 2, 85),
                    progress_message=f"Downloaded {msg_count[0]} messages…")

        _update(run_id, progress=20, progress_message="Downloading messages…")
        messages, actual_until = get_chat_messages_filtered(
            client,
            params["chat_id"],
            since_dt,
            until_dt,
            params["only_mine"],
            my_user_id,
            params["exclude_system_messages"],
        )

        _update(run_id, progress=85, progress_message="Processing messages…")
        processed = [process_message(m) for m in messages]

        participants = [
            {
                "id": m.get("userId", ""),
                "displayName": m.get("displayName", "Unknown"),
                "userPrincipalName": m.get("email", ""),
            }
            for m in members
        ]

        export_data = {
            "chat_id": params["chat_id"],
            "chat_type": chat.get("chatType", "unknown"),
            "participants": participants,
            "date_range_start": since_dt.isoformat(),
            "date_range_end": actual_until.isoformat(),
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "message_count": len(processed),
            "messages": processed,
        }

        # Write file
        ext = params["format"]
        result_path = RESULTS_DIR / f"{run_id}.{ext}"
        if ext == "json":
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        else:
            # Reuse existing export function (writes to file)
            from cli.teams_chat_export import export_to_txt
            export_to_txt(export_data, str(result_path))

        # Build grid data (top 50 messages)
        sender_counter: Counter = Counter()
        for m in processed:
            sender_counter[m.get("from", {}).get("displayName", "Unknown")] += 1

        grid_data = [
            {
                "id": m["id"],
                "created": m["createdDateTime"],
                "sender": m.get("from", {}).get("displayName", "Unknown"),
                "body_text": m.get("body_text", "")[:300],
                "attachments": len(m.get("attachments", [])),
            }
            for m in processed[:50]
        ]

        summary = {
            "total_messages": len(processed),
            "total_chats": 1,
            "date_range_start": since_dt.isoformat(),
            "date_range_end": actual_until.isoformat(),
            "top_senders": [
                {"name": name, "count": count}
                for name, count in sender_counter.most_common(10)
            ],
            "chat_type": chat.get("chatType", "unknown"),
            "participants": [p["displayName"] for p in participants],
        }

        _update(
            run_id,
            status=RunStatus.COMPLETED,
            progress=100,
            progress_message="Complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result_file=str(result_path),
            summary=summary,
            grid_data=grid_data,
            grid_total=len(processed),
        )

    except Exception as exc:
        _update(
            run_id,
            status=RunStatus.FAILED,
            progress=100,
            progress_message=str(exc),
            error=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


# ── List Chats ────────────────────────────────────────────────────────────

def start_list_chats(
    chat_type: str = "oneOnOne",
    max_participants: Optional[int] = 2,
    topic_include: Optional[List[str]] = None,
    topic_exclude: Optional[List[str]] = None,
    participants_filter: Optional[List[str]] = None,
) -> str:
    run_id = uuid.uuid4().hex
    with _lock:
        _runs[run_id] = {
            "action": ActionType.LIST_CHATS,
            "status": RunStatus.PENDING,
            "progress": 0,
            "progress_message": "Queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "params": {
                "chat_type": chat_type,
                "max_participants": max_participants,
                "topic_include": topic_include or [],
                "topic_exclude": topic_exclude or [],
                "participants": participants_filter or [],
            },
        }
    t = threading.Thread(target=_run_list_chats, args=(run_id,), daemon=True)
    t.start()
    return run_id


def _matches_filters(chat: Dict, members: Optional[list], filters: Dict) -> bool:
    """Replicates filter logic from list_chats.py."""
    chat_type = chat.get("chatType", "unknown")

    if filters["chat_type"] != "all" and chat_type != filters["chat_type"]:
        return False

    if filters["max_participants"] is not None and members:
        if len(members) > filters["max_participants"]:
            return False

    if filters["topic_include"]:
        topic = (chat.get("topic") or "").lower()
        if not any(kw.lower() in topic for kw in filters["topic_include"]):
            return False

    if filters["topic_exclude"]:
        topic = (chat.get("topic") or "").lower()
        if any(kw.lower() in topic for kw in filters["topic_exclude"]):
            return False

    if filters["participants"] and members:
        emails = [m.get("email", "").lower() for m in members]
        if not any(e.lower() in emails for e in filters["participants"]):
            return False

    return True


def _run_list_chats(run_id: str) -> None:
    try:
        _update(run_id, status=RunStatus.RUNNING, progress=5, progress_message="Authenticating…")
        token = get_access_token()
        client = GraphAPIClient(token, verbose=False)

        info = _get(run_id)
        filters = info["params"]

        _update(run_id, progress=10, progress_message="Fetching chats…")

        # Build Graph API query parameters for server-side filtering
        api_params: Dict[str, Any] = {
            "$expand": "members",
            "$top": "50",
        }

        # Apply chatType filter server-side when a specific type is requested
        chat_type = filters.get("chat_type", "all")
        if chat_type and chat_type != "all":
            api_params["$filter"] = f"chatType eq '{chat_type}'"

        results: List[Dict[str, Any]] = []
        total_processed = 0

        for chat in client._paginate("/me/chats", api_params):
            total_processed += 1
            chat_id = chat.get("id", "")

            # Members come from $expand (avoids per-chat API call)
            members = chat.get("members")
            if members is None:
                try:
                    members = client.get_chat_members(chat_id)
                except Exception:
                    members = []

            # Apply remaining filters that Graph API doesn't support natively
            if not _matches_filters(chat, members, filters):
                continue

            topic = chat.get("topic")
            if not topic and members:
                names = [m.get("displayName", "Unknown") for m in members if m.get("displayName")]
                topic = ", ".join(names) if names else "(No name)"

            results.append({
                "chat_id": chat_id,
                "chat_type": chat.get("chatType", "unknown"),
                "topic": topic,
                "display_name": topic or "(No name)",
                "member_count": len(members) if members else 0,
            })

            if total_processed % 5 == 0:
                _update(run_id, progress=min(10 + total_processed, 90),
                        progress_message=f"Processed {total_processed} chats, {len(results)} match…")

        # Write file
        result_path = RESULTS_DIR / f"{run_id}.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({"chats": results, "total": len(results)}, f, indent=2, ensure_ascii=False)

        grid_data = results[:50]
        summary = {"total_chats": len(results)}

        _update(
            run_id,
            status=RunStatus.COMPLETED,
            progress=100,
            progress_message="Complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result_file=str(result_path),
            summary=summary,
            grid_data=grid_data,
            grid_total=len(results),
        )

    except Exception as exc:
        _update(
            run_id,
            status=RunStatus.FAILED,
            progress=100,
            progress_message=str(exc),
            error=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


# ── List Active Chats ────────────────────────────────────────────────────

def start_list_active_chats(
    min_activity_days: int = 365,
    max_meeting_participants: int = 10,
) -> str:
    run_id = uuid.uuid4().hex
    with _lock:
        _runs[run_id] = {
            "action": ActionType.LIST_ACTIVE_CHATS,
            "status": RunStatus.PENDING,
            "progress": 0,
            "progress_message": "Queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "params": {
                "min_activity_days": min_activity_days,
                "max_meeting_participants": max_meeting_participants,
            },
        }
    t = threading.Thread(target=_run_list_active_chats, args=(run_id,), daemon=True)
    t.start()
    return run_id


def _run_list_active_chats(run_id: str) -> None:
    try:
        _update(run_id, status=RunStatus.RUNNING, progress=5, progress_message="Authenticating…")
        token = get_access_token()
        client = GraphAPIClient(token, verbose=False)

        info = _get(run_id)
        params = info["params"]
        min_days = params["min_activity_days"]
        max_meeting = params["max_meeting_participants"]

        _update(run_id, progress=10, progress_message="Fetching chats…")

        results: List[Dict[str, Any]] = []
        total = 0

        api_params = {
            "$select": "id,chatType,topic,lastMessagePreview",
            "$expand": "members",
            "$top": "50",
        }
        for chat in client._paginate("/me/chats", api_params):
            total += 1
            chat_id = chat.get("id", "")
            chat_type = chat.get("chatType", "unknown")

            if chat_type == "channel":
                continue

            # Members come from $expand (avoids per-chat API call)
            members = chat.get("members")
            if members is None:
                try:
                    members = client.get_chat_members(chat_id)
                except Exception:
                    continue

            if chat_type == "meeting" and max_meeting and members and len(members) > max_meeting:
                continue

            # Last activity
            last_activity = None
            preview = chat.get("lastMessagePreview")
            if preview and isinstance(preview, dict):
                dt_str = preview.get("createdDateTime")
                if dt_str:
                    try:
                        last_activity = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

            if last_activity and min_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=min_days)
                if last_activity < cutoff:
                    continue

            topic = chat.get("topic")
            if not topic and members:
                names = [m.get("displayName", "Unknown") for m in members if m.get("displayName")]
                topic = ", ".join(names) if names else "(No name)"

            results.append({
                "chat_id": chat_id,
                "chat_type": chat_type,
                "display_name": topic or "(No name)",
                "member_count": len(members) if members else 0,
                "last_activity": last_activity.isoformat() if last_activity else None,
            })

            if total % 5 == 0:
                _update(run_id, progress=min(10 + total, 90),
                        progress_message=f"Processed {total} chats, {len(results)} active…")

        # Sort by last activity descending
        results.sort(key=lambda x: x.get("last_activity") or "", reverse=True)

        # Write file
        result_path = RESULTS_DIR / f"{run_id}.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({"chats": results, "total": len(results)}, f, indent=2, ensure_ascii=False)

        grid_data = results[:50]
        summary = {"total_chats": len(results)}

        _update(
            run_id,
            status=RunStatus.COMPLETED,
            progress=100,
            progress_message="Complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result_file=str(result_path),
            summary=summary,
            grid_data=grid_data,
            grid_total=len(results),
        )

    except Exception as exc:
        _update(
            run_id,
            status=RunStatus.FAILED,
            progress=100,
            progress_message=str(exc),
            error=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
