# UI QA checklist: landing (/) and dashboard (/app)

Scope: GitHub Pages build (`python -m sentinel.build_pages`) and the live FastAPI app, which share the same HTML/CSS/JS.
Viewports: 1440x900, 1280x800, 1024x768, 768x1024, 390x844, 360x740. Also checked: reduced motion, no WebGL, light theme, keyboard only.

Tooling: Playwright-core on headless Chrome (SwiftShader WebGL), axe-core 4.x, Lighthouse 12.
Harness scripts: `qa.mjs` covers sections, axe, overflow, tab walk, label clipping, rail overlap and broken click orders. `extra.mjs` covers reduced motion, no WebGL, light theme and keyboard/focus trap.
Screenshot names below refer to the harness output (`landing-<vp>-<section>.png`, `app-<vp>-<step>.png`). The final live set is in `docs/screenshots/qa/`.

Severity: **major** means broken, inaccessible (axe serious/critical) or misleading. **minor** means cosmetic, moderate a11y or polish.

## Metric decision: "path-level changes"

The dashboard popup said **6 changes**, but `make backtest` printed **14 diffs**. The two counted different things: the UI keyed recommendations without the path, and it used `display_status`.

There is now one definition: a **path-level change** is a hypothesis `(agent, path)` whose verdict flipped, or a recommendation `(kind, intervention, path)` that was gained (+) or lost (−).
- `static/js/app/diff.js` mirrors `sentinel/backtest.py::diff_seasons` exactly.
- Demo: **14**. district_b: **5**.
- The same label is used in the dashboard ("14 path-level changes after write-back" plus a one-line definition), the CLI ("14 path-level changes (...)"), the landing memory card and the README.

## district_b (Kalinagar) failure

This was a seed and agent design bug, not an intended contrast. Evidence was hard-wired to fodder, so rice never reconstructed.

Fixed in `73bdf62`:
- Evidence is now keyed on the dominant in-window stage.
- Result: J = 1.0 PASS. Only the dairy paths are refused (no precedent). Shelters act in 2025. 5 path-level changes.
- Covered by `tests/test_kalinagar.py`.

## Issues

