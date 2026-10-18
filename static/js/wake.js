// Pages build only: the live demo runs on a free Render instance that sleeps when idle.
// Clicking "Launch live demo" pings /healthz (CORS-open) until it answers, then navigates;
// after 60 s it offers the recorded replay instead of leaving the visitor staring at a blank tab.
(() => {
  const links = [...document.querySelectorAll("a[data-live-cta]")];
  if (!links.length) return;
  const LIVE = new URL(links[0].href).origin;
  let box = null, timer = null, waking = false, gen = 0;

  function ui(target) {
    if (!box) {
      box = document.createElement("div");
      box.className = "wake-toast";
      box.setAttribute("role", "status");
      box.setAttribute("aria-live", "polite");
      document.body.appendChild(box);
    }
    box.innerHTML = '<span class="wake-dot" aria-hidden="true"></span><span class="wake-msg">Waking live server… <span class="wake-t">0</span>s</span>' +
      ' <a class="wake-skip" href="' + target + '">Open anyway</a> <button type="button" class="wake-x" aria-label="Cancel">×</button>';
    box.hidden = false;
    box.querySelector(".wake-x").onclick = stop;
    return box;
  }
  function stop() { waking = false; gen++; clearInterval(timer); if (box) box.hidden = true; }

  async function ping() {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 8000);
    try {
      const r = await fetch(LIVE + "/healthz?t=" + Date.now(), { cache: "no-store", signal: ctl.signal });
      if (!r.ok) return false;
      const j = await r.json();
      return j && j.ok === true;
    } catch { return false; } finally { clearTimeout(t); }
  }

  async function wake(target) {
    if (waking) return;
    waking = true;
    const my = ++gen;
    const el = ui(target);
    const t0 = Date.now();
    timer = setInterval(() => {
      const s = Math.round((Date.now() - t0) / 1000);
      const tEl = el.querySelector(".wake-t"); if (tEl) tEl.textContent = s;
      if (s >= 60 && !el.querySelector(".wake-replay")) {
        el.querySelector(".wake-msg").innerHTML = 'Still waking (free instance)… <span class="wake-t">' + s + '</span>s';
        el.insertAdjacentHTML("beforeend", ' <a class="wake-replay" href="app/">Open recorded replay instead</a>');
      }
    }, 500);
    while (waking && my === gen) {
      if (await ping()) { if (waking && my === gen) { clearInterval(timer); location.href = target; } return; }
      await new Promise((r) => setTimeout(r, 2500));
    }
  }

  for (const a of links) {
    a.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; // new tab: let it go
      e.preventDefault();
      wake(a.href);
    });
  }
})();
