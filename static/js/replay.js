/* Static replay shim for the GitHub Pages build.
 * Patches window.fetch so the unchanged dashboard (/app) talks to JSON recorded from real
 * FalkorDB runs by `python -m sentinel.export_static`, instead of a live API.
 * Flow per tenant (same order as the backtest double run): fresh -> run 2024 -> close -> run 2025.
 */
(function () {
  "use strict";
  var DATA = window.SENTINEL_DATA || "../data";
  var realFetch = window.fetch.bind(window);
  var cache = {};
  var ORDER = ["fresh", "ran2024", "closed2024", "ran2025"];
  var KEY = "sentinelReplayStage";

  function stages() { try { return JSON.parse(sessionStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } }
  function stageOf(t) { return stages()[t] || "fresh"; }
  function setStage(t, s) { var all = stages(); all[t] = s; sessionStorage.setItem(KEY, JSON.stringify(all)); }

  function load(name) {
    if (!cache[name]) cache[name] = realFetch(DATA + "/" + name + ".json").then(function (r) {
      if (!r.ok) throw new Error("replay data " + name + " " + r.status);
      return r.json();
    });
    return cache[name];
  }
  function json(body, status) {
    return new Response(JSON.stringify(body), { status: status || 200, headers: { "content-type": "application/json", "x-sentinel-replay": "1" } });
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function sse(steps, done) {
    var enc = new TextEncoder();
    var stream = new ReadableStream({
      start: async function (ctl) {
        for (var i = 0; i < steps.length; i++) {
          ctl.enqueue(enc.encode("event: step\ndata: " + JSON.stringify(steps[i]) + "\n\n"));
          await sleep(Math.min(260, 40 + (steps[i].ms || 0) * 4)); // paced replay of recorded steps
        }
        ctl.enqueue(enc.encode("event: done\ndata: " + JSON.stringify(done) + "\n\n"));
        ctl.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream", "x-sentinel-replay": "1" } });
  }
  function lookup(data, stage, path) {
    // newest stage first back to fresh: reads persist until the graph changes
    for (var i = ORDER.indexOf(stage); i >= 0; i--) {
      var hit = data.stages[ORDER[i]] && data.stages[ORDER[i]][path];
      if (hit) return hit;
    }
    return null;
  }
  var ORDER_MSG = "Static replay follows the recorded order: Run 2024 → Close episode → Run 2025. Use Reset to start over.";

  async function handle(path, method) {
    if (/\/health$/.test(path)) {
      var meta = await load("meta");
      var h = Object.assign({}, meta.health, { replay: true, recorded_at: meta.recorded_at });
      return json(h);
    }
    if (/\/api\/tenants$/.test(path)) return json((await load("meta")).tenants);
    var m = path.match(/\/api\/([^/]+)\/(.*)$/);
    if (!m) return json({ detail: "not in replay" }, 404);
    var tenant = m[1], rest = m[2];
    var data = await load(tenant);
    var stage = stageOf(tenant);
    var canon = "/api/" + tenant + "/" + rest;

    if (method === "POST") {
      if (rest === "reset") { setStage(tenant, "fresh"); return json(data.actions.reset); }
      var run = rest.match(/^run\/(\d{4})/);
      if (run) {
        var y = run[1];
        if (y === "2024" && (stage === "fresh" || stage === "ran2024")) {
          setStage(tenant, "ran2024");
          return sse(data.actions.run2024.steps, data.actions.run2024.done);
        }
        if (y === "2025" && (stage === "closed2024" || stage === "ran2025")) {
          setStage(tenant, "ran2025");
          return sse(data.actions.run2025.steps, data.actions.run2025.done);
        }
        return json({ detail: ORDER_MSG }, 409);
      }
      if (/^close\//.test(rest)) {
        if (stage !== "ran2024" && stage !== "closed2024") return json({ detail: ORDER_MSG }, 409);
        setStage(tenant, "closed2024");
        return json(data.actions.close2024.body);
      }
      if (/^approve\//.test(rest)) {
        return json({ ok: true, replay: true, officer: { id: "district_officer", name: "District officer (replay)", role: "approval not persisted in static replay" } });
      }
      return json({ detail: "not available in static replay" }, 405);
    }
    var hit = lookup(data, stage, canon.split("?")[0]);
    if (hit) return json(hit.body, hit.status);
    return json({ detail: "not recorded at this stage of the replay" }, 404);
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    var u;
    try { u = new URL(url, location.href); } catch (e) { return realFetch(input, init); }
    if (u.origin === location.origin && (/\/api\//.test(u.pathname) || /\/health$/.test(u.pathname)) && !/\/data\//.test(u.pathname)) {
      return handle(u.pathname, method).catch(function (err) { return json({ detail: String(err) }, 500); });
    }
    return realFetch(input, init);
  };
  window.SENTINEL_REPLAY = true;
})();