| # | Sev | Where | Issue | Fix | Verified |
|---|-----|-------|-------|-----|----------|
| 1 | major | landing, all vp | Horizontal scroll (1490 > 1440 px; 549 > 390 px on phones): the oversized grain layer and the 60-second `pre` forced grid min-content | `.stage{overflow:hidden}`, `overflow-x:clip` on html/body, `min-width:0` on grid cells | `scrollWidth == innerWidth` at all 6 vp |
| 2 | major | landing nav | axe *label-content-name-mismatch* (serious) on the brand link | Dropped the aria-label; visible text "Cascade Sentinel" is the name | axe 0 |
| 3 | major | landing ≤640 | Hero copy below the fold: the hero inherited the chapters' 150vh min-height, so the h1 was cut at 390x844 | `.hero.chapter{min-height:100svh}` on phones | landing-390x844-top |
| 4 | major | landing, all vp | Chapter copy scrolled under the nav while the scene played. Sticky never worked because `body{overflow-x:hidden}` makes body a scroll container | `overflow-x:clip`; desktop panels sticky at `max(96px, 50vh-240px)`; mobile bottom sheet now sticks | landing-*-ch1..ch4 |
| 5 | major | /404 (Pages) | The 404 used a meta-refresh to `./`; on nested paths that resolves to another missing URL (loop) | Real branded 404 with absolute links to `/cascade-sentinel/` and `/app/` | live `/cascade-sentinel/x/y` |
| 6 | major | meta | `og:image` was relative and WebP (broken social cards); no Twitter title/image | 1200x630 `og.png`; absolute URL rewritten at build; og:url, canonical, twitter:* added | page source on Pages |
| 7 | major | dashboard, all vp | Change count inconsistent (6 vs 14) | One metric, see above | diff modal "14 path-level changes" |
| 8 | major | dashboard | Out-of-order clicks (Run 2025 first, Close before Run) ended in "Run failed (409)" with a Retry that could never work | Stepper gating from the episode probes (only the valid next step is enabled and highlighted), next-step hint (aria-live), server `detail` shown on any error | initial `disabled 2024/close/2025 = false,true,true` |
| 9 | major | dashboard | Tenant switch or Reset mid-run: `state.tenant` changed but the reset was skipped (in-flight guard), so the UI showed tenant B with tenant A data | Tenant select disabled while busy; Reset/tenant guarded with a toast | "tenant select disabled mid-run = true" |
| 10 | major | dashboard | Double-click Close could write back twice | Close is disabled once the episode is closed (gating + in-flight guard) | harness dblclick: one write-back, Close disabled |
| 11 | major | dashboard | Explain focus trap leaked: hidden Copy buttons inside a closed `<details>` counted as "last", so Tab escaped and Esc stopped working | Trap on document, counts only rendered focusables, pulls focus back on focusin | extra.mjs: trapped after 25 Tabs, Esc closes, focus returns to Explain |
| 12 | major | dashboard | Sticky replay banner covered the Explain drawer header and Close button; the shell overflowed the viewport so the legend was clipped | Banner is an in-flow `<aside>`; body is a flex column; drawer/modal header sticky | "Close hittable" check, app-*-4-explain |
| 13 | major | dashboard | axe color-contrast (serious): tenant select 2.19:1, orchestrator avatar 3.58:1; light theme phase labels and act chip | Styled select; `#c2410c` avatar; light tokens `--act-text:#1b5e2b`, phase label `#a84300` | axe 0 serious, dark and light |
| 14 | major | dashboard ≤1100 | Debate and Graph panes both active: graph squeezed to ~0 px; header + stepper 430 px tall at 390 | Only Graph active by default; compact one-row header, 4-column stepper with short labels, `.col-center` flex fix | app-390x844-*, app-360x740-* |
| 15 | major | dashboard mobile | Graph mis-zoomed after it was rendered while its tab was hidden; minZoom 0.4 clipped the graph on phones | `refit()` on tab switch and resize; top-to-bottom dagre layout on narrow screens; minZoom 0.15 | app-390x844-7-graph2025 |
| 16 | major | dashboard | Approve spinner never cleared after success | Button becomes "Approved ✓" (disabled) | approve toast + card state |
| 17 | minor | landing scene | 3D labels clipped at screen edges ("dairy branch · no precedent", "heatwave · Tmax forecast") | Labels flip left near the right edge and clamp inside the viewport; hidden when the node is off screen | label-clip check 0 |
| 18 | minor | landing scene | Labels drawn under the copy panel or nav | Hidden while overlapping the active panel (rect read once per frame) | check 0 |
| 19 | minor | landing | Chapter rail dots overlapped right-hand panels (1024) and the finale cards | Extra right padding ≥961 px; rail hidden <1200 px | rail-overlap check 0 |
| 20 | minor | landing hero | Stat labels low contrast over the grid; third chip wrapped | Chips with dark backdrop and lighter text; 10 px gap | landing-*-top |
| 21 | minor | landing | Track cards and glass panels hard to read over bright orbs | Panel 0.78 and track 0.84 opacity | landing-1024x768-ch5 |
| 22 | minor | landing | "36 passing tests" was stale | 37 | pytest 37 passed |
| 23 | minor | landing ≤640 | Memory panel taller than the viewport; long ids overflowed the cards | Footnote and long caption hidden on phones; `overflow-wrap:anywhere` | panel-height check 0 |
| 24 | minor | landing | Brand double gap | Removed the extra margin | — |
| 25 | minor | dashboard | Console warning: cytoscape `text-decoration` is invalid | Dashed border style instead | 0 console warnings |
| 26 | minor | dashboard | axe moderate: no `<main>`/h1, duplicate banner (dialog `<header>`s), unlabeled asides, content outside landmarks | `<main>` (display:contents), visually hidden h1, dialog heads are divs, aside labels, banner is a labelled aside | axe 0 |
| 27 | minor | dashboard | Stepper flex buttons rendered "Run  Season  2024" with double gaps | Single span child | — |
| 28 | minor | dashboard diff | Redundant "weak_analog weak_analog", raw underscores, long paths overflowed on phones | Readable labels, wrapped path in mono with full path in the title, coloured verdicts | app-*-6-diff |
| 29 | minor | dashboard | Theme toggle had confusing `aria-pressed` semantics | Plain button named "Light theme" / "Dark theme" | — |
| 30 | minor | Pages | Local-only "FalkorDB Browser" link shown; canonical pointed at `origin/app` | Hidden in the static build; canonical points at the Pages URL | — |
| 31 | minor | dashboard | "ready" toast covered the legend and became the LCP element at 8 s; pill said "API ping 1" in the replay | Toast removed; pill says "Recorded replay" | Lighthouse LCP element |
| 32 | minor | dashboard | Copy-Cypher failed on non-secure origins | `execCommand` fallback; aria-label "Copy Cypher query" | "Copied" |
| 33 | minor | Pages banner | 3 lines on phones; the GitHub link came before "Skip to graph" | Short text on phones, placed after the skip link | tab order |
| 34 | minor | perf | Google Fonts CSS was render-blocking; scene built before first paint; mobile particles 900 + 500 at DPR 1.5 | Preload/print-swap fonts; scene lazy-inits after 2 rAF + idle (copy is never held more than 1.6 s); mobile 700 + 360 particles, DPR ≤1.25 | Lighthouse below |

## Edge-case flows (all pass)

- Run 2025 before 2024: the button is disabled and the hint says "Start with ① Run Season 2024".
- Double-click Close: a single write-back; Close then disabled.
- Reset mid-run: refused with "Wait for the current step to finish".
- Tenant switch mid-run: select disabled. After the run, switching asks for confirmation and resets.
- Esc closes Explain, What-changed and the Reset confirm. Focus returns to the trigger.
- Enter/Space activate every stepper button and card button.
- Layer toggles, Fit/+/−, Memory tabs, Copy MCP, Copy Cypher, Approve, Explain and Reset all work.
- Reload mid-flow restores the stage from the episode probes.

## Lighthouse (headless, SwiftShader; WebGL is CPU-emulated, so landing TBT is pessimistic)

Accessibility, Best practices and SEO score 100 on both pages. Performance numbers are in the final report section below.
