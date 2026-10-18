import { el, trapFocus } from "../api.js";

let toastTimer = 0;

export function showToast(msg) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3200);
}

export function showBanner(on, text) {
  const banner = document.getElementById("healthBanner");
  if (!banner) return;
  banner.classList.toggle("hidden", !on);
  const msg = document.getElementById("healthBannerMsg");
  if (msg && text) msg.textContent = text;
}

export function setBusy(on) {
  document.querySelectorAll("[data-busy]").forEach((btn) => {
    btn.disabled = !!on;
  });
}

export function openModal(id, returnTo) {
  const modal = document.getElementById(id);
  if (!modal) return () => {};
  modal.classList.remove("hidden");
  const panel = modal.querySelector(".modal-panel") || modal;
  const release = trapFocus(panel, () => closeModal(id, returnTo));
  modal._release = release;
  modal._returnTo = returnTo;
  return release;
}

export function closeModal(id, returnTo) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add("hidden");
  modal._release?.();
  (returnTo || modal._returnTo)?.focus?.();
}

export function openDrawer(id, returnTo) {
  const drawer = document.getElementById(id);
  if (!drawer) return;
  drawer.classList.remove("hidden");
  const panel = drawer.querySelector(".drawer-panel") || drawer;
  drawer._release = trapFocus(panel, () => closeDrawer(id, returnTo));
  drawer._returnTo = returnTo;
}

export function closeDrawer(id, returnTo) {
  const drawer = document.getElementById(id);
  if (!drawer) return;
  drawer.classList.add("hidden");
  drawer._release?.();
  (returnTo || drawer._returnTo)?.focus?.();
}

export function confirmReset() {
  return new Promise((resolve) => {
    const yes = document.getElementById("confirmYes");
    const no = document.getElementById("confirmNo");
    const trigger = document.activeElement;
    let settled = false;
    function done(val) {
      if (settled) return;
      settled = true;
      yes.removeEventListener("click", onYes);
      no.removeEventListener("click", onNo);
      closeModal("confirmModal", trigger);
      resolve(val);
    }
    function onYes() { done(true); }
    function onNo() { done(false); }
    yes.addEventListener("click", onYes);
    no.addEventListener("click", onNo);
    openModal("confirmModal", trigger);
    const modal = document.getElementById("confirmModal");
    modal._release?.();
    const panel = modal.querySelector(".modal-panel") || modal;
    modal._release = trapFocus(panel, () => done(false));
  });
}

export function errorBox(host, err, retry) {
  host.replaceChildren();
  const box = el("div", { class: "error-state" },
    el("p", { text: err?.message || "Something went wrong." }),
  );
  if (retry) box.append(el("button", { class: "btn", type: "button", text: "Retry", onclick: retry }));
  host.append(box);
}
