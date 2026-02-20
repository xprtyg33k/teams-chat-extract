/**
 * storage.js – Lightweight persistence layer.
 *
 * Uses localStorage for:
 *   • Last-known auth info (display only, NOT the token itself)
 *   • Run history cache (mirrors server-side but survives page reloads)
 *
 * Uses an in-browser SQLite-style approach via a simple JSON store that
 * keeps an array of run-history records keyed by run_id.  The "DB" is
 * flushed to localStorage on every mutation.
 */

const STORAGE_PREFIX = "tce_";
const AUTH_KEY = `${STORAGE_PREFIX}auth`;
const HISTORY_KEY = `${STORAGE_PREFIX}runs`;

// ── Auth info (display-only, not the real token) ──────────────────────────

export function saveAuthInfo(info) {
  try {
    localStorage.setItem(AUTH_KEY, JSON.stringify(info));
  } catch (_) {
    /* quota or private mode */
  }
}

export function loadAuthInfo() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

export function clearAuthInfo() {
  try {
    localStorage.removeItem(AUTH_KEY);
  } catch (_) {
    /* ignore */
  }
}

// ── Run History DB (in-memory + localStorage persistence) ─────────────────

/** @type {Map<string, object>} */
let _db = new Map();
let _loaded = false;

function _ensureLoaded() {
  if (_loaded) return;
  _loaded = true;
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        for (const item of arr) {
          _db.set(item.run_id, item);
        }
      }
    }
  } catch (_) {
    /* ignore */
  }
}

function _flush() {
  try {
    const arr = Array.from(_db.values());
    localStorage.setItem(HISTORY_KEY, JSON.stringify(arr));
  } catch (_) {
    /* ignore */
  }
}

/**
 * Upsert a run record.
 */
export function upsertRun(run) {
  _ensureLoaded();
  const existing = _db.get(run.run_id) || {};
  _db.set(run.run_id, { ...existing, ...run });
  _flush();
}

/**
 * Return all runs, newest first.
 */
export function getAllRuns() {
  _ensureLoaded();
  return Array.from(_db.values()).sort(
    (a, b) => (b.created_at || "").localeCompare(a.created_at || "")
  );
}

/**
 * Get a single run by id.
 */
export function getRun(runId) {
  _ensureLoaded();
  return _db.get(runId) || null;
}

/**
 * Merge server-side history into local DB (idempotent).
 */
export function mergeHistory(serverRuns) {
  _ensureLoaded();
  for (const r of serverRuns) {
    const existing = _db.get(r.run_id);
    if (!existing || existing.status !== r.status) {
      _db.set(r.run_id, { ...existing, ...r });
    }
  }
  _flush();
}

/**
 * Clear all stored runs.
 */
export function clearHistory() {
  _db.clear();
  _flush();
}
