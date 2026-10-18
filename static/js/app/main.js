import { api, readSSE, el, ApiError, authHeaders, sessionId } from "../api.js";
import { state, initTheme, setTheme, getTheme, episodeIdFor } from "./state.js";
import { draw, fit, refit, zoomBy, applyLayerFilters, renderPathsTable, destroyGraph, highlightPath } from "./graph.js";
import { resetTimeline, addStep, renderHypotheses, renderRationale } from "./timeline.js";
import { renderRecs, renderClosePanel } from "./recs.js";
import { bindExplainClose } from "./explain.js";
import { bindMemoryTabs, loadMemory } from "./memory.js";
import { showDiffAfter2025 } from "./diff.js";
import { showToast, showBanner, setBusy as setBusyRaw, closeModal, confirmReset } from "./ui.js";

function $(id) { return document.getElementById(id); }

function setBusy(on) {
  setBusyRaw(on);
  state.inFlight = !!on;
  updateStepper();
}

function setHealthPill(ok, ping) {
  const pill = $("healthPill");
  if (!pill) return;
  pill.classList.toggle("ok", !!ok);
  pill.classList.toggle("bad", !ok);
  pill.textContent = ok ? `API ping ${ping ?? 1}` : "API down";
}

async function checkHealth() {
  try {
    const h = await api("/health");
    state.health = h;
    setHealthPill(!!h.ok, h.ping);
    $("healthPill").textContent = h.replay ? "Recorded replay" : h.ok ? "Live FalkorDB" : "API down";
    $("healthPill").title = h.replay ? "Static replay of recorded FalkorDB runs" : `Live FalkorDB · your own sandbox graph (session ${sessionId().slice(0, 6)}) · ping ${h.ping ?? 1}`;
    showBanner(false);
    renderMcp(h.tools || []);
    return true;
  } catch {
    setHealthPill(false);
    showBanner(true, "Can't reach FalkorDB/API. Run make up && make seed");
    return false;
  }
}

function renderMcp(tools) {
  const host = $("mcpList");
  if (!host) return;
  host.replaceChildren();
  tools.forEach((name) => host.append(el("li", {}, el("code", { text: name }))));
}

async function loadTenants() {
  const sel = $("tenant");
  const data = await api("/api/tenants");
  state.tenants = data.tenants || [];
  sel.replaceChildren();
  state.tenants.forEach((t) => {
    sel.append(el("option", { value: t.id, text: t.name }));
  });
  if (state.tenants[0]) state.tenant = state.tenants[0].id;
}

async function refreshEpisodes() {
  const st = {};
  for (const year of [2024, 2025]) {
    try {
      const info = await api(`/api/${state.tenant}/episode/${year}`);
      st[year] = info.status || "absent";
      const btn = year === 2024 ? $("btn2024") : $("btn2025");
      if (info.status && info.status !== "absent") btn?.classList.add("done");
      else btn?.classList.remove("done");
      if (year === 2024 && info.status === "closed") $("btnClose")?.classList.add("done");
      if (year === 2024 && info.status === "open") {
        state.episodeId = info.id;
        $("btnClose")?.classList.remove("done");
      }
      if (year === 2024 && info.status === "closed") state.episodeId = info.id;
    } catch {
      st[year] = "absent"; /* episode probe is best-effort */
    }
  }
  state.seasons = st;
  updateStepper();
}

// Season flow is strictly 2024 -> close -> 2025 (the double run). Gate the buttons so an
// out-of-order click is impossible, and say what to do next instead of failing later.
function updateStepper() {
  const s24 = state.seasons?.[2024] || "absent";
  const s25 = state.seasons?.[2025] || "absent";
  const busy = !!state.inFlight;
  const set = (id, enabled, why) => {
    const b = $(id);
    if (!b) return;
    b.disabled = busy || !enabled;
    if (!enabled && why) b.title = why; else b.removeAttribute("title");
  };
  set("btn2024", s24 !== "closed", "Season 2024 is closed. Reset to run it again.");
  set("btnClose", s24 === "open", s24 === "closed" ? "Episode already closed." : "Run Season 2024 first.");
  set("btn2025", s24 === "closed", "Close the 2024 episode first.");
  set("btnReset", true);
  const tenantSel = $("tenant");
  if (tenantSel) tenantSel.disabled = busy;
  ["btn2024", "btnClose", "btn2025"].forEach((id) => $(id)?.classList.remove("btn-primary"));
  const next = s24 === "absent" ? "btn2024" : s24 === "open" ? "btnClose" : s25 === "absent" ? "btn2025" : null;
  if (next) $(next)?.classList.add("btn-primary");
  const hint = $("stepHint");
  if (hint) {
    hint.textContent = busy ? "Working…"
      : s24 === "absent" ? "Start with ① Run Season 2024. Day-1 data only; held-out outcomes stay sealed."
      : s24 === "open" ? "Next: ② Close Episode to write the real outcomes back into memory."
      : s25 === "absent" ? "Next: ③ Run Season 2025 and see what memory changed."
      : "Done. Explain any card, or Reset to replay the double run.";
  }
}

