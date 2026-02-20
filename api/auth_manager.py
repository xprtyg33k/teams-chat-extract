"""
Authentication manager for the Web UI.

Manages MSAL device-code flow lifecycle, token caching,
and session validation.  All state is stored in a module-level
singleton so it survives across HTTP requests.
"""

import os
import threading
import uuid
from typing import Any, Dict, Optional, Tuple

import msal
import requests

from cli.teams_chat_export import (
    GRAPH_API_BASE_URL,
    SCOPES,
    TOKEN_CACHE_FILE,
    load_env_file,
    load_token_cache,
    save_token_cache,
    clear_token_cache,
    validate_token,
)

# ── Module-level state ────────────────────────────────────────────────────

_lock = threading.Lock()
_access_token: Optional[str] = None
_user_info: Optional[Dict[str, Any]] = None
_pending_flows: Dict[str, Dict[str, Any]] = {}  # flow_id → {app, flow, cache}


def _get_credentials() -> Tuple[str, str]:
    """Return (tenant_id, client_id) from environment."""
    load_env_file()
    tenant_id = os.environ.get("TEAMS_TENANT_ID", "")
    client_id = os.environ.get("TEAMS_CLIENT_ID", "")
    if not tenant_id or not client_id:
        raise RuntimeError(
            "TEAMS_TENANT_ID and TEAMS_CLIENT_ID must be set in .env or environment."
        )
    return tenant_id, client_id


def _build_app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    tenant_id, client_id = _get_credentials()
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    return msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=cache,
    )


# ── Public API ────────────────────────────────────────────────────────────


def get_auth_status() -> Dict[str, Any]:
    """
    Return current authentication status.
    Tries the in-memory token first, then the file-based cache.
    """
    global _access_token, _user_info

    with _lock:
        # 1. Already have a good token?
        if _access_token:
            is_valid, info = validate_token(_access_token)
            if is_valid:
                if info:
                    _user_info = info
                return {
                    "authenticated": True,
                    "user_name": (_user_info or {}).get("displayName"),
                    "user_email": (_user_info or {}).get("mail")
                        or (_user_info or {}).get("userPrincipalName"),
                    "user_id": (_user_info or {}).get("id"),
                }

        # 2. Try silent acquisition from file cache
        try:
            cache = load_token_cache()
            app = _build_app(cache)
            accounts = app.get_accounts()
            if accounts:
                result = app.acquire_token_silent(SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    is_valid, info = validate_token(result["access_token"])
                    if is_valid:
                        _access_token = result["access_token"]
                        _user_info = info
                        save_token_cache(cache)
                        return {
                            "authenticated": True,
                            "user_name": (info or {}).get("displayName"),
                            "user_email": (info or {}).get("mail")
                                or (info or {}).get("userPrincipalName"),
                            "user_id": (info or {}).get("id"),
                        }
        except Exception:
            pass

    return {"authenticated": False}


def start_device_code_flow() -> Dict[str, str]:
    """
    Initiate a device-code flow.

    Returns dict with ``user_code``, ``verification_uri``, ``message``, ``flow_id``.
    """
    cache = msal.SerializableTokenCache()
    app = _build_app(cache)
    flow = app.initiate_device_flow(scopes=SCOPES)

    if "user_code" not in flow:
        raise RuntimeError("Failed to create device flow – check tenant/client IDs.")

    flow_id = uuid.uuid4().hex
    with _lock:
        _pending_flows[flow_id] = {"app": app, "flow": flow, "cache": cache}

    return {
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri", "https://microsoft.com/devicelogin"),
        "message": flow["message"],
        "flow_id": flow_id,
    }


def poll_device_code_flow(flow_id: str) -> Dict[str, Any]:
    """
    Attempt to complete a pending device-code flow.

    Returns ``{"status": "pending" | "success" | "error", ...}``.
    """
    global _access_token, _user_info

    with _lock:
        entry = _pending_flows.get(flow_id)
    if not entry:
        return {"status": "error", "error": "Unknown flow_id"}

    app: msal.PublicClientApplication = entry["app"]
    flow = entry["flow"]
    cache: msal.SerializableTokenCache = entry["cache"]

    result = app.acquire_token_by_device_flow(flow, exit_condition=lambda flow: True)

    if "access_token" in result:
        with _lock:
            _access_token = result["access_token"]
            _pending_flows.pop(flow_id, None)
        save_token_cache(cache)

        is_valid, info = validate_token(result["access_token"])
        if info:
            with _lock:
                _user_info = info
        return {
            "status": "success",
            "user_name": (info or {}).get("displayName"),
            "user_email": (info or {}).get("mail") or (info or {}).get("userPrincipalName"),
        }

    error = result.get("error", "")
    if error == "authorization_pending":
        return {"status": "pending"}

    # Clean up on hard error
    with _lock:
        _pending_flows.pop(flow_id, None)
    return {"status": "error", "error": result.get("error_description", error)}


def force_login() -> Dict[str, str]:
    """Clear all cached tokens and start a fresh device-code flow."""
    global _access_token, _user_info

    with _lock:
        _access_token = None
        _user_info = None
    clear_token_cache()
    return start_device_code_flow()


def get_access_token() -> str:
    """
    Return a valid access token, raising if not authenticated.
    """
    global _access_token

    with _lock:
        if _access_token:
            return _access_token

    # Try cache
    status = get_auth_status()
    if status.get("authenticated"):
        with _lock:
            if _access_token:
                return _access_token

    raise RuntimeError("Not authenticated. Please log in first.")
