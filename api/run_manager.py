"""
Background run / job manager.

Each "run" is identified by a UUID token and executed on a background thread.
Run metadata is persisted to a local SQLite database so history survives
server restarts.  An in-memory cache keeps hot reads (progress polling) fast.
"""

import json
import os
import sqlite3
import sys
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cli.teams_chat_export import (
    GraphAPIClient,
    format_meeting_transcript_txt,
    get_chat_messages_filtered,
    get_user_by_identifier,
    find_chats_by_participants,
    html_to_text,
    parse_webvtt_transcript,
    parse_date,
    process_message,
    export_to_json,
    load_env_file,
)

from api.auth_manager import get_access_token
from api.models import ActionType, RunStatus

# ── Paths ─────────────────────────────────────────────────────────────────

RESULTS_DIR = Path("./api_results")
RESULTS_DIR.mkdir(exist_ok=True)

DB_PATH = Path("./runs.db")

# ── SQLite persistence layer ─────────────────────────────────────────────

_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db() -> None:
    """Create the runs table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id       TEXT PRIMARY KEY,
                action       TEXT NOT NULL,
                status       TEXT NOT NULL,
                progress     INTEGER NOT NULL DEFAULT 0,
                progress_message TEXT,
                created_at   TEXT NOT NULL,
                completed_at TEXT,
                error        TEXT,
                result_file  TEXT,
                params       TEXT,
                summary      TEXT,
                grid_data    TEXT,
                grid_total   INTEGER NOT NULL DEFAULT 0
            )
        """)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict, deserializing JSON fields."""
    d = dict(row)
    for field in ("params", "summary", "grid_data"):
        if d.get(field):
            d[field] = json.loads(d[field])
        elif field == "grid_data":
            d[field] = []
        elif field == "summary":
            d[field] = {}
    return d


def _persist(run_id: str, data: Dict[str, Any]) -> None:
    """Upsert a run record into SQLite and update the in-memory cache."""
    row = dict(data)
    for field in ("params", "summary", "grid_data"):
        if field in row and not isinstance(row[field], str):
            row[field] = json.dumps(row[field], ensure_ascii=False)

    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO runs
                (run_id, action, status, progress, progress_message,
                 created_at, completed_at, error, result_file,
                 params, summary, grid_data, grid_total)
            VALUES
                (:run_id, :action, :status, :progress, :progress_message,
                 :created_at, :completed_at, :error, :result_file,
                 :params, :summary, :grid_data, :grid_total)
            ON CONFLICT(run_id) DO UPDATE SET
                action=excluded.action,
                status=excluded.status,
                progress=excluded.progress,
                progress_message=excluded.progress_message,
                completed_at=excluded.completed_at,
                error=excluded.error,
                result_file=excluded.result_file,
                params=excluded.params,
                summary=excluded.summary,
                grid_data=excluded.grid_data,
                grid_total=excluded.grid_total
        """, {
            "run_id": run_id,
            "action": row.get("action", ""),
            "status": row.get("status", ""),
            "progress": row.get("progress", 0),
            "progress_message": row.get("progress_message"),
            "created_at": row.get("created_at", ""),
            "completed_at": row.get("completed_at"),
            "error": row.get("error"),
            "result_file": row.get("result_file"),
            "params": row.get("params"),
            "summary": row.get("summary"),
            "grid_data": row.get("grid_data"),
            "grid_total": row.get("grid_total", 0),
        })


def _load_cache_from_db() -> None:
    """Populate the in-memory cache from SQLite on startup."""
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC"
        ).fetchall()
    with _lock:
        for row in rows:
            _cache[row["run_id"]] = _row_to_dict(row)


# Initialise on import
_init_db()
_load_cache_from_db()


# ── Internal helpers ──────────────────────────────────────────────────────


def _update(run_id: str, **kwargs: Any) -> None:
    with _lock:
        if run_id not in _cache:
            return
        _cache[run_id].update(kwargs)
        data = dict(_cache[run_id])
    _persist(run_id, data)