function applyBundle(bundle, year) {
  state.lastBundle = bundle;
  state.episodeId = bundle.episode_id;
  state.year = year;
  if (year === 2024) state.bundle2024 = bundle;
  if (year === 2025) state.bundle2025 = bundle;
  renderRecs(bundle);
  renderHypotheses(bundle.hypotheses);
  renderRationale(bundle.rationale);
  renderPathsTable(bundle.paths, bundle.path_status, bundle.direct_exposure);
}

async function loadSnapshot(eid) {
  const snap = await api(`/api/${state.tenant}/snapshot/${eid}`);
  try {
    await draw(snap.result.elements, snap.result.unprecedented);
  } catch (err) {
    showToast("Graph viewer failed to load local cytoscape/dagre");
    throw err;
  }
}

async function runSeason(year) {
  if (state.inFlight) return;
  state.inFlight = true;
  setBusy(true);
  resetTimeline();
  showToast(`Running season ${year} (synthetic day-1 data)…`);
  try {
    const res = await fetch(`/api/${state.tenant}/run/${year}`, { method: "POST", headers: authHeaders() });
    if (!res.ok) throw new ApiError(res.status, `/run/${year}`, await res.text());
    await readSSE(res, {
      onStep: addStep,
      onDone: async (bundle) => {
        applyBundle(bundle, year);
        await loadSnapshot(bundle.episode_id);
        if (year === 2025) await showDiffAfter2025(bundle);
        showToast(`Season ${year} complete`);
      },
    });
    await refreshEpisodes();
  } catch (err) {
    errorRun(err, () => runSeason(year));
  } finally {
    state.inFlight = false;
    setBusy(false);
  }
}

function detailOf(err) {
  try { return JSON.parse(err.body || "{}").detail || ""; } catch { return ""; }
}

function errorRun(err, retry) {
  const host = $("recs");
  const detail = err instanceof ApiError ? detailOf(err) : "";
  const msg = err instanceof ApiError ? `Run failed (${err.status || "network"}). ${detail}`.trim() : "Run failed.";
  host.replaceChildren();
  host.append(el("div", { class: "error-state" },
    el("p", { text: msg }),
    el("button", { class: "btn", type: "button", text: "Retry", onclick: retry }),
  ));
  showToast(msg);
}

async function closeEpisode() {
  if (state.inFlight) return;
  const eid = state.episodeId || episodeIdFor(2024);
  state.inFlight = true;
  setBusy(true);
  try {
    const out = await api(`/api/${state.tenant}/close/${eid}`, { method: "POST" });
    const r = out.result;
    state.closeResult = r;
    renderClosePanel(r);
    showToast(`Write-back done. Reconstruction ${r.reconstruction_pass ? "PASS" : "FAIL"} J=${Number(r.reconstruction_jaccard).toFixed(2)}`);
    try { await loadSnapshot(eid); } catch { /* snapshot optional after close */ }
    await refreshEpisodes();
  } catch (err) {
    const msg = err instanceof ApiError ? `Close failed (${err.status || "network"}). ${detailOf(err)}`.trim() : "Close failed";
    showToast(msg);
    $("closePanel").replaceChildren(el("div", { class: "error-state" },
      el("p", { text: msg }),
      el("button", { class: "btn", type: "button", text: "Retry", onclick: () => closeEpisode() }),
    ));
  } finally {
    state.inFlight = false;
    setBusy(false);
  }
}

async function resetGraph({ skipConfirm = false } = {}) {
  if (state.inFlight) { showToast("Wait for the current step to finish."); return; }
  if (!skipConfirm) {
    const ok = await confirmReset();
    if (!ok) return;
  }
  if (state.inFlight) return;
  state.inFlight = true;
  setBusy(true);
  try {
    const out = await api(`/api/${state.tenant}/reset`, { method: "POST" });
    state.bundle2024 = state.bundle2025 = state.lastBundle = state.closeResult = null;
    state.episodeId = null;
    state.approved = {};
    resetTimeline();
    destroyGraph();
    renderRecs({ recommendations: [] });
    renderHypotheses([]);
    renderRationale("");
    $("closePanel")?.replaceChildren();
    $("pathsTable")?.replaceChildren();
    showToast(`Graph reseeded: ${out.nodes} nodes, ${out.edges} edges (synthetic)`);
    await refreshEpisodes();
    loadMemory("episodic");
  } catch (err) {
    showToast(err instanceof ApiError ? `Reset failed (${err.status || "network"})` : "Reset failed");
  } finally {
    state.inFlight = false;
    setBusy(false);
  }
}

