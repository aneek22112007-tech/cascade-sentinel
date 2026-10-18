import { api, el, fmtP, ApiError } from "../api.js";
import { state } from "./state.js";
import { openDrawer, closeDrawer, showToast } from "./ui.js";

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
  const ta = el("textarea", { readonly: true, style: "position:fixed;left:-9999px;top:0" });
  ta.value = text;
  document.body.append(ta);
  ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  if (!ok) throw new Error("copy failed");
}

function codeBlock(text) {
  const pre = el("pre", { class: "codeblock" });
  pre.append(document.createTextNode(text || ""));
  const btn = el("button", {
    class: "btn copy",
    type: "button",
    text: "Copy",
    "aria-label": "Copy Cypher query",
    onclick: async () => {
      try {
        await copyText(text || "");
        btn.textContent = "Copied";
        showToast("Cypher copied");
        setTimeout(() => { btn.textContent = "Copy"; }, 1200);
      } catch {
        btn.textContent = "Failed";
      }
    },
  });
  pre.append(btn);
  return pre;
}

export async function openExplain(recId) {
  const body = document.getElementById("drawerBody");
  const trigger = document.activeElement;
  body.replaceChildren(el("div", { class: "skeleton", style: "height:120px" }));
  openDrawer("drawer", trigger);
  try {
    const out = await api(`/api/${state.tenant}/explain/${encodeURIComponent(recId)}`);
    const r = out.result || {};
    renderExplain(body, r, out.cypher || r.cypher || []);
  } catch (err) {
    const msg = err instanceof ApiError ? `Explain failed (${err.status || "network"})` : "Explain failed";
    body.replaceChildren(el("div", { class: "error-state", text: msg }));
  }
}

function renderExplain(body, r, cypher) {
  body.replaceChildren();
  body.append(el("p", {}, el("span", { class: "badge badge-synthetic", text: "synthetic" })));

  body.append(el("h3", { text: "Path" }));
  const ol = el("ol");
  (r.path?.hops || []).forEach((h) => {
    const li = el("li");
    li.append(
      document.createTextNode(`${h.from} `),
      el("code", { text: h.type }),
      document.createTextNode(` ${h.to} · w=${h.weight} · conf=${h.confidence} · lag=${h.lag_days ?? 0} `),
      el("span", { class: "chip", text: h.source || "" }),
    );
    ol.append(li);
  });
  body.append(ol);

  body.append(el("h3", { text: "Analogs" }));
  const analogs = el("div", { class: "row" });
  (r.analogs || []).forEach((a) => {
    analogs.append(el("span", { class: "chip", text: `${a.episode_id} sim=${Number(a.similarity || 0).toFixed(2)} y=${a.year ?? ""}` }));
  });
  if (!analogs.childNodes.length) analogs.append(el("span", { class: "muted", text: "none ≥ 0.5" }));
  body.append(analogs);

  body.append(el("h3", { text: "Precedent" }));
  const table = el("table", { class: "samples" });
  table.append(el("thead", {}, el("tr", {}, el("th", { text: "intervention" }), el("th", { text: "succ/trials" }), el("th", { text: "P" }), el("th", { text: "in analog" }))));
  const tb = el("tbody");
  (r.precedents || []).forEach((p) => {
    tb.append(el("tr", {},
      el("td", { text: p.name || p.id }),
      el("td", { class: "tabular", text: `${p.successes}/${p.trials}` }),
      el("td", { class: "tabular", text: fmtP(p.precedent_weight) }),
      el("td", { text: p.in_analog ? "yes" : "no" }),
    ));
  });
  table.append(tb);
  body.append(table);

  body.append(el("h3", { text: "Defeated rivals" }));
  const ul = el("ul");
  (r.defeated_rivals || []).forEach((d) => {
    ul.append(el("li", {}, el("strong", { text: d.agent_id || "" }), document.createTextNode(" " + (d.reason || ""))));
  });
  if (!ul.childNodes.length) ul.append(el("li", { text: "none" }));
  body.append(ul);

  body.append(el("h3", { text: "Sources" }));
  const srcs = el("ul");
  (r.sources || []).forEach((s) => {
    const li = el("li");
    if (s.url) li.append(el("a", { href: s.url, target: "_blank", rel: "noopener", text: s.title || s.id }));
    else li.append(document.createTextNode(s.title || s.id || ""));
    li.append(document.createTextNode(" "));
    li.append(el("span", { class: "badge", text: s.provenance || "synthetic" }));
    srcs.append(li);
  });
  if (!srcs.childNodes.length) srcs.append(el("li", { class: "muted", text: "none listed" }));
  body.append(srcs);

  body.append(el("h3", { text: "Owner and audit trail" }));
  const owner = r.owner || {};
  body.append(el("p", { text: `${owner.name || owner.id || "—"} · ${owner.role || ""}` }));

  const details = el("details");
  details.append(el("summary", { text: "Cypher behind this answer" }));
  (cypher || []).forEach((c) => details.append(codeBlock(c)));
  body.append(details);
}

export function bindExplainClose() {
  document.getElementById("drawerClose")?.addEventListener("click", () => closeDrawer("drawer"));
}
