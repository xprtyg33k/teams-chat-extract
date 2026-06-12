/**
 * business.js – Business / orchestration layer.
 *
 * The UI calls ONLY this module.  It composes API calls, manages polling,
 * persists to storage, and fires callbacks the UI can subscribe to.
 */

import * as api from "./api.js";
import * as store from "./storage.js";

// ── Event emitter (tiny) ──────────────────────────────────────────────────

const _listeners = {};

export function on(event, fn) {
  (_listeners[event] ||= []).push(fn);
}

export function off(event, fn) {
  if (_listeners[event]) {
    _listeners[event] = _listeners[event].filter((f) => f !== fn);
  }
}

function _emit(event, data) {
  for (const fn of _listeners[event] || []) {
    try {
      fn(data);
    } catch (e) {
      console.error(`[business] listener error on "${event}":`, e);
    }
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────

let _authInfo = null;
let _pollTimer = null;
let _authHeartbeat = null;
const AUTH_HEARTBEAT_MS = 60 * 60 * 1000; // 1 hour

/**
 * Check if user is authenticated (server-side token valid).
 * Emits "auth:changed".  Also sets up an hourly heartbeat.
 */
export async function checkAuth() {
  try {
    const status = await api.getAuthStatus();
    if (status.authenticated) {
      _authInfo = {
        user_name: status.user_name,
        user_email: status.user_email,
        user_id: status.user_id,
      };
      store.saveAuthInfo(_authInfo);
      _emit("auth:changed", { authenticated: true, ..._authInfo });
      _scheduleAuthHeartbeat();
      return true;
    }
  } catch (e) {
    console.warn("[business] checkAuth error:", e);
  }
  _authInfo = null;
  _emit("auth:changed", { authenticated: false });
  return false;
}

/**
 * Schedule a low-frequency auth heartbeat (once per hour).
 * Replaces any previous heartbeat.
 */
function _scheduleAuthHeartbeat() {
  if (_authHeartbeat) clearInterval(_authHeartbeat);
  _authHeartbeat = setInterval(async () => {
    try {
      const status = await api.getAuthStatus();
      if (!status.authenticated) {
        _authInfo = null;
        _emit("auth:changed", { authenticated: false });
        clearInterval(_authHeartbeat);
        _authHeartbeat = null;
      }
    } catch (_) {
      /* ignore transient network errors */
    }
  }, AUTH_HEARTBEAT_MS);
}

/**
 * Start the device-code login flow.
 * Emits "auth:device-code" with { user_code, verification_uri, message }.
 * Then polls automatically, emitting "auth:changed" on success.
 */
export async function startLogin() {
  stopLoginPoll();
  const dcInfo = await api.startDeviceCodeFlow();
  _emit("auth:device-code", dcInfo);
  _startPolling(dcInfo.flow_id);
}

/**
 * Force a fresh login (clears server cache).
 */
export async function forceLogin() {
  stopLoginPoll();
  store.clearAuthInfo();
  const dcInfo = await api.forceLogin();
  _emit("auth:device-code", dcInfo);
  _startPolling(dcInfo.flow_id);
}

export async function doLogout() {
  stopLoginPoll();
  if (_authHeartbeat) {
    clearInterval(_authHeartbeat);
    _authHeartbeat = null;
  }
  _authInfo = null;
  store.clearAuthInfo();
  await api.logout();
  _emit("auth:changed", { authenticated: false });
}

function _startPolling(flowId) {
  stopLoginPoll();
  _pollTimer = setInterval(async () => {
    try {
      const res = await api.pollDeviceCode(flowId);
      if (res.status === "success") {
        stopLoginPoll();
        await checkAuth();
      } else if (res.status === "error") {
        stopLoginPoll();
        _emit("auth:error", { error: res.error || "Login failed" });
      }
      // "pending" → keep polling
    } catch (e) {
      console.warn("[business] poll error:", e);
    }
  }, 3000);
}

export function stopLoginPoll() {
  if (_pollTimer) {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }
}

export function getCachedAuth() {
  return store.loadAuthInfo();
}

// ── Run management ────────────────────────────────────────────────────────

const _runPollers = new Map(); // run_id → intervalId

/**
 * Launch an action.  Returns the run object.
 * Validates auth before starting.
 *
 * @param {"export_chat"|"export_meeting_transcript"|"list_chats"|"list_active_chats"} action
 * @param {object} params  – form data to send
 */
export async function startRun(action, params) {
  // Quick auth check before action (the only per-action ping)
  const authed = await checkAuth();
  if (!authed) {
    throw new Error("Not authenticated – please sign in again.");
  }

  let run;
  switch (action) {
    case "export_chat":
      run = await api.startExportChat(params);
      break;
    case "export_meeting_transcript":
      run = await api.startExportMeetingTranscript(params);
      break;
    case "list_chats":
      run = await api.startListChats(params);
      break;
    case "list_active_chats":
      run = await api.startListActiveChats(params);
      break;
    default:
      throw new Error(`Unknown action: ${action}`);
  }
  store.upsertRun(run);
  _emit("run:started", run);
  _beginStatusPolling(run.run_id);
  return run;
}

function _beginStatusPolling(runId) {
  // Clear existing poller for this run
  if (_runPollers.has(runId)) {
    clearTimeout(_runPollers.get(runId));
  }

  let delay = 2000; // start at 2s, back off gradually

  async function poll() {
    try {
      const status = await api.getRunStatus(runId);
      store.upsertRun({ run_id: runId, ...status });
      _emit("run:progress", { run_id: runId, ...status });

      if (status.status === "completed" || status.status === "failed" || status.status === "cancelled") {
        _runPollers.delete(runId);

        if (status.status === "completed") {
          // Fetch grid data
          try {
            const results = await api.getRunResults(runId);
            store.upsertRun({ run_id: runId, results });
            _emit("run:completed", { run_id: runId, ...status, results });
          } catch (e) {
            _emit("run:completed", { run_id: runId, ...status });
          }
        } else {
          _emit("run:failed", { run_id: runId, ...status });
        }
        return; // stop polling
      }
    } catch (e) {
      console.warn("[business] status poll error:", e);
    }

    // Gradually increase poll interval (2s → 3s → 4s → max 5s)
    delay = Math.min(delay + 500, 5000);
    const tid = setTimeout(poll, delay);
    _runPollers.set(runId, tid);
  }

  const tid = setTimeout(poll, delay);
  _runPollers.set(runId, tid);
}

/**
 * Get the download URL for a completed run.
 */
export function getDownloadUrl(runId) {
  return api.downloadUrl(runId);
}

/**
 * Fetch and merge run history from server.
 * Also returns the merged list.
 */
export async function refreshHistory() {
  try {
    const data = await api.getRunHistory();
    if (data.runs) {
      store.mergeHistory(data.runs);
    }
  } catch (e) {
    console.warn("[business] refreshHistory error:", e);
  }
  return store.getAllRuns();
}

export async function deleteRun(runId) {
  await api.deleteRun(runId);
  store.removeRun(runId);
  _emit("run:deleted", { run_id: runId });
}

export async function clearAllRuns() {
  const result = await api.clearAllRuns();
  store.clearRuns();
  _emit("runs:cleared", { deleted: result.deleted });
  return result;
}

/**
 * Get locally stored run history (no network call).
 */
export function getLocalHistory() {
  return store.getAllRuns();
}

/**
 * Fetch results for a completed run (for re-hydrating the grid).
 * Returns { action, params, summary, grid_data, grid_total, run_id }.
 */
export async function loadRunResults(runId) {
  const results = await api.getRunResults(runId);
  return results;
}

/**
 * Get available actions with metadata.
 */
export function getActions() {
  return [
    {
      id: "list_active_chats",
      label: "Active Chats",
      icon: "🟢",
      description: "Find recently active chats",
    },
    {
      id: "export_meeting_transcript",
      label: "Meeting Transcript",
      icon: "📝",
      description: "Export a meeting transcript as text or JSON",
    },
    {
      id: "list_chats",
      label: "List Chats",
      icon: "📋",
      description: "Browse and filter your chats",
    },
    {
      id: "export_chat",
      label: "Export Chat",
      icon: "📤",
      description: "Export messages from a specific chat",
    },
  ];
}
