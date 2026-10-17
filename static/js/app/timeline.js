import { el } from "../api.js";

function phaseOf(ev) {
  const tool = ev.tool || "";
  const summary = ev.summary || "";
  if (tool === "open_episode" || tool === "enumerate_cascade_paths") return "Setup";
  if (tool === "propose_hypothesis") return "Proposals";
  if (tool === "support_hypothesis" || tool === "attack_hypothesis") {
    return String(summary).startsWith("round2") ? "Round 2" : "Critique";
  }
  if (tool === "compute_accepted_risk") return "Adjudication";
  if (tool === "recommend_action") return "Recommendations";
  return "Run";
}

let lastPhase = "";
let stepCount = 0;

export function resetTimeline() {
  lastPhase = "";
  stepCount = 0;
  const ol = document.getElementById("timeline");
  if (ol) ol.replaceChildren();
  const counter = document.getElementById("stepCount");
  if (counter) counter.textContent = "0 steps";
}

export function addStep(ev) {
  const ol = document.getElementById("timeline");
  if (!ol) return;
  const phase = phaseOf(ev);
  if (phase !== lastPhase) {
    ol.append(el("li", { class: "phase-label", text: phase }));
    lastPhase = phase;
  }
  const agent = ev.agent || "orchestrator";
  const initials = agent.slice(0, 2).toUpperCase();
  const li = el(
    "li",
    {},
    el("span", { class: `avatar ${agent}`, text: initials, title: agent, "aria-label": agent }),
    el("div", {},
      el("strong", { text: ev.tool || "" }),
      el("div", { class: "muted", text: ev.summary || "" }),
    ),
    el("span", { class: "ms tabular muted", text: `${Math.round(ev.ms || 0)}ms` }),
  );
  ol.append(li);
  stepCount += 1;
  const counter = document.getElementById("stepCount");
  if (counter) counter.textContent = `${stepCount} steps`;
  ol.parentElement?.scrollTo?.({ top: ol.parentElement.scrollHeight });
}

function displayStatus(h) {
  if (h.display_status) return h.display_status;
  if (h.status === "proposed") return "contested";
  return h.status || "";
}

export function renderHypotheses(hyps) {
  const host = document.getElementById("hyps");
  if (!host) return;
  host.replaceChildren();
  if (!hyps?.length) {
    host.append(el("p", { class: "muted", text: "Hypotheses appear after a season run." }));
    return;
  }
  for (const h of hyps) {
    const st = displayStatus(h);
    const item = el("article", { class: "hyp-item", dataset: { path: h.path_signature || "" } });
    item.append(
      el("div", { class: "row" },
        el("span", { class: `avatar ${h.agent_id || ""}`, text: (h.agent_id || "?").slice(0, 2).toUpperCase() }),
        el("strong", { text: h.agent_id || "" }),
        el("span", { class: `chip chip-${st}`, text: st }),
      ),
      el("p", { text: h.claim || "" }),
      el("div", { class: "sa-bars" },
        el("div", { text: `eff ${Number(h.eff_confidence || 0).toFixed(2)}` }),
        el("div", { text: `support ${Number(h.support || 0).toFixed(2)}` }),
        el("div", { class: "progress" }, el("span", { style: `width:${Math.min(100, Number(h.support || 0) * 100)}%` })),
        el("div", { text: `attack ${Number(h.attack || 0).toFixed(2)}` }),
        el("div", { class: "progress weak" }, el("span", { style: `width:${Math.min(100, Number(h.attack || 0) * 100)}%` })),
      ),
      el("p", { class: "reason", text: h.reason || "" }),
    );
    host.append(item);
  }
}

export function renderRationale(text) {
  const host = document.getElementById("rationale");
  if (!host) return;
  host.textContent = text || "";
}
