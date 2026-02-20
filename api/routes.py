"""
FastAPI REST routes.

All endpoints follow a clean RESTful contract.
Runs (jobs) return a token (run_id) that the front-end can poll.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api import auth_manager, run_manager
from api.models import (
    AuthStatusResponse,
    DeviceCodePollRequest,
    DeviceCodePollResponse,
    DeviceCodeResponse,
    ExportChatRequest,
    ListActiveChatsRequest,
    ListChatsRequest,
    ResultsResponse,
    RunHistoryResponse,
    RunResponse,
    RunStatusResponse,
)

router = APIRouter(prefix="/api")

# ── Auth routes ───────────────────────────────────────────────────────────


@router.get("/auth/status", response_model=AuthStatusResponse)
def auth_status():
    """Check whether the current server session has a valid token."""
    return auth_manager.get_auth_status()


@router.post("/auth/device-code", response_model=DeviceCodeResponse)
def auth_device_code():
    """Start device-code login flow."""
    try:
        return auth_manager.start_device_code_flow()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/device-code/poll", response_model=DeviceCodePollResponse)
def auth_device_code_poll(body: DeviceCodePollRequest):
    """Poll for device-code flow completion."""
    return auth_manager.poll_device_code_flow(body.flow_id)


@router.post("/auth/force-login", response_model=DeviceCodeResponse)
def auth_force_login():
    """Clear cached tokens and start fresh login."""
    try:
        return auth_manager.force_login()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/logout")
def auth_logout():
    """Log out (clear server-side token)."""
    auth_manager.force_login()  # clears state
    return {"ok": True}


# ── Run routes ────────────────────────────────────────────────────────────


@router.post("/runs/export-chat", response_model=RunResponse)
def run_export_chat(body: ExportChatRequest):
    """Start a chat-export run and return its run_id."""
    try:
        auth_manager.get_access_token()
    except RuntimeError:
        raise HTTPException(status_code=401, detail="Not authenticated")

    run_id = run_manager.start_export_chat(
        chat_id=body.chat_id,
        since=body.since,
        until=body.until,
        fmt=body.format.value,
        exclude_system_messages=body.exclude_system_messages,
        only_mine=body.only_mine,
    )
    info = run_manager.get_run_status(run_id)
    return {
        "run_id": run_id,
        "action": info["action"],
        "status": info["status"],
        "created_at": info["created_at"],
    }


@router.post("/runs/list-chats", response_model=RunResponse)
def run_list_chats(body: ListChatsRequest):
    """Start a list-chats run."""
    try:
        auth_manager.get_access_token()
    except RuntimeError:
        raise HTTPException(status_code=401, detail="Not authenticated")

    run_id = run_manager.start_list_chats(
        chat_type=body.chat_type,
        max_participants=body.max_participants,
        topic_include=body.topic_include,
        topic_exclude=body.topic_exclude,
        participants_filter=body.participants,
    )
    info = run_manager.get_run_status(run_id)
    return {
        "run_id": run_id,
        "action": info["action"],
        "status": info["status"],
        "created_at": info["created_at"],
    }


@router.post("/runs/list-active-chats", response_model=RunResponse)
def run_list_active_chats(body: ListActiveChatsRequest):
    """Start a list-active-chats run."""
    try:
        auth_manager.get_access_token()
    except RuntimeError:
        raise HTTPException(status_code=401, detail="Not authenticated")

    run_id = run_manager.start_list_active_chats(
        min_activity_days=body.min_activity_days,
        max_meeting_participants=body.max_meeting_participants,
    )
    info = run_manager.get_run_status(run_id)
    return {
        "run_id": run_id,
        "action": info["action"],
        "status": info["status"],
        "created_at": info["created_at"],
    }


@router.get("/runs/{run_id}/status", response_model=RunStatusResponse)
def run_status(run_id: str):
    """Poll the status of a run."""
    info = run_manager.get_run_status(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": run_id,
        "action": info["action"],
        "status": info["status"],
        "progress": info.get("progress", 0),
        "progress_message": info.get("progress_message"),
        "created_at": info["created_at"],
        "completed_at": info.get("completed_at"),
        "error": info.get("error"),
        "summary": info.get("summary"),
    }


@router.get("/runs/{run_id}/download")
def run_download(run_id: str):
    """Download the result file for a completed run."""
    fp = run_manager.get_result_file_path(run_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(
        path=str(fp),
        filename=fp.name,
        media_type="application/octet-stream",
    )


@router.get("/runs/{run_id}/results")
def run_results(run_id: str):
    """Get grid-ready results for display (summary + top items)."""
    data = run_manager.get_result_grid_data(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, **data}


@router.get("/runs/history", response_model=RunHistoryResponse)
def run_history():
    """Get run history."""
    all_runs = run_manager.get_all_runs()
    return {
        "runs": [
            {
                "run_id": r["run_id"],
                "action": r["action"],
                "status": r["status"],
                "created_at": r["created_at"],
                "completed_at": r.get("completed_at"),
                "summary": r.get("summary"),
            }
            for r in all_runs
        ],
        "total": len(all_runs),
    }