def _get(run_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return dict(_cache[run_id]) if run_id in _cache else None


def _insert(run_id: str, data: Dict[str, Any]) -> None:
    """Insert a brand-new run into cache + DB."""
    with _lock:
        _cache[run_id] = data
    _persist(run_id, data)


# ── Public helpers ────────────────────────────────────────────────────────

def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    return _get(run_id)


def get_all_runs() -> List[Dict[str, Any]]:
    with _lock:
        runs = list(_cache.values())
    return [
        {
            "run_id": r.get("run_id", rid),
            "action": r["action"],
            "status": r["status"],
            "progress": r.get("progress", 0),
            "progress_message": r.get("progress_message"),
            "params": r.get("params"),
            "created_at": r["created_at"],
            "completed_at": r.get("completed_at"),
            "summary": r.get("summary"),
            "error": r.get("error"),
        }
        for rid, r in sorted(
            {r.get("run_id", ""): r for r in runs}.items(),
            key=lambda x: x[1]["created_at"],
            reverse=True,
        )
    ]


def delete_run(run_id: str) -> bool:
    """Delete a single run from cache, DB, and disk."""
    with _lock:
        data = _cache.pop(run_id, None)
    if data is None:
        with _get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT result_file FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return False
        data = dict(row)
    with _get_conn() as conn:
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
    result_file = data.get("result_file")
    if result_file:
        p = Path(result_file)
        if p.exists():
            p.unlink()
    return True


def clear_all_runs() -> int:
    """Delete all runs from cache, DB, and remove all result files."""
    with _get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.execute("DELETE FROM runs")
    with _lock:
        _cache.clear()
    for f in RESULTS_DIR.iterdir():
        if f.is_file():
            f.unlink()
    return count


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
        "action": info.get("action"),
        "params": info.get("params"),
        "summary": info.get("summary", {}),
        "grid_data": info.get("grid_data", []),
        "grid_total": info.get("grid_total", 0),
    }


# ── Export Chat ───────────────────────────────────────────────────────────

MAX_PARALLEL_EXPORTS = 4


def start_export_chat(
    chat_ids: List[str],
    since: str,
    until: Optional[str],
    fmt: str,
    exclude_system_messages: bool,
    only_mine: bool,
) -> str:
    run_id = uuid.uuid4().hex
    data = {
        "run_id": run_id,
        "action": ActionType.EXPORT_CHAT,
        "status": RunStatus.PENDING,
        "progress": 0,
        "progress_message": "Queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "result_file": None,
        "params": {
            "chat_ids": chat_ids,
            "since": since,
            "until": until,
            "format": fmt,
            "exclude_system_messages": exclude_system_messages,
            "only_mine": only_mine,
        },
        "summary": None,
        "grid_data": [],
        "grid_total": 0,
    }
    _insert(run_id, data)
    t = threading.Thread(target=_run_export_chat, args=(run_id,), daemon=True)
    t.start()
    return run_id


def _export_single_chat(
    client: "GraphAPIClient",
    chat_id: str,
    since_dt: datetime,
    until_dt: Optional[datetime],
    only_mine: bool,
    my_user_id: str,
    exclude_system_messages: bool,
) -> Dict[str, Any]:
    """Export a single chat, returning its export_data dict."""
    chat = client.get_chat_by_id(chat_id)
    members = client.get_chat_members(chat_id)

    messages, actual_until = get_chat_messages_filtered(
        client,
        chat_id,
        since_dt,
        until_dt,
        only_mine,
        my_user_id,
        exclude_system_messages,
    )

    processed = [process_message(m) for m in messages]

    participants = [
        {
            "id": m.get("userId", ""),
            "displayName": m.get("displayName", "Unknown"),
            "userPrincipalName": m.get("email", ""),
        }
        for m in members
    ]

    return {
        "chat_id": chat_id,
        "chat_type": chat.get("chatType", "unknown"),
        "participants": participants,
        "date_range_start": since_dt.isoformat(),
        "date_range_end": actual_until.isoformat(),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "message_count": len(processed),
        "messages": processed,
    }


