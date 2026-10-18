import { el, hopChips } from "../api.js";
import { state } from "./state.js";

let cy = null;
let popover = null;

export function rankOf(kind) {
  return {
    HazardType: 0,
    CropStage: 1,
    LivestockStage: 1,
    Commodity: 2,
    Market: 3,
    LaborGroup: 4,
    HealthOutcome: 5,
    Intervention: 6,
    District: -1,
    Officer: 7,
    Forecast: -1,
  }[kind] ?? 3;
}

function token(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function styleFor() {
  const text = token("--text", "#e8eef5");
  const border = token("--border", "#3d4d60");
  const surface2 = token("--surface-2", "#2c3a4a");
  return [
    { selector: "node", style: { "background-color": surface2, label: "data(label)", color: text, "font-size": 10, "text-wrap": "wrap", "text-max-width": 110, "text-valign": "bottom", "text-margin-y": 4, width: 26, height: 26, "border-width": 1, "border-color": border } },
    { selector: "node[kind = 'HazardType']", style: { "background-color": token("--heat-3", "#e8590c"), shape: "diamond", width: 28, height: 28 } },
    { selector: "node[kind = 'HealthOutcome']", style: { "background-color": token("--heat-4", "#fa5252"), shape: "ellipse" } },
    { selector: "node[kind = 'Intervention']", style: { "background-color": token("--defeated", "#495057"), shape: "round-rectangle", width: 26, height: 18 } },
    { selector: "node.act", style: { "background-color": token("--act", "#2f9e44") } },
    { selector: "node.defeated_precedent", style: { "background-color": token("--unprecedented", "#868e96"), "border-width": 2, "border-style": "dashed", "border-color": token("--defeated", "#495057"), opacity: 0.75 } },
    { selector: "node.on-unprecedented", style: { "border-width": 2, "border-color": token("--unprecedented", "#868e96") } },
    { selector: "edge", style: { width: 1.4, "line-color": border, "target-arrow-color": border, "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.7 } },
    { selector: "edge.accepted", style: { width: (ele) => 2.5 + (Number(ele.data("weight")) || 0.5) * 3, "line-color": token("--heat-3", "#e8590c"), "target-arrow-color": token("--heat-4", "#fa5252"), "line-fill": "linear-gradient", "line-gradient-stop-colors": `${token("--heat-3", "#e8590c")} ${token("--heat-4", "#fa5252")}` } },
    { selector: "edge.contested", style: { "line-style": "dashed", "line-color": token("--contested", "#fcc419"), "target-arrow-color": token("--contested", "#fcc419"), width: 2 } },
    { selector: "edge.weak_analog", style: { "line-style": "dashed", "line-color": token("--contested", "#fcc419"), "target-arrow-color": token("--contested", "#fcc419"), width: 2 } },
    { selector: "edge.defeated", style: { "line-style": "dashed", width: 1, "line-color": token("--defeated", "#495057"), "target-arrow-color": token("--defeated", "#495057") } },
    { selector: "edge.unprecedented", style: { "line-color": token("--unprecedented", "#868e96"), "target-arrow-color": token("--unprecedented", "#868e96"), width: 2, opacity: 0.55 } },
    { selector: "node.dim, edge.dim", style: { opacity: 0.18 } },
  ];
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-sentinel-src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "1") return resolve();
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", reject);
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.async = false;
    s.dataset.sentinelSrc = src;
    s.onload = () => { s.dataset.loaded = "1"; resolve(); };
    s.onerror = () => reject(new Error("failed " + src));
    document.head.appendChild(s);
  });
}

async function ensureDagre() {
  if (!window.cytoscape) {
    await loadScript((window.SENTINEL_STATIC || "/static") + "/vendor/cytoscape.min.js");
    await loadScript((window.SENTINEL_STATIC || "/static") + "/vendor/dagre.min.js");
    await loadScript((window.SENTINEL_STATIC || "/static") + "/vendor/cytoscape-dagre.js");
  }
  const cytoscape = window.cytoscape;
  const ext = window.cytoscapeDagre;
  if (!cytoscape || !ext) throw new Error("Cytoscape or dagre extension failed to load");
  if (!window.__sentinelDagre) {
    cytoscape.use(ext);
    window.__sentinelDagre = true;
  }
  return cytoscape;
}

function hidePopover() {
  popover?.remove();
  popover = null;
}

function showPopover(renderedPos, title, rows) {
  hidePopover();
  const box = el("div", { class: "popover", role: "dialog", "aria-label": title });
  box.append(el("strong", { text: title }));
  for (const [k, v] of rows) {
    box.append(el("div", {}, el("span", { class: "muted", text: k + " " }), document.createTextNode(String(v ?? "—"))));
  }
  const host = document.querySelector(".graph-stage") || document.getElementById("graphHost") || document.getElementById("graph");
  host.style.position = "relative";
  box.style.left = `${Math.min(renderedPos.x + 8, host.clientWidth - 200)}px`;
  box.style.top = `${Math.max(8, renderedPos.y + 8)}px`;
  host.append(box);
  popover = box;
}

