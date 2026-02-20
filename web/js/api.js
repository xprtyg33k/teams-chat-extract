/**
 * api.js – Thin HTTP client for the /api endpoints.
 *
 * Every public function returns a Promise that resolves to the parsed JSON
 * response body or rejects with an Error whose `message` contains the
 * server-supplied detail (when available).
 *
 * API_BASE is injected by the server/Docker build process.
 */

// Allow override via window.API_BASE (set by Docker or index.html)
// Default to relative /api for backward compatibility
const BASE = (typeof window !== "undefined" && window.API_BASE)
  ? `${window.API_BASE}/api`
  : "/api";

async function _request(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== null) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err.detail) detail = err.detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  // Handle 204 No Content
  if (res.status === 204) return {};
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────

export function getAuthStatus() {
  return _request("GET", "/auth/status");
}

export function startDeviceCodeFlow() {
  return _request("POST", "/auth/device-code");
}

export function pollDeviceCode(flowId) {
  return _request("POST", "/auth/device-code/poll", { flow_id: flowId });
}

export function forceLogin() {
  return _request("POST", "/auth/force-login");
}

export function logout() {
  return _request("POST", "/auth/logout");
}

// ── Runs ──────────────────────────────────────────────────────────────────

export function startExportChat(params) {
  return _request("POST", "/runs/export-chat", params);
}

export function startListChats(params) {
  return _request("POST", "/runs/list-chats", params);
}

export function startListActiveChats(params) {
  return _request("POST", "/runs/list-active-chats", params);
}

export function getRunStatus(runId) {
  return _request("GET", `/runs/${runId}/status`);
}

export function getRunResults(runId) {
  return _request("GET", `/runs/${runId}/results`);
}

export function getRunHistory() {
  return _request("GET", "/runs/history");
}

/**
 * Returns a URL the browser can open to download the file.
 */
export function downloadUrl(runId) {
  return `${BASE}/runs/${runId}/download`;
}