def _run_export_chat(run_id: str) -> None:
    try:
        _update(run_id, status=RunStatus.RUNNING, progress=5, progress_message="Authenticating…")
        token = get_access_token()
        client = GraphAPIClient(token, verbose=False)

        info = _get(run_id)
        params = info["params"]
        chat_ids = params["chat_ids"]
        total_chats = len(chat_ids)

        since_dt = parse_date(params["since"])
        until_dt = parse_date(params["until"]) if params["until"] else None

        _update(run_id, progress=10, progress_message="Fetching user profile…")
        my_profile = client.get_my_profile()
        my_user_id = my_profile.get("id")

        # ── Export chats (parallel when > 1) ──────────────────────────
        all_export_data: List[Dict[str, Any]] = []
        completed_count = [0]
        errors: List[str] = []
        _progress_lock = threading.Lock()

        def _do_export(cid: str) -> Optional[Dict[str, Any]]:
            # Each worker gets its own client to avoid sharing requests.Session
            worker_client = GraphAPIClient(token, verbose=False)
            try:
                result = _export_single_chat(
                    worker_client, cid, since_dt, until_dt,
                    params["only_mine"], my_user_id,
                    params["exclude_system_messages"],
                )
                # Inject chat_id into each message for grid attribution
                for msg in result.get("messages", []):
                    msg["chat_id"] = cid
                with _progress_lock:
                    completed_count[0] += 1
                    pct = 15 + int(70 * completed_count[0] / total_chats)
                    _update(
                        run_id, progress=min(pct, 85),
                        progress_message=f"Exported {completed_count[0]}/{total_chats} chats…",
                    )
                return result
            except Exception as exc:
                with _progress_lock:
                    completed_count[0] += 1
                    errors.append(f"{cid}: {exc}")
                return None

        if total_chats == 1:
            _update(run_id, progress=15, progress_message="Exporting chat…")
            result = _do_export(chat_ids[0])
            if result:
                all_export_data.append(result)
        else:
            _update(run_id, progress=15,
                    progress_message=f"Exporting {total_chats} chats in parallel…")
            workers = min(total_chats, MAX_PARALLEL_EXPORTS)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_do_export, cid): cid for cid in chat_ids}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        all_export_data.append(result)

        if not all_export_data:
            raise RuntimeError(
                f"All exports failed: {'; '.join(errors)}" if errors
                else "No messages found"
            )

        # ── Aggregate results ─────────────────────────────────────────
        _update(run_id, progress=85, progress_message="Processing results…")

        all_processed = []
        all_participants_set: Dict[str, Dict] = {}
        for ed in all_export_data:
            all_processed.extend(ed["messages"])
            for p in ed["participants"]:
                all_participants_set[p["id"]] = p

        sender_counter: Counter = Counter()
        for m in all_processed:
            sender_counter[m.get("from", {}).get("displayName", "Unknown")] += 1

        grid_data = [
            {
                "chat_id": m.get("chat_id", ""),
                "id": m["id"],
                "created": m["createdDateTime"],
                "sender": m.get("from", {}).get("displayName", "Unknown"),
                "body_text": m.get("body_text", "")[:300],
                "attachments": len(m.get("attachments", [])),
            }
            for m in all_processed[:50]
        ]
        # For single-chat exports, omit redundant chat_id column
        if total_chats == 1:
            for row in grid_data:
                row.pop("chat_id", None)

        # Determine date range across all exports
        all_starts = [ed["date_range_start"] for ed in all_export_data]
        all_ends = [ed["date_range_end"] for ed in all_export_data]

        all_participants = list(all_participants_set.values())

        summary = {
            "total_messages": len(all_processed),
            "total_chats": len(all_export_data),
            "date_range_start": min(all_starts),
            "date_range_end": max(all_ends),
            "top_senders": [
                {"name": name, "count": count}
                for name, count in sender_counter.most_common(10)
            ],
            "chat_type": (
                all_export_data[0]["chat_type"]
                if total_chats == 1
                else "multiple"
            ),
            "participants": [p["displayName"] for p in all_participants],
        }
        if errors:
            summary["errors"] = errors

        # ── Write output file ─────────────────────────────────────────
        ext = params["format"]
        result_path = RESULTS_DIR / f"{run_id}.{ext}"

        if total_chats == 1:
            output = all_export_data[0]
        else:
            output = {
                "export_count": len(all_export_data),
                "date_range_start": min(all_starts),
                "date_range_end": max(all_ends),
                "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                "total_messages": len(all_processed),
                "chats": all_export_data,
            }

        if ext == "json":
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
        else:
            from cli.teams_chat_export import export_to_txt
            if total_chats == 1:
                export_to_txt(output, str(result_path))
            else:
                with open(result_path, "w", encoding="utf-8") as f:
                    for ed in all_export_data:
                        f.write(f"\n{'='*60}\n")
                        f.write(f"Chat: {ed['chat_id']}\n")
                        f.write(f"Type: {ed['chat_type']}\n")
                        f.write(f"Messages: {ed['message_count']}\n")
                        f.write(f"{'='*60}\n\n")
                        for m in ed["messages"]:
                            ts = m.get("createdDateTime", "")
                            sender = m.get("from", {}).get("displayName", "Unknown")
                            body = m.get("body_text", "")
                            f.write(f"[{ts}] {sender}: {body}\n")

        _update(
            run_id,
            status=RunStatus.COMPLETED,
            progress=100,
            progress_message="Complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result_file=str(result_path),
            summary=summary,
            grid_data=grid_data,
            grid_total=len(all_processed),
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


# ── Export Meeting Transcript ─────────────────────────────────────────────

def start_export_meeting_transcript(
    meeting_identifier: str,
    identifier_type: str,
    transcript_id: Optional[str],
    fmt: str,
) -> str:
    run_id = uuid.uuid4().hex
    data = {
        "run_id": run_id,
        "action": ActionType.EXPORT_MEETING_TRANSCRIPT,
        "status": RunStatus.PENDING,
        "progress": 0,
        "progress_message": "Queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "result_file": None,
        "params": {
            "meeting_identifier": meeting_identifier,
            "identifier_type": identifier_type,
            "transcript_id": transcript_id,
            "format": fmt,
        },
        "summary": None,
        "grid_data": [],
        "grid_total": 0,
    }
    _insert(run_id, data)
    t = threading.Thread(target=_run_export_meeting_transcript, args=(run_id,), daemon=True)
    t.start()
    return run_id


def _resolve_online_meeting(client: GraphAPIClient, identifier_type: str, meeting_identifier: str) -> Dict[str, Any]:
    if identifier_type == "online_meeting_id":
        return client.get_online_meeting_by_id(meeting_identifier)
    if identifier_type == "join_meeting_id":
        return client.get_online_meeting_by_join_meeting_id(meeting_identifier)
    return client.get_online_meeting_by_join_web_url(meeting_identifier)


def _select_transcript(transcripts: List[Dict[str, Any]], transcript_id: Optional[str]) -> Dict[str, Any]:
    if transcript_id:
        for transcript in transcripts:
            if transcript.get("id") == transcript_id:
                return transcript
        raise RuntimeError(f"Transcript not found: {transcript_id}")
    return sorted(
        transcripts,
        key=lambda t: t.get("createdDateTime") or "",
        reverse=True,
    )[0]


def _run_export_meeting_transcript(run_id: str) -> None:
    try:
        _update(run_id, status=RunStatus.RUNNING, progress=5, progress_message="Authenticating…")
        token = get_access_token()
        client = GraphAPIClient(token, verbose=False)

        info = _get(run_id)
        params = info["params"]

        _update(run_id, progress=15, progress_message="Resolving meeting…")
        meeting = _resolve_online_meeting(
            client,
            params["identifier_type"],
            params["meeting_identifier"],
        )

        _update(run_id, progress=35, progress_message="Listing transcripts…")
        transcripts = client.list_online_meeting_transcripts(meeting["id"])
        if not transcripts:
            raise RuntimeError("No transcripts found for this meeting")

        transcript = _select_transcript(transcripts, params.get("transcript_id"))

        _update(run_id, progress=55, progress_message="Downloading transcript content…")
        raw_content, content_type = client.get_transcript_content(meeting["id"], transcript["id"])

        metadata: Optional[Dict[str, Any]] = None
        metadata_error: Optional[str] = None
        try:
            metadata = client.get_transcript_metadata_content(meeting["id"], transcript["id"])
        except Exception as exc:
            metadata_error = str(exc)

        _update(run_id, progress=75, progress_message="Processing transcript…")
        cues = parse_webvtt_transcript(raw_content)
        if not cues:
            raise RuntimeError("Transcript downloaded but no cues were found in the content")

        grid_data = [
            {
                "start": cue.get("start"),
                "end": cue.get("end"),
                "speaker": cue.get("speaker") or "Unknown Speaker",
                "text": cue.get("text", "")[:300],
            }
            for cue in cues[:50]
        ]

        summary = {
            "total_messages": len(cues),
            "chat_type": "meeting_transcript",
            "date_range_start": meeting.get("startDateTime") or transcript.get("createdDateTime"),
            "date_range_end": meeting.get("endDateTime") or transcript.get("endDateTime"),
        }
        if metadata_error:
            summary["metadata_warning"] = metadata_error

        output = {
            "export_type": "meeting_transcript",
            "meeting": {
                "id": meeting.get("id"),
                "subject": meeting.get("subject"),
                "joinWebUrl": meeting.get("joinWebUrl"),
                "startDateTime": meeting.get("startDateTime"),
                "endDateTime": meeting.get("endDateTime"),
            },
            "transcript": {
                "id": transcript.get("id"),
                "createdDateTime": transcript.get("createdDateTime"),
                "endDateTime": transcript.get("endDateTime"),
                "contentType": content_type,
            },
            "cue_count": len(cues),
            "cues": cues,
        }
        if metadata is not None:
            output["metadata"] = metadata
        if metadata_error:
            output["metadata_error"] = metadata_error

        ext = params["format"]
        result_path = RESULTS_DIR / f"{run_id}.{ext}"
        if ext == "json":
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
        else:
            with open(result_path, "w", encoding="utf-8") as f:
                f.write(format_meeting_transcript_txt(output["meeting"], output["transcript"], cues))

        _update(
            run_id,
            status=RunStatus.COMPLETED,
            progress=100,
            progress_message="Complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result_file=str(result_path),
            summary=summary,
            grid_data=grid_data,
            grid_total=len(cues),
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
    data = {
        "run_id": run_id,
        "action": ActionType.LIST_CHATS,
        "status": RunStatus.PENDING,
        "progress": 0,
        "progress_message": "Queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "result_file": None,
        "params": {
            "chat_type": chat_type,
            "max_participants": max_participants,
            "topic_include": topic_include or [],
            "topic_exclude": topic_exclude or [],
            "participants": participants_filter or [],
        },
        "summary": None,
        "grid_data": [],
        "grid_total": 0,
    }
    _insert(run_id, data)
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
    data = {
        "run_id": run_id,
        "action": ActionType.LIST_ACTIVE_CHATS,
        "status": RunStatus.PENDING,
        "progress": 0,
        "progress_message": "Queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "result_file": None,
        "params": {
            "min_activity_days": min_activity_days,
            "max_meeting_participants": max_meeting_participants,
        },
        "summary": None,
        "grid_data": [],
        "grid_total": 0,
    }
    _insert(run_id, data)
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
