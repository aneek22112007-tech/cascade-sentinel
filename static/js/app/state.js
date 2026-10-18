export const state = {
  tenant: "demo",
  episodeId: null,
  year: 2024,
  bundle2024: null,
  bundle2025: null,
  lastBundle: null,
  closeResult: null,
  health: null,
  tenants: [],
  inFlight: false,
  approved: {},
  recFilter: "all",
  mobilePane: "graph",
  layers: {
    "layer-corridor": true,
    "layer-semantic": true,
    "layer-episodic": true,
    "layer-procedural": true,
    "layer-governance": true,
  },
};

const THEME_KEY = "sentinelTheme";

export function getTheme() {
  return document.documentElement.getAttribute("data-theme")
    || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
}

export function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
}

export function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") setTheme(stored);
  else setTheme(matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
}

export function episodeIdFor(year, tenant = state.tenant) {
  return `ep_${year}_${tenant}`;
}