export async function draw(elements, unprecedented) {
  await ensureDagre();
  hidePopover();
  const nodes = (elements.nodes || []).map((n) => {
    n.data.rank = rankOf(n.data.kind);
    return n;
  });
  const ids = new Set(nodes.map((n) => n.data.id));
  const edges = (elements.edges || []).filter((e) => ids.has(e.data.source) && ids.has(e.data.target));
  if (cy) cy.destroy();
  const container = document.getElementById("graph");
  cy = window.cytoscape({
    container,
    elements: nodes.concat(edges),
    style: styleFor(),
    // portrait phones read the cascade top-to-bottom; wider screens left-to-right
    layout: { name: "dagre", rankDir: innerWidth < 700 ? "TB" : "LR", ranker: "network-simplex", nodeSep: 28, rankSep: innerWidth < 700 ? 60 : 90, padding: 20 },
    minZoom: 0.15,
    maxZoom: 2.2,
  });
  applyLayerFilters();
  document.getElementById("graphEmpty")?.classList.add("hidden");
  cy.ready(() => { try { cy.fit(undefined, 28); } catch { /* layout pending */ } });
  animateAccepted();
  const badge = document.getElementById("unprecBadge");
  const hasUnprec = (unprecedented && unprecedented.length) || cy.edges(".unprecedented").length > 0;
  badge?.classList.toggle("hidden", !hasUnprec);

  cy.on("tap", "node, edge", (ev) => {
    const d = ev.target.data();
    const pos = ev.target.renderedPosition ? ev.target.renderedPosition() : ev.renderedPosition;
    if (ev.target.isNode()) {
      showPopover(pos, d.label || d.id, [
        ["id", d.id],
        ["kind", d.kind],
        ["layer", d.layer],
        ["status", d.status],
        ["provenance", d.provenance],
      ]);
    } else {
      showPopover(pos, d.label || "edge", [
        ["type", d.label],
        ["weight", d.weight],
        ["confidence", d.confidence],
        ["lag_days", d.lag_days],
        ["cite", d.cite],
      ]);
    }
  });
  cy.on("tap", (ev) => { if (ev.target === cy) hidePopover(); });
}

function animateAccepted() {
  if (!cy) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hops = [];
  cy.edges(".accepted").forEach((e) => hops.push(e));
  hops.sort((a, b) => (a.source().data("rank") || 0) - (b.source().data("rank") || 0));
  if (reduce) {
    hops.forEach((e) => e.style("opacity", 1));
    return;
  }
  hops.forEach((e) => e.style("opacity", 0.15));
  hops.forEach((e, i) => {
    setTimeout(() => {
      e.animate({ style: { opacity: 1, width: 4 + (e.data("weight") || 0.5) * 2 } }, { duration: 220 });
    }, i * 250);
  });
}

export function applyLayerFilters() {
  if (!cy) return;
  for (const [cls, on] of Object.entries(state.layers)) {
    cy.nodes("." + cls).style("display", on ? "element" : "none");
  }
}

export function fit() { cy?.fit(undefined, 24); }
// Re-measure after the container was hidden (mobile tabs) or resized, then refit.
export function refit() {
  if (!cy) return;
  const host = cy.container();
  if (!host || host.offsetWidth === 0 || host.offsetHeight === 0) return;
  cy.resize();
  cy.fit(undefined, 24);
}
let resizeTimer = 0;
addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(refit, 150); });
export function zoomBy(delta) { if (cy) cy.zoom(cy.zoom() * delta); }

export function highlightPath(signature) {
  if (!cy) return;
  if (!signature) {
    cy.elements().removeClass("dim");
    return;
  }
  const ids = hopChips(signature);
  const keep = new Set(ids);
  cy.elements().addClass("dim");
  ids.forEach((id) => cy.$id(id).removeClass("dim"));
  cy.edges().forEach((e) => {
    if (keep.has(e.data("source")) && keep.has(e.data("target"))) e.removeClass("dim");
  });
}

function pathTable(paths, pathStatus) {
  const table = el("table", { class: "paths-table" });
  const thead = el("thead");
  const hr = el("tr");
  ["rank", "path", "score", "lag_days", "I", "T", "exposure", "status"].forEach((h) => hr.append(el("th", { text: h })));
  thead.append(hr);
  table.append(thead);
  const tb = el("tbody");
  for (const p of paths) {
    const tr = el("tr");
    tr.append(el("td", { class: "tabular", text: String(p.rank ?? "") }));
    const chips = el("td", { class: "path-chips" });
    hopChips(p.signature).forEach((h) => chips.append(el("span", { class: "chip", text: h })));
    tr.append(chips);
    tr.append(el("td", { class: "tabular", text: p.score != null ? Number(p.score).toFixed(3) : "—" }));
    tr.append(el("td", { class: "tabular", text: String(p.lag_days ?? "—") }));
    tr.append(el("td", { class: "tabular", text: p.intensity != null ? Number(p.intensity).toFixed(2) : "—" }));
    tr.append(el("td", { class: "tabular", text: p.timing != null ? Number(p.timing).toFixed(2) : "—" }));
    tr.append(el("td", { class: "tabular", text: p.exposure != null ? Number(p.exposure).toFixed(2) : "—" }));
    const st = (pathStatus && pathStatus[p.signature]) || "";
    tr.append(el("td", {}, el("span", { class: `chip chip-${st === "proposed" ? "contested" : st}`, text: st === "proposed" ? "contested" : st || "—" })));
    tb.append(tr);
  }
  table.append(tb);
  return table;
}

export function renderPathsTable(paths, pathStatus, direct) {
  const host = document.getElementById("pathsTable");
  if (!host) return;
  host.replaceChildren();
  if (!paths?.length && !direct?.length) {
    host.append(el("p", { class: "muted", text: "Run a season to list cascade paths." }));
    return;
  }
  host.append(el("h3", { text: "Cascade paths (3+ hops)" }));
  if (paths?.length) host.append(pathTable(paths, pathStatus));
  else host.append(el("p", { class: "muted", text: "none" }));
  host.append(el("h3", { text: "Direct exposure (1–2 hops)" }));
  if (direct?.length) host.append(pathTable(direct, pathStatus));
  else host.append(el("p", { class: "muted", text: "none" }));
}

export function destroyGraph() {
  hidePopover();
  if (cy) { cy.destroy(); cy = null; }
  document.getElementById("graphEmpty")?.classList.remove("hidden");
}
