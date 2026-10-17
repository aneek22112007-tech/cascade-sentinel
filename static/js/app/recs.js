import { api, el, fmtP, hopChips, ApiError } from "../api.js";
import { state } from "./state.js";
import { highlightPath } from "./graph.js";
import { openExplain } from "./explain.js";
import { showToast } from "./ui.js";

function analogLabel(id) {
  return String(id || "").replace(/^ep_lib_/, "");
}

function recMatches(r, filter) {
  if (filter === "all") return true;
  return r.kind === filter;
}

export function renderRecs(bundle) {
  const host = document.getElementById("recs");
  const filters = document.getElementById("recFilters");
  if (!host) return;
  const recs = bundle?.recommendations || [];
  const counts = { all: recs.length, act: 0, defeated_precedent: 0, escalate: 0 };
  recs.forEach((r) => { if (counts[r.kind] != null) counts[r.kind] += 1; });
  if (filters) {
    filters.replaceChildren();
    [["all", "All"], ["act", "Act"], ["defeated_precedent", "Weak precedent"], ["escalate", "Escalate"]].forEach(([id, label]) => {
      const btn = el("button", {
        class: "btn btn-ghost",
        type: "button",
        role: "tab",
        "aria-selected": state.recFilter === id ? "true" : "false",
        text: `${label} ${counts[id] ?? 0}`,
        onclick: () => { state.recFilter = id; renderRecs(bundle); },
      });
      filters.append(btn);
    });
  }
  host.replaceChildren();
  if (!recs.length) {
    host.append(el("div", { class: "empty", text: "Run Season 2024 to see precedent-gated recommendations." }));
    return;
  }
  const visible = recs.filter((r) => recMatches(r, state.recFilter));
  for (const r of visible) {
    host.append(recCard(r));
  }
}

function recCard(r) {
  const card = el("article", { class: `card rec-card ${r.kind}`, dataset: { id: r.id, path: r.path_signature || "" } });
  card.addEventListener("mouseenter", () => highlightPath(r.path_signature));
  card.addEventListener("mouseleave", () => highlightPath(null));
  card.addEventListener("focusin", () => highlightPath(r.path_signature));
  card.addEventListener("focusout", () => highlightPath(null));

  const title = r.kind === "escalate"
    ? (r.message || "UNPRECEDENTED: escalate to district officer")
    : (r.intervention_name || r.intervention_id || "Recommendation");
  const h3 = el("h3", { text: title });
  card.append(h3);

  if (r.kind === "defeated_precedent") {
    card.append(el("span", { class: "chip chip-defeated", text: "Weak precedent" }));
  }
  if (r.kind === "act") {
    card.append(el("span", { class: "chip chip-act", text: "act" }));
  }
  if (r.kind === "escalate") {
    card.append(el("span", { class: "chip chip-escalate", text: "UNPRECEDENTED" }));
    const ownerName = r.escalated_to_name || r.escalated_to?.name;
    if (ownerName) card.append(el("p", { class: "muted", text: ownerName }));
  }

  if (r.lead_time_days != null) {
    card.append(el("p", { class: "muted", text: `lead time ${r.lead_time_days} days` }));
  }
  if (r.precedent_weight != null) {
    const p = Number(r.precedent_weight);
    const bar = el("div", { class: `progress ${p < 0.5 ? "weak" : ""}`, title: "Precedent threshold 0.5" });
    bar.append(el("span", { style: `width:${Math.round(Math.min(1, p) * 100)}%` }));
    card.append(bar);
    const trials = r.trials || 0;
    const succ = r.successes || 0;
    card.append(el("p", { class: "muted tabular", text: `${succ} of ${trials} past seasons, P=${fmtP(p)}` }));
  }
  if (r.score != null) card.append(el("p", { class: "muted tabular", text: `score ${Number(r.score).toFixed(3)}` }));

  const chips = el("div", { class: "path-chips" });
  hopChips(r.path_signature).forEach((h) => chips.append(el("span", { class: "chip", text: h })));
  card.append(chips);

  const analogs = el("div", { class: "row" });
  (r.analog_episode_ids || []).slice(0, 6).forEach((id) => analogs.append(el("span", { class: "chip", text: analogLabel(id) })));
  if (analogs.childNodes.length) card.append(analogs);

  const actions = el("div", { class: "row" });
  actions.append(el("button", { class: "btn", type: "button", text: "Explain", onclick: () => openExplain(r.id) }));
  if (r.kind === "act") {
    actions.append(el("button", { class: "btn btn-primary", type: "button", text: "Approve", onclick: () => approve(r, card) }));
  }
  card.append(actions);

  if (state.approved[r.id]) {
    markApproved(card, state.approved[r.id]);
  }
  return card;
}

