/**
 * app.js – Application entry point.
 *
 * Wires business-layer events to UI functions and binds DOM event listeners.
 */

import * as biz from "./business.js";
import * as ui from "./ui.js";

// ── Bootstrap ─────────────────────────────────────────────────────────────

let _currentAction = null;
let _activeRunId = null;

async function init() {
  wireEvents();
  wireBusinessListeners();

  // Try cached auth info for instant UI while we verify
  const cached = biz.getCachedAuth();
  if (cached) {
    ui.setUserBadge(cached.user_name, cached.user_email);
  }

  // Check real auth status
  const authed = await biz.checkAuth();
  if (!authed) {
    ui.showAuthGate();
  }
}

// ── DOM event wiring ──────────────────────────────────────────────────────

function wireEvents() {
  const els = ui.getElements();

  // Auth: start login
  els.btnStartLogin.addEventListener("click", async () => {
    els.btnStartLogin.disabled = true;
    try {
      await biz.startLogin();
    } catch (e) {
      ui.showError("Login failed", e.message);
      els.btnStartLogin.disabled = false;
    }
  });

  // Auth: logout (delegated, since it's created dynamically)
  els.userBadge.addEventListener("click", async (e) => {
    if (e.target.id === "btnLogout" || e.target.closest("#btnLogout")) {
      await biz.doLogout();
    }
  });

  // Sidebar actions
  document.querySelectorAll(".action-card[data-action]").forEach((card) => {
    card.addEventListener("click", () => {
      const action = card.dataset.action;
      if (action === "history") {
        showHistory();
      } else {
        _currentAction = action;
        ui.setActiveAction(action);
        ui.showForm(action);
      }
    });
  });

  // Form submissions
  els.formExportChat.addEventListener("submit", (e) => {
    e.preventDefault();
    submitRun("export_chat", els.formExportChat);
  });
  els.formListChats.addEventListener("submit", (e) => {
    e.preventDefault();
    submitRun("list_chats", els.formListChats);
  });
  els.formListActiveChats.addEventListener("submit", (e) => {
    e.preventDefault();
    submitRun("list_active_chats", els.formListActiveChats);
  });

  // Date shortcut buttons (delegated on forms panel)
  els.panelForms.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-date-shift");
    if (btn) {
      ui.shiftDateInput(btn.dataset.dateTarget, btn.dataset.shift);
    }
  });

  // Results: download
  els.btnDownload.addEventListener("click", () => {
    const runId = els.btnDownload.dataset.runId;
    if (runId) {
      window.open(biz.getDownloadUrl(runId), "_blank");
    }
  });

  // Results: new run
  els.btnNewRun.addEventListener("click", () => {
    _activeRunId = null;
    if (_currentAction) {
      ui.showForm(_currentAction);
    } else {
      ui.showForm(null);
    }
  });

  // Grid: sort
  els.gridHead.addEventListener("click", (e) => {
    const th = e.target.closest("th");
    if (th && th.dataset.col) {
      ui.gridSort(th.dataset.col);
    }
  });

  // Grid: search
  els.gridSearch.addEventListener("input", (e) => {
    ui.gridFilter(e.target.value);
  });

  // Grid: pagination
  els.btnPrev.addEventListener("click", () => ui.gridPrev());
  els.btnNext.addEventListener("click", () => ui.gridNext());

  // Grid: copy
  els.btnCopyGrid.addEventListener("click", () => ui.copyGridToClipboard());

  // Grid: row actions (copy chat ID, export chat)
  els.gridBody.addEventListener("click", (e) => {
    const copyBtn = e.target.closest("[data-copy-id]");
    if (copyBtn) {
      e.stopPropagation();
      const chatId = copyBtn.dataset.copyId;
      navigator.clipboard.writeText(chatId).then(
        () => ui.showToast("Chat ID copied!"),
        () => ui.showToast("Copy failed – check permissions")
      );
      return;
    }
    const exportBtn = e.target.closest("[data-export-chat]");
    if (exportBtn) {
      e.stopPropagation();
      const chatId = exportBtn.dataset.exportChat;
      _currentAction = "export_chat";
      ui.setActiveAction("export_chat");
      ui.prefillExportChat(chatId);
      return;
    }
  });

  // History: click a run — view or download (delegated)
  els.historyList.addEventListener("click", async (e) => {
    const dlBtn = e.target.closest("[data-dl-run]");
    if (dlBtn) {
      window.open(biz.getDownloadUrl(dlBtn.dataset.dlRun), "_blank");
      return;
    }
    const viewBtn = e.target.closest("[data-view-run]");
    if (viewBtn) {
      await loadAndShowRun(viewBtn.dataset.viewRun);
      return;
    }
    const item = e.target.closest(".history-item");
    if (item && item.dataset.runId) {
      await loadAndShowRun(item.dataset.runId);
    }
  });
}

// ── Business event listeners ──────────────────────────────────────────────

function wireBusinessListeners() {
  biz.on("auth:changed", (data) => {
    if (data.authenticated) {
      ui.setUserBadge(data.user_name, data.user_email);
      ui.hideDeviceCode();
      ui.showMain();
    } else {
      ui.clearUserBadge();
      ui.showAuthGate();
    }
  });

  biz.on("auth:device-code", (data) => {
    ui.showDeviceCode(data.user_code, data.verification_uri);
  });

  biz.on("auth:error", (data) => {
    ui.hideDeviceCode();
    ui.showError("Authentication Error", data.error);
    ui.getElement("btnStartLogin").disabled = false;
  });

  biz.on("run:started", (run) => {
    _activeRunId = run.run_id;
    const labels = {
      export_chat: "Exporting chat…",
      list_chats: "Listing chats…",
      list_active_chats: "Finding active chats…",
    };
    ui.showProgress(labels[run.action] || "Running…");
  });

  biz.on("run:progress", (data) => {
    if (data.run_id === _activeRunId) {
      ui.updateProgress(data.progress || 0, data.progress_message || "Working…");
    }
  });

  biz.on("run:completed", (data) => {
    if (data.run_id === _activeRunId) {
      const r = data.results || {};
      ui.showResults(
        r.summary || data.summary || {},
        r.grid_data || [],
        r.grid_total || 0,
        data.run_id
      );
    }
  });

  biz.on("run:failed", (data) => {
    if (data.run_id === _activeRunId) {
      ui.hideProgress();
      ui.showError("Run Failed", data.error || data.progress_message || "Unknown error");
      if (_currentAction) ui.showForm(_currentAction);
    }
  });
}

// ── Actions ───────────────────────────────────────────────────────────────

async function submitRun(action, formEl) {
  const raw = ui.readForm(formEl);
  const params = ui.buildParams(action, raw);
  try {
    await biz.startRun(action, params);
  } catch (e) {
    ui.showError("Failed to start run", e.message);
  }
}

async function showHistory() {
  _currentAction = null;
  ui.setActiveAction("history");
  ui.showHistoryPanel();
  ui.renderHistory([]); // clear while loading
  const runs = await biz.refreshHistory();
  ui.renderHistory(runs);
}

/**
 * Fetch results for a completed run and display in the grid.
 */
async function loadAndShowRun(runId) {
  const results = await biz.loadRunResults(runId);
  if (results) {
    _activeRunId = runId;
    ui.showResults(
      results.summary || {},
      results.grid_data || [],
      results.grid_total || 0,
      runId
    );
  } else {
    ui.showError("Load Failed", "Could not retrieve results for this run.");
  }
}

// ── Go ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", init);
