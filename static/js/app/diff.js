import { api, el } from "../api.js";
import { state, episodeIdFor } from "./state.js";
import { openModal } from "./ui.js";

// Canonical metric: "path-level changes". Mirrors sentinel/backtest.py::diff_seasons
// exactly, so the dashboard, `make backtest` and the landing page report one number.
// A change is (a) a hypothesis (agent, path) whose verdict differs between seasons, or
// (b) a recommendation (kind, intervention, path) gained or lost.
function verdict(h) {
  if (!h) return "—";
  return h.status && h.status !== "proposed" ? h.status : "contested";
}

export function diffBundles(a, b) {
  const rows = [];
  const key = (h) => h.agent_id + "\u0000" + h.path_signature;
  const ah = new Map((a.hypotheses || []).map((h) => [key(h), h]));
  const bh = new Map((b.hypotheses || []).map((h) => [key(h), h]));
  const keys = [...new Set([...ah.keys(), ...bh.keys()])].sort();
  for (const k of keys) {
    const sa = verdict(ah.get(k));
    const sb = verdict(bh.get(k));
    const [agent, path] = k.split("\u0000");
    if (sa !== sb) rows.push({ type: "hyp", label: `hyp ${agent}`, path, a: sa, b: sb });
  }
  const rkey = (r) => [r.kind, r.intervention_id || "", r.path_signature].join("\u0000");
  const ar = new Set((a.recommendations || []).map(rkey));
  const br = new Set((b.recommendations || []).map(rkey));
  const recRow = (k, sign) => {
    const [kind, iid, path] = k.split("\u0000");
    return { type: "rec", label: iid ? `${sign} ${kind} · ${iid}` : `${sign} ${kind}`, path, a: sign === "+" ? "—" : kind, b: sign === "+" ? kind : "—" };
  };
  [...br].filter((x) => !ar.has(x)).sort().forEach((x) => rows.push(recRow(x, "+")));
  [...ar].filter((x) => !br.has(x)).sort().forEach((x) => rows.push(recRow(x, "−")));
  return rows;
}

export async function showDiff(a, b, { recsOnly = false } = {}) {
  const body = document.getElementById("diffBody");
  const rows = diffBundles(a || { recommendations: [] }, b || { recommendations: [] });
  body.replaceChildren();
  if (recsOnly) {
    body.append(el("p", { class: "muted", text: "Hypothesis diffs need a fresh 2024 run in this tab. Showing recommendation changes only. Synthetic data." }));
  } else {
    body.append(
      el("p", { class: "diff-count" }, [el("strong", { text: `${rows.length} path-level changes` }), document.createTextNode(" after write-back")]),
      el("p", { class: "muted small", text: "Path-level change = a hypothesis verdict that flipped, or a recommendation gained (+) or lost (−), counted per cascade path. Same metric as make backtest. Synthetic data." }),
    );
  }
  const grid = el("div", { class: "diff-grid" });
  grid.append(el("strong", { text: "change" }), el("strong", { text: "2024" }), el("strong", { text: "2025" }));
  rows.forEach((r) => {
    const cell = el("div", { class: "diff-what" }, [el("span", { class: "diff-label", text: r.label.replace(/_/g, " ") }), el("code", { class: "diff-path", text: r.path.split(">").join(" › "), title: r.path })]);
    const nice = (v) => v.replace(/_/g, " ");
    grid.append(cell, el("div", { class: `diff-st st-${r.a}`, text: nice(r.a) }), el("div", { class: `diff-st st-${r.b}`, text: nice(r.b) }));
  });
  body.append(grid);
  openModal("diffModal", document.getElementById("btn2025"));
}

export async function showDiffAfter2025(bundle2025) {
  if (state.bundle2024) {
    await showDiff(state.bundle2024, bundle2025);
    return;
  }
  try {
    const recs = await api(`/api/${state.tenant}/recommendations/${episodeIdFor(2024)}`);
    await showDiff({ recommendations: recs.recommendations || [] }, bundle2025, { recsOnly: true });
  } catch {
    await showDiff({ recommendations: [] }, bundle2025, { recsOnly: true });
  }
}
