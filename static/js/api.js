export function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

export function html(strings, ...vals) {
  return strings.reduce((acc, part, i) => acc + part + (i < vals.length ? escapeHTML(vals[i]) : ""), "");
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs)) {
    if (val == null || val === false) continue;
    if (key === "class") node.className = val;
    else if (key === "text") node.textContent = String(val);
    else if (key === "dataset") Object.assign(node.dataset, val);
    else if (key.startsWith("on") && typeof val === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), val);
    } else if (val === true) node.setAttribute(key, "");
    else node.setAttribute(key, String(val));
  }
  for (const child of children.flat()) {
    if (child == null) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export class ApiError extends Error {
  constructor(status, path, body) {
    super(`${status} ${path}`);
    this.status = status;
    this.path = path;
    this.body = body;
  }
}

// One private sandbox graph per browser (the server clones the tenant seed on first use),
// so concurrent visitors never step on each other's runs, closes or resets.
let cachedSid = "";
export function sessionId() {
  if (cachedSid) return cachedSid;
  let sid = "";
  try { sid = localStorage.getItem("sentinelSession") || ""; } catch { /* storage blocked */ }
  if (!/^[a-z0-9]{8,40}$/.test(sid)) {
    const raw = window.crypto && crypto.randomUUID ? crypto.randomUUID() : `${Math.random()}${Date.now()}`;
    sid = raw.replace(/[^a-z0-9]/gi, "").toLowerCase().slice(0, 32).padEnd(12, "0");
    try { localStorage.setItem("sentinelSession", sid); } catch { /* per-page id only */ }
  }
  cachedSid = sid;
  return sid;
}

export function authHeaders() {
  const token = (typeof localStorage !== "undefined" && localStorage.getItem("sentinelToken")) || "";
  const h = { "X-Sentinel-Session": sessionId() };
  if (token) h["X-Sentinel-Token"] = token;
  return h;
}

export async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {}, authHeaders());
  let res;
  try {
    res = await fetch(path, Object.assign({}, opts, { headers }));
  } catch (err) {
    throw new ApiError(0, path, String(err));
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, path, text);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("text/event-stream")) return res;
  if (ct.includes("application/json")) return res.json();
  return res;
}

export async function readSSE(res, { onStep, onDone }) {
  if (!res.body) throw new ApiError(0, res.url || "sse", "no stream body");
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let event = "message";
  let gotDone = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const block of parts) {
      let data = "";
      event = "message";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      let payload;
      try { payload = JSON.parse(data); } catch { continue; }
      if (event === "step" && onStep) onStep(payload);
      if (event === "done") {
        gotDone = true;
        if (onDone) await onDone(payload);
      }
    }
  }
  if (!gotDone) throw new ApiError(0, res.url || "sse", "stream ended without a done event");
}

export function trapFocus(root, onClose) {
  const sel = 'button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  // only elements that can really take focus: enabled and rendered (not inside a closed <details>)
  const nodes = () => [...root.querySelectorAll(sel)].filter((n) => !n.disabled && n.getClientRects().length > 0
    && !(n.closest("details:not([open])") && n.tagName !== "SUMMARY"));
  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key !== "Tab") return;
    const list = nodes();
    if (!list.length) return;
    const first = list[0];
    const last = list[list.length - 1];
    const inside = root.contains(document.activeElement);
    if (e.shiftKey && (document.activeElement === first || !inside)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (document.activeElement === last || !inside)) {
      e.preventDefault();
      first.focus();
    }
  }
  function onFocusIn(e) {
    if (!root.contains(e.target)) nodes()[0]?.focus();
  }
  document.addEventListener("keydown", onKey, true);
  document.addEventListener("focusin", onFocusIn);
  queueMicrotask(() => nodes()[0]?.focus());
  return () => {
    document.removeEventListener("keydown", onKey, true);
    document.removeEventListener("focusin", onFocusIn);
  };
}

export function fmtP(p) {
  if (p == null || Number.isNaN(Number(p))) return "—";
  return Number(p).toFixed(2);
}

export function hopChips(signature) {
  return String(signature || "").split(">").filter(Boolean);
}
