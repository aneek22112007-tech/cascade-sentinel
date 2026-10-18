import { api, el, ApiError } from "../api.js";
import { state } from "./state.js";

const LAYERS = ["episodic", "semantic", "procedural", "corridor", "signal", "governance"];

export async function loadMemory(layer) {
  const host = document.getElementById("memoryBody");
  if (!host) return;
  if (!LAYERS.includes(layer)) return;
  host.replaceChildren(el("div", { class: "skeleton", style: "height:80px" }));
  try {
    const out = await api(`/api/${state.tenant}/memory/${layer}`);
    renderMemory(host, out.result || out);
  } catch (err) {
    const msg = err instanceof ApiError ? `Memory view failed (${err.status || "network"})` : "Memory view failed";
    host.replaceChildren(el("div", { class: "error-state", text: msg }));
  }
}

function renderMemory(host, result) {
  host.replaceChildren();
  const counts = result.label_counts || {};
  const max = Math.max(1, ...Object.values(counts));
  const list = el("div", { class: "bar-list" });
  Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([lab, n]) => {
    list.append(el("div", { class: "row" },
      el("span", { text: lab }),
      el("div", { class: "meter" }, el("span", { style: `width:${Math.round((n / max) * 100)}%` })),
      el("span", { class: "tabular", text: String(n) }),
    ));
  });
  host.append(el("p", { class: "muted", text: `edge_touch_count ${result.edge_touch_count ?? 0}` }));
  host.append(list);
  const table = el("table", { class: "samples" });
  table.append(el("thead", {}, el("tr", {}, el("th", { text: "id" }), el("th", { text: "labels" }), el("th", { text: "provenance" }))));
  const tb = el("tbody");
  (result.samples || []).forEach((s) => {
    const labels = Array.isArray(s.labels) ? s.labels.join(", ") : String(s.labels || "");
    const prov = labels.includes("Source") && s.provenance === "real" ? "real" : (s.provenance || "synthetic");
    tb.append(el("tr", {},
      el("td", { text: s.id }),
      el("td", { text: labels }),
      el("td", {}, el("span", { class: prov === "real" ? "badge" : "badge badge-synthetic", text: prov })),
    ));
  });
  table.append(tb);
  host.append(table);
}

export function bindMemoryTabs() {
  const tabs = document.getElementById("memoryTabs");
  if (!tabs) return;
  tabs.replaceChildren();
  LAYERS.forEach((layer, i) => {
    const btn = el("button", {
      class: "btn btn-ghost",
      type: "button",
      role: "tab",
      "aria-selected": i === 0 ? "true" : "false",
      text: layer,
      onclick: () => {
        tabs.querySelectorAll("[role=tab]").forEach((t) => t.setAttribute("aria-selected", t === btn ? "true" : "false"));
        loadMemory(layer);
      },
    });
    tabs.append(btn);
  });
  loadMemory("episodic");
}
