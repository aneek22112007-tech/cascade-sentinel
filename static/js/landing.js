const KEY = "sentinelTheme";

function currentTheme() {
  return document.documentElement.getAttribute("data-theme")
    || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(KEY, theme);
  const btn = document.getElementById("themeToggle");
  if (btn) {
    btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    btn.textContent = theme === "dark" ? "Light" : "Dark";
  }
}

const stored = localStorage.getItem(KEY);
if (stored === "light" || stored === "dark") applyTheme(stored);
else applyTheme(matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");

document.getElementById("themeToggle")?.addEventListener("click", () => {
  applyTheme(currentTheme() === "dark" ? "light" : "dark");
});

document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const pre = btn.closest(".codeblock");
    const text = pre ? pre.innerText.replace(/\bCopy\b/g, "").trim() : "";
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "Copied";
      setTimeout(() => { btn.textContent = "Copy"; }, 1200);
    } catch {
      btn.textContent = "Failed";
    }
  });
});