function markApproved(card, officer) {
  card.classList.add("approved");
  const note = el("p", { class: "muted", text: `Approved by ${officer.name}, ${officer.role}` });
  card.append(note);
  card.querySelectorAll("button").forEach((b) => {
    if (b.textContent === "Approve") b.disabled = true;
  });
}

async function approve(r, card) {
  const btn = [...card.querySelectorAll("button")].find((b) => b.textContent === "Approve");
  if (btn) {
    btn.disabled = true;
    btn.prepend(el("span", { class: "spin", "aria-hidden": "true" }));
  }
  try {
    const out = await api(`/api/${state.tenant}/approve/${encodeURIComponent(r.id)}`, { method: "POST" });
    state.approved[r.id] = out.officer;
    markApproved(card, out.officer);
    showToast(`Approved by ${out.officer.name}, ${out.officer.role}`);
  } catch (err) {
    if (btn) { btn.disabled = false; btn.querySelector(".spin")?.remove(); }
    const msg = err instanceof ApiError ? `Could not approve (${err.status || "network"})` : "Could not approve";
    card.append(el("p", { class: "error-state", text: msg }));
  }
}

export function renderClosePanel(result) {
  const host = document.getElementById("closePanel");
  if (!host || !result) return;
  host.replaceChildren();
  const pass = result.reconstruction_pass;
  host.append(
    el("div", { class: "card writeback" },
      el("h3", { text: "Close episode" }),
      el("p", {},
        el("strong", { class: "tabular", text: `Jaccard ${Number(result.reconstruction_jaccard ?? 0).toFixed(2)}` }),
        document.createTextNode(" "),
        el("span", { class: `chip ${pass ? "chip-act" : "chip-defeated"}`, text: pass ? "PASS" : "FAIL" }),
      ),
      el("div", { class: "path-chips" }, ...hopChips(result.realized_signature || (result.realized_path || []).join(">")).map((h) => el("span", { class: "chip", text: h }))),
    ),
  );
  const ivTable = el("table");
  ivTable.append(el("thead", {}, el("tr", {}, el("th", { text: "intervention" }), el("th", { text: "trials" }), el("th", { text: "successes" }), el("th", { text: "P" }))));
  const tb = el("tbody");
  Object.entries(result.interventions || {}).forEach(([id, row]) => {
    const b = row.before || {};
    const a = row.after || {};
    const changed = b.trials !== a.trials || b.precedent_weight !== a.precedent_weight;
    const tr = el("tr", { class: changed ? "chg" : "" });
    tr.append(
      el("td", { text: id }),
      el("td", { class: "tabular", text: `${b.trials} → ${a.trials}` }),
      el("td", { class: "tabular", text: `${b.successes} → ${a.successes}` }),
      el("td", { class: "tabular", text: `${fmtP(b.precedent_weight)} → ${fmtP(a.precedent_weight)}` }),
    );
    tb.append(tr);
  });
  ivTable.append(tb);
  const agTable = el("table");
  agTable.append(el("thead", {}, el("tr", {}, el("th", { text: "agent" }), el("th", { text: "hits/misses" }), el("th", { text: "C" }), el("th", { text: "verdict" }))));
  const atb = el("tbody");
  Object.entries(result.agents || {}).forEach(([id, row]) => {
    const b = row.before || {};
    const a = row.after || {};
    const tr = el("tr");
    tr.append(
      el("td", { text: id }),
      el("td", { class: "tabular", text: `${b.hits}/${b.misses} → ${a.hits}/${a.misses}` }),
      el("td", { class: "tabular", text: `${fmtP(b.credibility)} → ${fmtP(a.credibility)}` }),
      el("td", { text: row.verdict || "" }),
    );
    atb.append(tr);
  });
  agTable.append(atb);
  host.append(el("div", { class: "card writeback" }, el("h3", { text: "Interventions" }), ivTable));
  host.append(el("div", { class: "card writeback" }, el("h3", { text: "Agents" }), agTable));
}