function bindMobileTabs() {
  document.querySelectorAll(".mobile-tabs [data-pane]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pane = btn.getAttribute("data-pane");
      state.mobilePane = pane;
      const target = pane === "memory" ? "debate" : pane;
      document.querySelectorAll(".app-grid > .pane").forEach((p) => p.classList.toggle("active", p.dataset.pane === target));
      $("leftPane")?.classList.toggle("show-memory", pane === "memory");
      if (pane === "memory") $("memoryAnchor")?.setAttribute("open", "");
      document.querySelectorAll(".mobile-tabs [data-pane]").forEach((b) => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));
      if (pane === "graph") requestAnimationFrame(() => refit());
    });
  });
}

function bindLayers() {
  document.querySelectorAll("[data-layer]").forEach((box) => {
    box.addEventListener("change", () => {
      state.layers[box.getAttribute("data-layer")] = box.checked;
      applyLayerFilters();
    });
  });
}

function localHost() {
  const h = location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

function syncThemeButton() {
  const b = $("themeToggle");
  if (!b) return;
  const other = getTheme() === "dark" ? "Light" : "Dark";
  b.textContent = other;
  b.setAttribute("aria-label", `${other} theme`);
}

async function boot() {
  initTheme();
  $("themeToggle")?.addEventListener("click", () => {
    const next = getTheme() === "dark" ? "light" : "dark";
    setTheme(next);
    syncThemeButton();
    if (state.lastBundle) loadSnapshot(state.episodeId).catch(() => {});
  });
  syncThemeButton();

  if (!localHost()) $("browserLink")?.classList.add("hidden");

  bindExplainClose();
  bindMemoryTabs();
  bindMobileTabs();
  bindLayers();

  $("btn2024").addEventListener("click", () => runSeason(2024));
  $("btnClose").addEventListener("click", () => closeEpisode());
  $("btn2025").addEventListener("click", () => runSeason(2025));
  $("btnReset").addEventListener("click", () => resetGraph());
  $("diffClose")?.addEventListener("click", () => closeModal("diffModal"));
  $("healthRetry")?.addEventListener("click", () => checkHealth());
  $("fitBtn")?.addEventListener("click", () => fit());
  $("zoomIn")?.addEventListener("click", () => zoomBy(1.2));
  $("zoomOut")?.addEventListener("click", () => zoomBy(1 / 1.2));
  $("copyMcp")?.addEventListener("click", async () => {
    await navigator.clipboard.writeText("python -m sentinel.mcp_server --list");
    showToast("Command copied");
  });

  document.getElementById("hyps")?.addEventListener("mouseover", (e) => {
    const item = e.target.closest("[data-path]");
    if (item) highlightPath(item.dataset.path);
  });
  document.getElementById("hyps")?.addEventListener("mouseout", (e) => {
    if (!e.target.closest("[data-path]")) highlightPath(null);
  });

  $("tenant").addEventListener("change", async () => {
    const sel = $("tenant");
    const next = sel.value;
    const prev = state.tenant;
    sel.value = prev;
    if (state.inFlight) { showToast("Wait for the current step to finish."); return; }
    const ok = await confirmReset();
    if (!ok) return;
    if (state.inFlight) { showToast("Wait for the current step to finish."); return; }
    state.tenant = next;
    sel.value = next;
    await resetGraph({ skipConfirm: true });
  });

  const ok = await checkHealth();
  if (ok) {
    try { await loadTenants(); } catch { showToast("Could not load tenants"); }
    await refreshEpisodes();
    await restoreSession();
  }
}

async function restoreSession() {
  for (const year of [2025, 2024]) {
    try {
      const info = await api(`/api/${state.tenant}/episode/${year}`);
      if (!info.status || info.status === "absent") continue;
      state.episodeId = info.id;
      state.year = year;
      try {
        const recs = await api(`/api/${state.tenant}/recommendations/${info.id}`);
        renderRecs({ recommendations: recs.recommendations || [] });
      } catch { /* recs optional */ }
      try { await loadSnapshot(info.id); } catch { /* snapshot optional */ }
      return;
    } catch {
      /* episode probe is best-effort */
    }
  }
}

boot();
