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

  // History: click a run or download button (delegated)
  els.historyList.addEventListener("click", (e) => {
    const dlBtn = e.target.closest("[data-dl-run]");
    if (dlBtn) {
      window.open(biz.getDownloadUrl(dlBtn.dataset.dlRun), "_blank");
      return;
    }
    const item = e.target.closest(".history-item");
    if (item && item.dataset.runId) {
      // Could reload results for this run — for now just download
      window.open(biz.getDownloadUrl(item.dataset.runId), "_blank");
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

// ── Go ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", init);
