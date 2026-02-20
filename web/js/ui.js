/**
 * ui.js – DOM manipulation helpers.
 *
 * All direct DOM access lives here.  The app.js orchestrator calls these
 * functions in response to business-layer events.
 */

// ── Cached elements ───────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const els = {
  // sections
  authGate: $("#authGate"),
  mainContent: $("#mainContent"),

  // auth
  userBadge: $("#userBadge"),
  btnStartLogin: $("#btnStartLogin"),
  deviceCodePanel: $("#deviceCodePanel"),
  deviceCode: $("#deviceCode"),
  deviceCodeLink: $("#deviceCodeLink"),
  authSpinner: $("#authSpinner"),

  // panels
  panelForms: $("#panelForms"),
  panelProgress: $("#panelProgress"),
  panelResults: $("#panelResults"),
  panelHistory: $("#panelHistory"),

  // forms
  formExportChat: $("#formExportChat"),
  formListChats: $("#formListChats"),
  formListActiveChats: $("#formListActiveChats"),
  noActionSelected: $("#noActionSelected"),

  // progress
  progressBar: $("#progressBar"),
  progressTitle: $("#progressTitle"),
  progressText: $("#progressText"),

  // results
  summaryCards: $("#summaryCards"),
  gridHead: $("#gridHead"),
  gridBody: $("#gridBody"),
  gridSearch: $("#gridSearch"),
  gridInfo: $("#gridInfo"),
  pageInfo: $("#pageInfo"),
  btnPrev: $("#btnPrev"),
  btnNext: $("#btnNext"),
  btnDownload: $("#btnDownload"),
  btnNewRun: $("#btnNewRun"),
  btnCopyGrid: $("#btnCopyGrid"),

  // history
  historyList: $("#historyList"),
};

// ── Utility ───────────────────────────────────────────────────────────────

