import { api, el } from "../api.js";
import { state, episodeIdFor } from "./state.js";
import { openModal } from "./ui.js";

function statusOf(h) {
  if (!h) return "—";
  if (h.display_status) return h.display_status;
  return h.status === "proposed" ? "contested" : h.status;
}

export function diffBundles(a, b) {
  const rows = [];
  const ah = Object.fromEntries((a.hypotheses || []).map((h) => [h.agent_id + h.path_signature, h]));
  const bh = Object.fromEntries((b.hypotheses || []).map((h) => [h.agent_id + h.path_signature, h]));
  for (const k of new Set([...Object.keys(ah), ...Object.keys(bh)])) {
    const sa = statusOf(ah[k]);
    const sb = statusOf(bh[k]);
    if (sa !== sb) rows.push([k.slice(0, 64), sa, sb]);
  }
  const ar = new Set((a.recommendations || []).map((r) => r.kind + ":" + (r.intervention_id || "esc")));
  const br = new Set((b.recommendations || []).map((r) => r.kind + ":" + (r.intervention_id || "esc")));
  for (const x of br) if (!ar.has(x)) rows.push(["+ " + x, "—", x.split(":")[0]]);
  for (const x of ar) if (!br.has(x)) rows.push(["− " + x, x.split(":")[0], "—"]);
  return rows;
}

export async function showDiff(a, b, { recsOnly = false } = {}) {
  const body = document.getElementById("diffBody");
  const rows = diffBundles(a || { recommendations: [] }, b || { recommendations: [] });
  body.replaceChildren();
  if (recsOnly) {
    body.append(el("p", { class: "muted", text: "Hypothesis diffs need a fresh 2024 run in this tab. Showing recommendation changes only. Synthetic data." }));
  } else {
    body.append(el("p", { text: `${rows.length} changes after write-back. Synthetic data.` }));
  }
  const grid = el("div", { class: "diff-grid" });
  grid.append(el("strong", { text: "change" }), el("strong", { text: "2024" }), el("strong", { text: "2025" }));
  rows.forEach((r) => {
    grid.append(el("div", { text: r[0] }), el("div", { text: r[1] }), el("div", { text: r[2] }));
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
