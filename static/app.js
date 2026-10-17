/* Cascade Sentinel UI — dark, judge-friendly, no build step. */
(() => {
  const $ = (id) => document.getElementById(id);
  const tenantSel = $("tenant");
  const timeline = $("timeline");
  const recsEl = $("recs");
  const toast = $("toast");
  let cy = null;
  let last2024 = null;
  let last2025 = null;
  let episodeId = null;

  cytoscape.use(cytoscapeDagre);

  function tenant() { return tenantSel.value; }
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 2800);
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(`${res.status} ${path}`);
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("text/event-stream")) return res;
    return res.json();
  }

  function avatar(agent) {
    const letter = (agent || "?").slice(0, 2).toUpperCase();
    return `<span class="avatar ${agent || ""}">${letter}</span>`;
  }

  function addStep(ev) {
    const li = document.createElement("li");
    li.innerHTML = `${avatar(ev.agent)}<div><strong>${ev.tool}</strong><div>${ev.summary || ""}</div></div><span class="ms">${(ev.ms || 0).toFixed(0)}ms</span>`;
    timeline.prepend(li);
  }

  async function readSSE(res, onDone) {
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let event = "message";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const block of parts) {
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const payload = JSON.parse(data);
        if (event === "step") addStep(payload);
        if (event === "done") onDone(payload);
        event = "message";
      }
    }
  }

  function rankOf(kind) {
    return {
      HazardType: 0, CropStage: 1, LivestockStage: 1, Commodity: 2,
      Market: 3, LaborGroup: 4, HealthOutcome: 5, Intervention: 6,
      District: -1, Officer: 7, Forecast: -1,
    }[kind] ?? 3;
  }

  function styleFor() {
    return [
      { selector: "node", style: { "background-color": "#2c3a4a", label: "data(label)", color: "#e8eef5", "font-size": 10, "text-wrap": "wrap", "text-max-width": 110, "text-valign": "bottom", "text-margin-y": 4, width: 26, height: 26, "border-width": 1, "border-color": "#3d4d60" } },
      { selector: "node[kind = 'HazardType']", style: { "background-color": "#e8590c", shape: "diamond", width: 28, height: 28 } },
      { selector: "node[kind = 'HealthOutcome']", style: { "background-color": "#fa5252", shape: "ellipse" } },
      { selector: "node[kind = 'Intervention']", style: { "background-color": "#495057", shape: "round-rectangle", width: 26, height: 18 } },
      { selector: "node.act", style: { "background-color": "#2f9e44" } },
      { selector: "node.defeated_precedent", style: { "background-color": "#868e96", "text-decoration": "line-through" } },
      { selector: "edge", style: { width: 1.4, "line-color": "#3d4d60", "target-arrow-color": "#3d4d60", "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.7 } },
      { selector: "edge.accepted", style: { width: 4, "line-color": "#e8590c", "target-arrow-color": "#fa5252", "line-fill": "linear-gradient", "line-gradient-stop-colors": "#e8590c #fa5252" } },
      { selector: "edge.contested", style: { "line-style": "dashed", "line-color": "#fcc419", "target-arrow-color": "#fcc419", width: 2 } },
      { selector: "edge.defeated", style: { "line-style": "dashed", width: 1, "line-color": "#495057", "target-arrow-color": "#495057" } },
      { selector: "edge.unprecedented", style: { "line-color": "#868e96", "target-arrow-color": "#868e96", width: 2, opacity: 0.55 } },
    ];
  }

  function draw(elements) {
    const nodes = (elements.nodes || []).map((n) => {
      n.data.rank = rankOf(n.data.kind);
      return n;
    });
    const ids = new Set(nodes.map((n) => n.data.id));
    const edges = (elements.edges || []).filter((e) => ids.has(e.data.source) && ids.has(e.data.target));
    if (cy) cy.destroy();
    cy = cytoscape({
      container: $("graph"),
      elements: nodes.concat(edges),
      style: styleFor(),
      layout: { name: "dagre", rankDir: "LR", ranker: "network-simplex", nodeSep: 28, rankSep: 90, padding: 20 },
      minZoom: 0.4, maxZoom: 2.2,
    });
    animateAccepted();
    const unprec = (cy.edges(".unprecedented").length > 0);
    $("unprecBadge").classList.toggle("hidden", !unprec);
  }

  function animateAccepted() {
    const edges = cy.edges(".accepted");
    const hops = [];
    edges.forEach((e) => hops.push(e));
    hops.sort((a, b) => (a.source().data("rank") || 0) - (b.source().data("rank") || 0));
    hops.forEach((e) => e.style("opacity", 0.15));
    hops.forEach((e, i) => {
      setTimeout(() => {
        e.animate({ style: { opacity: 1, width: 4 + (e.data("weight") || 0.5) * 2 } }, { duration: 220 });
      }, i * 250);
    });
  }

  function renderRecs(bundle) {
    const recs = bundle.recommendations || [];
    recsEl.innerHTML = "";
    recs.forEach((r) => {
      const card = document.createElement("article");
      card.className = `card ${r.kind}`;
      const title = r.kind === "escalate" ? (r.message || "UNPRECEDENTED") : (r.intervention_name || r.intervention_id);
      const trials = r.trials || 0;
      const succ = r.successes || 0;
      const p = r.precedent_weight;
      const bar = p == null ? "" : `<div class="bar"><span style="width:${Math.round(p * 100)}%"></span></div><div>${succ} of ${trials} past seasons, P=${p.toFixed(2)}</div>`;
      const analogs = (r.analog_episode_ids || []).slice(0, 4).map((id) => `<span class="chip">${id.replace("ep_lib_", "")}</span>`).join("");
      card.innerHTML = `<h3>${title}</h3>
        <div class="muted">${r.kind}${r.lead_time_days ? " · lead " + r.lead_time_days + "d" : ""}</div>
        ${bar}
        <div class="chips">${analogs}</div>
        <div class="rowbtns">
          <button data-explain="${r.id}">Explain</button>
          <button data-approve="${r.id}">Approve</button>
        </div>`;
      recsEl.appendChild(card);
    });
  }

  async function loadSnapshot(eid) {
    const snap = await api(`/api/${tenant()}/snapshot/${eid}`);
    draw(snap.result.elements);
  }

  async function runSeason(year) {
    timeline.innerHTML = "";
    showToast(`Running season ${year} (synthetic day-1 data)…`);
    const res = await fetch(`/api/${tenant()}/run/${year}`, { method: "POST" });
    await readSSE(res, async (bundle) => {
      episodeId = bundle.episode_id;
      if (year === 2024) last2024 = bundle;
      if (year === 2025) last2025 = bundle;
      renderRecs(bundle);
      await loadSnapshot(bundle.episode_id);
      if (year === 2025 && last2024) showDiff(last2024, last2025);
      showToast(`Season ${year} complete`);
    });
  }

  async function closeEpisode() {
    if (!episodeId) episodeId = `ep_2024_${tenant()}`;
    const out = await api(`/api/${tenant()}/close/${episodeId}`, { method: "POST" });
    const r = out.result;
    showToast(`Write-back done. Reconstruction ${r.reconstruction_pass ? "PASS" : "FAIL"} J=${r.reconstruction_jaccard.toFixed(2)}`);
    const rec = document.createElement("article");
    rec.className = "card";
    rec.innerHTML = `<h3>Write-back</h3><pre class="cypher">${JSON.stringify({
      pass: r.reconstruction_pass,
      jaccard: r.reconstruction_jaccard,
      cool_shelters: r.interventions.worksite_cool_shelters,
      agronomy: r.agents.agronomy,
    }, null, 2)}</pre>`;
    recsEl.prepend(rec);
  }

  async function reset() {
    await api(`/api/${tenant()}/reset`, { method: "POST" });
    timeline.innerHTML = "";
    recsEl.innerHTML = "";
    last2024 = last2025 = episodeId = null;
    if (cy) cy.destroy();
    showToast("Graph reseeded (synthetic archetype)");
  }

  async function explain(id) {
    const out = await api(`/api/${tenant()}/explain/${id}`);
    const r = out.result;
    const hops = (r.path.hops || []).map((h) =>
      `<li>${h.from} <code>${h.type}</code> ${h.to} · w=${h.weight} · src <span class="chip">${h.source || ""}</span></li>`
    ).join("");
    const analogs = (r.analogs || []).map((a) =>
      `<span class="chip">${a.episode_id} sim=${a.similarity.toFixed(2)}</span>`
    ).join(" ");
    const prec = (r.precedents || []).map((p) =>
      `<tr><td>${p.name}</td><td>${p.successes}/${p.trials}</td><td>${p.precedent_weight.toFixed(2)}</td></tr>`
    ).join("");
    const rivals = (r.defeated_rivals || []).map((d) =>
      `<li><strong>${d.agent_id}</strong> ${d.reason}</li>`
    ).join("");
    const cypher = (out.cypher || r.cypher || []).map((c, i) =>
      `<pre class="cypher">${c}<button data-copy="${i}">copy</button></pre>`
    ).join("");
    $("drawerBody").innerHTML = `
      <p><span class="badge">synthetic</span></p>
      <h3>Path</h3><ol>${hops}</ol>
      <h3>Analogs</h3><div class="chips">${analogs || "none ≥ 0.5"}</div>
      <h3>Precedent</h3>
      <table><thead><tr><th>intervention</th><th>succ/trials</th><th>P</th></tr></thead><tbody>${prec}</tbody></table>
      <h3>Defeated rivals</h3><ul>${rivals || "<li>none</li>"}</ul>
      <h3>Owner and audit trail</h3>
      <p>${(r.owner && (r.owner.name || r.owner.id)) || "—"} · ${(r.owner && r.owner.role) || ""}</p>
      <details><summary>Cypher behind this answer</summary>${cypher}</details>`;
    $("drawer").classList.remove("hidden");
    $("drawerBody").querySelectorAll("[data-copy]").forEach((btn) => {
      btn.onclick = () => {
        const pre = btn.parentElement;
        navigator.clipboard.writeText(pre.innerText.replace("copy", "").trim());
        showToast("Cypher copied");
      };
    });
  }

  function showDiff(a, b) {
    const rows = [];
    const ah = Object.fromEntries((a.hypotheses || []).map((h) => [h.agent_id + h.path_signature, h]));
    const bh = Object.fromEntries((b.hypotheses || []).map((h) => [h.agent_id + h.path_signature, h]));
    for (const k of new Set([...Object.keys(ah), ...Object.keys(bh)])) {
      const sa = ah[k] ? (ah[k].status === "proposed" ? "contested" : ah[k].status) : "—";
      const sb = bh[k] ? (bh[k].status === "proposed" ? "contested" : bh[k].status) : "—";
      if (sa !== sb) rows.push([k.slice(0, 48), sa, sb]);
    }
    const ar = new Set((a.recommendations || []).map((r) => r.kind + ":" + (r.intervention_id || "esc")));
    const br = new Set((b.recommendations || []).map((r) => r.kind + ":" + (r.intervention_id || "esc")));
    for (const x of br) if (!ar.has(x)) rows.push(["+ " + x, "—", x.split(":")[0]]);
    for (const x of ar) if (!br.has(x)) rows.push(["− " + x, x.split(":")[0], "—"]);
    $("diffBody").innerHTML = `<p>${rows.length} changes after write-back. Synthetic data.</p>
      <div class="diff"><strong>change</strong><strong>2024</strong><strong>2025</strong>
      ${rows.map((r) => `<div>${r[0]}</div><div>${r[1]}</div><div>${r[2]}</div>`).join("")}</div>`;
    $("diffModal").classList.remove("hidden");
  }

  recsEl.addEventListener("click", async (e) => {
    const expl = e.target.getAttribute("data-explain");
    const appr = e.target.getAttribute("data-approve");
    if (expl) await explain(expl);
    if (appr) {
      const out = await api(`/api/${tenant()}/approve/${appr}`, { method: "POST" });
      showToast(`Approved by ${out.officer.name}`);
    }
  });

  document.querySelectorAll(".legend input[data-layer]").forEach((box) => {
    box.addEventListener("change", () => {
      if (!cy) return;
      const cls = box.getAttribute("data-layer");
      cy.nodes("." + cls).style("display", box.checked ? "element" : "none");
    });
  });

  $("btn2024").onclick = () => runSeason(2024);
  $("btn2025").onclick = () => runSeason(2025);
  $("btnClose").onclick = () => closeEpisode();
  $("btnReset").onclick = () => reset();
  $("drawerClose").onclick = () => $("drawer").classList.add("hidden");
  $("diffClose").onclick = () => $("diffModal").classList.add("hidden");
  tenantSel.onchange = () => reset();

  showToast("Cascade Sentinel ready. Data are synthetic archetypes.");
})();