function show(el) {
  if (el) el.classList.remove("hidden");
}
function hide(el) {
  if (el) el.classList.add("hidden");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Auth UI ───────────────────────────────────────────────────────────────

export function showAuthGate() {
  show(els.authGate);
  hide(els.mainContent);
  hide(els.deviceCodePanel);
}

export function showMain() {
  hide(els.authGate);
  show(els.mainContent);
}

export function setUserBadge(name, email) {
  els.userBadge.innerHTML = `
    <div class="user-badge">
      <span class="dot"></span>
      <span>${escapeHtml(name || email || "User")}</span>
      <button class="logout-btn" id="btnLogout" title="Sign out">✕</button>
    </div>`;
}

export function clearUserBadge() {
  els.userBadge.innerHTML = "";
}

export function showDeviceCode(code, uri) {
  els.deviceCode.textContent = code;
  els.deviceCodeLink.href = uri;
  els.deviceCodeLink.textContent = uri.replace(/^https?:\/\//, "");
  show(els.deviceCodePanel);
  show(els.authSpinner);
}

export function hideDeviceCode() {
  hide(els.deviceCodePanel);
  hide(els.authSpinner);
}

// ── Action sidebar ────────────────────────────────────────────────────────

export function setActiveAction(actionId) {
  $$(".action-card").forEach((card) => {
    card.classList.toggle("active", card.dataset.action === actionId);
  });
}

// ── Forms ─────────────────────────────────────────────────────────────────

const formMap = {
  export_chat: "formExportChat",
  list_chats: "formListChats",
  list_active_chats: "formListActiveChats",
};

export function showForm(actionId) {
  // hide all panels first
  hide(els.panelProgress);
  hide(els.panelResults);
  hide(els.panelHistory);
  show(els.panelForms);

  // hide all forms
  hide(els.formExportChat);
  hide(els.formListChats);
  hide(els.formListActiveChats);
  hide(els.noActionSelected);

  const formKey = formMap[actionId];
  if (formKey && els[formKey]) {
    show(els[formKey]);
    // Default the Since Date to 1 month ago when showing Export Chat
    if (actionId === "export_chat") {
      _setDefaultSinceDate();
    }
  } else {
    show(els.noActionSelected);
  }
}

function _setDefaultSinceDate() {
  const sinceInput = els.formExportChat.querySelector('input[name="since"]');
  if (sinceInput && !sinceInput.value) {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    sinceInput.value = _toDateString(d);
  }
}

function _toDateString(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Shift a date input by the given delta string (e.g. "+1m", "-3m", "+1y", "-1y").
 */
export function shiftDateInput(targetName, shiftStr) {
  const input = els.formExportChat.querySelector(`input[name="${targetName}"]`);
  if (!input) return;

  // Start from the current value, or today if empty
  const base = input.value ? new Date(input.value + "T00:00:00") : new Date();
  const sign = shiftStr.startsWith("-") ? -1 : 1;
  const num = parseInt(shiftStr.replace(/[^0-9]/g, ""), 10);
  const unit = shiftStr.slice(-1).toLowerCase();

  if (unit === "m") {
    base.setMonth(base.getMonth() + sign * num);
  } else if (unit === "y") {
    base.setFullYear(base.getFullYear() + sign * num);
  }
  input.value = _toDateString(base);
}

export function showHistoryPanel() {
  hide(els.panelForms);
  hide(els.panelProgress);
  hide(els.panelResults);
  show(els.panelHistory);
}

/**
 * Read form data into a plain object.
 */
export function readForm(formEl) {
  const fd = new FormData(formEl);
  const data = {};
  for (const [key, val] of fd.entries()) {
    data[key] = val;
  }
  // Checkboxes aren't included in FormData when unchecked
  for (const cb of formEl.querySelectorAll('input[type="checkbox"]')) {
    data[cb.name] = cb.checked;
  }
  return data;
}

/**
 * Build API-ready params from raw form data.
 */
export function buildParams(action, raw) {
  switch (action) {
    case "export_chat":
      return {
        chat_id: raw.chat_id,
        since: raw.since,
        until: raw.until || null,
        format: raw.format || "json",
        exclude_system_messages: !!raw.exclude_system_messages,
        only_mine: !!raw.only_mine,
      };
    case "list_chats": {
      const topicInc = raw.topic_include
        ? raw.topic_include.split(",").map((s) => s.trim()).filter(Boolean)
        : null;
      const topicExc = raw.topic_exclude
        ? raw.topic_exclude.split(",").map((s) => s.trim()).filter(Boolean)
        : null;
      return {
        chat_type: raw.chat_type || "oneOnOne",
        max_participants: raw.max_participants ? parseInt(raw.max_participants, 10) : null,
        topic_include: topicInc,
        topic_exclude: topicExc,
      };
    }
    case "list_active_chats":
      return {
        min_activity_days: parseInt(raw.min_activity_days || "365", 10),
        max_meeting_participants: parseInt(raw.max_meeting_participants || "10", 10),
      };
    default:
      return raw;
  }
}

// ── Progress ──────────────────────────────────────────────────────────────

export function showProgress(title) {
  hide(els.panelForms);
  hide(els.panelResults);
  hide(els.panelHistory);
  show(els.panelProgress);
  els.progressTitle.textContent = title || "Running…";
  els.progressBar.style.width = "0%";
  els.progressText.textContent = "Starting…";
}

export function updateProgress(percent, message) {
  els.progressBar.style.width = `${percent}%`;
  els.progressText.textContent = message || `${percent}%`;
}

export function hideProgress() {
  hide(els.panelProgress);
}

// ── Results ───────────────────────────────────────────────────────────────

let _gridData = [];
let _gridFiltered = [];
let _gridColumns = [];
let _sortCol = null;
let _sortAsc = true;
let _page = 0;
const PAGE_SIZE = 25;

export function showResults(summary, gridData, gridTotal, runId) {
  hide(els.panelForms);
  hide(els.panelProgress);
  hide(els.panelHistory);
  show(els.panelResults);

  // Summary cards
  _renderSummary(summary, gridTotal);

  // Grid
  _gridData = gridData || [];
  _gridFiltered = [..._gridData];
  _gridColumns = _gridData.length > 0 ? Object.keys(_gridData[0]) : [];
  _sortCol = null;
  _sortAsc = true;
  _page = 0;

  _renderGrid();

  // Download button stores run_id
  els.btnDownload.dataset.runId = runId;
}

function _renderSummary(summary, gridTotal) {
  let html = "";

  if (summary.total_messages != null) {
    html += _summaryCard("Total Messages", summary.total_messages);
  }
  if (summary.total_chats != null) {
    html += _summaryCard("Total Chats", summary.total_chats);
  }
  if (gridTotal != null) {
    html += _summaryCard("Showing", Math.min(gridTotal, _gridData.length) + " of " + gridTotal);
  }
  if (summary.chat_type) {
    html += _summaryCard("Chat Type", summary.chat_type);
  }
  if (summary.date_range_start) {
    html += _summaryCard("From", new Date(summary.date_range_start).toLocaleDateString());
  }
  if (summary.date_range_end) {
    html += _summaryCard("Until", new Date(summary.date_range_end).toLocaleDateString());
  }
  if (summary.participants && summary.participants.length) {
    html += _summaryCard("Participants", summary.participants.length);
  }
  if (summary.top_senders && summary.top_senders.length) {
    const top = summary.top_senders.slice(0, 3).map((s) => `${s.name} (${s.count})`).join(", ");
    html += _summaryCard("Top Senders", top);
  }

  els.summaryCards.innerHTML = html;
}

function _summaryCard(label, value) {
  return `<div class="summary-card"><div class="label">${escapeHtml(String(label))}</div><div class="value">${escapeHtml(String(value))}</div></div>`;
}

function _renderGrid() {
  // Detect chat_id column for row actions
  const chatIdCol = _gridColumns.find(
    (c) => c === "chat_id" || c === "ChatId" || c === "chatId"
  );

  // Header
  let headHtml = "<tr>";
  for (const col of _gridColumns) {
    const arrow =
      _sortCol === col ? (_sortAsc ? "▲" : "▼") : '<span style="opacity:0.3">⇅</span>';
    headHtml += `<th data-col="${col}">${escapeHtml(col)} <span class="sort-arrow">${arrow}</span></th>`;
  }
  if (chatIdCol) {
    headHtml += `<th class="grid-actions-col">Actions</th>`;
  }
  headHtml += "</tr>";
  els.gridHead.innerHTML = headHtml;

  // Body (paginated)
  const start = _page * PAGE_SIZE;
  const pageData = _gridFiltered.slice(start, start + PAGE_SIZE);

  const colSpan = chatIdCol ? _gridColumns.length + 1 : _gridColumns.length;
  let bodyHtml = "";
  if (pageData.length === 0) {
    bodyHtml = `<tr><td colspan="${colSpan}" style="text-align:center;padding:24px;color:var(--text-secondary)">No results</td></tr>`;
  } else {
    for (const row of pageData) {
      bodyHtml += "<tr>";
      for (const col of _gridColumns) {
        let val = row[col];
        if (val == null) val = "";
        if (col === chatIdCol) {
          // Render chat_id with copy icon
          bodyHtml += `<td title="${escapeHtml(String(val))}"><span class="chat-id-cell">${escapeHtml(String(val))}<button class="btn-icon btn-copy-id" data-copy-id="${escapeHtml(String(val))}" title="Copy Chat ID">📋</button></span></td>`;
        } else {
          bodyHtml += `<td title="${escapeHtml(String(val))}">${escapeHtml(String(val))}</td>`;
        }
      }
      if (chatIdCol) {
        const cid = escapeHtml(String(row[chatIdCol] || ""));
        bodyHtml += `<td class="grid-actions-cell"><button class="btn btn-sm btn-secondary" data-export-chat="${cid}" title="Export this chat">📤 Export</button></td>`;
      }
      bodyHtml += "</tr>";
    }
  }
  els.gridBody.innerHTML = bodyHtml;

  // Footer
  const totalPages = Math.max(1, Math.ceil(_gridFiltered.length / PAGE_SIZE));
  els.pageInfo.textContent = `Page ${_page + 1} of ${totalPages}`;
  els.gridInfo.textContent = `${_gridFiltered.length} rows`;
  els.btnPrev.disabled = _page === 0;
  els.btnNext.disabled = _page >= totalPages - 1;
}

export function gridSort(col) {
  if (_sortCol === col) {
    _sortAsc = !_sortAsc;
  } else {
    _sortCol = col;
    _sortAsc = true;
  }
  _gridFiltered.sort((a, b) => {
    const va = a[col] ?? "";
    const vb = b[col] ?? "";
    if (typeof va === "number" && typeof vb === "number") {
      return _sortAsc ? va - vb : vb - va;
    }
    return _sortAsc
      ? String(va).localeCompare(String(vb))
      : String(vb).localeCompare(String(va));
  });
  _page = 0;
  _renderGrid();
}

export function gridFilter(query) {
  const q = query.toLowerCase().trim();
  _gridFiltered = q
    ? _gridData.filter((row) =>
        _gridColumns.some((col) => String(row[col] ?? "").toLowerCase().includes(q))
      )
    : [..._gridData];
  _page = 0;
  _renderGrid();
}

export function gridPrev() {
  if (_page > 0) {
    _page--;
    _renderGrid();
  }
}

export function gridNext() {
  const totalPages = Math.ceil(_gridFiltered.length / PAGE_SIZE);
  if (_page < totalPages - 1) {
    _page++;
    _renderGrid();
  }
}

export function copyGridToClipboard() {
  if (_gridFiltered.length === 0) return;

  const header = _gridColumns.join("\t");
  const rows = _gridFiltered.map((row) =>
    _gridColumns.map((col) => String(row[col] ?? "")).join("\t")
  );
  const text = [header, ...rows].join("\n");

  navigator.clipboard.writeText(text).then(
    () => showToast("Copied to clipboard!"),
    () => showToast("Copy failed – check permissions")
  );
}

// ── History ───────────────────────────────────────────────────────────────

const ACTION_LABELS = {
  export_chat: "Export Chat",
  list_chats: "List Chats",
  list_active_chats: "Active Chats",
};

export function renderHistory(runs) {
  if (!runs || runs.length === 0) {
    els.historyList.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><p>No previous runs found.</p></div>`;
    return;
  }

  let html = "";
  for (const r of runs) {
    const label = ACTION_LABELS[r.action] || r.action;
    const time = r.created_at
      ? new Date(r.created_at).toLocaleString()
      : "—";
    const statusClass = (r.status || "pending").toLowerCase();

    html += `
      <div class="history-item" data-run-id="${r.run_id}">
        <div class="history-left">
          <span class="history-action">${escapeHtml(label)}</span>
          <span class="history-time">${escapeHtml(time)}</span>
        </div>
        <div class="history-right">
          <span class="status-badge ${statusClass}">${escapeHtml(r.status)}</span>
          ${r.status === "completed" ? `<button class="btn btn-sm btn-secondary" data-view-run="${r.run_id}" title="View in grid">👁</button>` : ""}
          ${r.status === "completed" ? `<button class="btn btn-sm btn-accent" data-dl-run="${r.run_id}" title="Download">⬇</button>` : ""}
        </div>
      </div>`;
  }
  els.historyList.innerHTML = html;
}

// ── Toast (simple) ────────────────────────────────────────────────────────

export function showToast(msg) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.style.cssText =
      "position:fixed;bottom:24px;right:24px;background:var(--bg-raised);color:var(--text-primary);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 20px;font-size:0.85rem;box-shadow:var(--shadow);z-index:9999;opacity:0;transition:opacity 0.3s";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = "1";
  setTimeout(() => {
    toast.style.opacity = "0";
  }, 2500);
}

// ── Error display ─────────────────────────────────────────────────────────

export function showError(title, detail) {
  hide(els.panelProgress);

  // Show inline in the forms area
  show(els.panelForms);
  const existing = els.panelForms.querySelector(".error-banner");
  if (existing) existing.remove();

  const banner = document.createElement("div");
  banner.className = "error-banner";
  banner.style.cssText =
    "background:rgba(248,81,73,0.12);border:1px solid var(--danger);border-radius:var(--radius-md);padding:16px 20px;margin-bottom:16px;";
  banner.innerHTML = `<strong style="color:var(--danger)">${escapeHtml(title)}</strong>${detail ? `<p style="margin-top:6px;color:var(--text-secondary);font-size:0.85rem">${escapeHtml(detail)}</p>` : ""}`;
  els.panelForms.prepend(banner);

  setTimeout(() => banner.remove(), 8000);
}

// ── Expose element getters for event wiring ──────────────────────────────

export function getElement(key) {
  return els[key];
}

export function getElements() {
  return els;
}

/**
 * Pre-fill the Export Chat form with a chat ID and switch to it.
 */
export function prefillExportChat(chatId) {
  const input = els.formExportChat.querySelector('input[name="chat_id"]');
  if (input) input.value = chatId;
  showForm("export_chat");
}
