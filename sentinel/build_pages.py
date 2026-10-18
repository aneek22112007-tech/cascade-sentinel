"""Build the static GitHub Pages site into ./site.

    python -m sentinel.build_pages [--out site] [--skip-export]

/            3D landing (static/landing.html, relative asset paths)
/app/        the real dashboard + static/js/replay.js (answers the API from recorded JSON)
/data/*.json real FalkorDB runs recorded by sentinel.export_static
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from sentinel import config

PAGES_URL = "https://aneek22112007-tech.github.io/cascade-sentinel/"
LIVE_URL = "https://cascade-sentinel.onrender.com/"

BANNER = (
    '<style>.badge-replay{background:#3b2f14;color:#ffe8a3;border:1px solid #7a651f;cursor:help;white-space:nowrap}'
    ".btn-live{white-space:nowrap;border-color:var(--heat-3)}.btn-live .s{display:none}"
    "@media (max-width:640px){.badge-replay{display:none}.btn-live .l{display:none}.btn-live .s{display:inline}"
    ".app-top .btn-live{min-height:36px;padding:4px 10px;font-size:12px}}</style>"
    '<span class="badge badge-replay" tabindex="0" title="Static replay of FalkorDB runs recorded by '
    'sentinel.export_static. Same dashboard, no database: open the live version for the real graph.">'
    "Recorded replay</span>"
    '<a class="btn btn-live" href="LIVE_APP" title="Real FalkorDB on a free Render instance; '
    'the first load can take 30-60 s to wake"><span class="l">Open live version ↗</span><span class="s">Live ↗</span></a>'
)

NOT_FOUND = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found · Cascade Sentinel</title><meta name="robots" content="noindex">
<link rel="icon" href="/cascade-sentinel/static/logo.svg" type="image/svg+xml">
<style>html{background:#05070b;color:#eef2f7;font:16px/1.5 system-ui,sans-serif}
body{min-height:100vh;margin:0;display:grid;place-items:center;text-align:center;padding:24px}
h1{font-size:28px;margin:12px 0 8px}p{color:#aab4c0;margin:0 0 20px}
a{display:inline-flex;align-items:center;min-height:44px;padding:0 18px;border-radius:999px;margin:4px;
text-decoration:none;font-weight:600}.hot{background:#ff7a1a;color:#120800}.ghost{border:1px solid #39424e;color:#eef2f7}
a:focus-visible{outline:2px solid #ffd43b;outline-offset:3px}</style></head>
<body><main><svg viewBox="0 0 64 64" width="48" height="48" aria-hidden="true"><path d="M12 40 L32 12 L52 40" fill="none"
stroke="#ff7a1a" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="32" cy="47" r="6"
fill="#ffd43b"/></svg><h1>No precedent for this page.</h1><p>Sentinel refuses to guess. Try one of these:</p>
<a class="hot" href="/cascade-sentinel/">Home</a><a class="ghost" href="/cascade-sentinel/app/">Live demo (replay)</a>
<a class="ghost" href="https://github.com/aneek22112007-tech/cascade-sentinel">GitHub</a></main></body></html>
"""


def build(out: Path, skip_export: bool = False) -> None:
    static = config.ROOT / "static"
    if out.exists():
        keep_data = out / "data" if skip_export else None
        tmp = None
        if keep_data and keep_data.exists():
            tmp = out.parent / ".data_keep"
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(keep_data, tmp)
        shutil.rmtree(out)
        if tmp:
            out.mkdir(parents=True)
            shutil.move(str(tmp), out / "data")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static, out / "static", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.map", "landing.html", "app.html", "index.html"))

    landing = (static / "landing.html").read_text()
    landing = landing.replace('href="health"', 'href="data/meta.json"')
    # Pages: "Launch live demo" goes to the real FalkorDB app on Render; the replay stays one click away
    landing = landing.replace('href="app"', f'href="{LIVE_URL}app"')
    landing = landing.replace(" data-pages-note hidden", " data-pages-note")
    # social cards need absolute URLs
    landing = landing.replace('content="static/img/og.png"', f'content="{PAGES_URL}static/img/og.png"')
    landing = landing.replace('<link rel="canonical" href="./" />', f'<link rel="canonical" href="{PAGES_URL}" />')
    landing = landing.replace('<meta property="og:url" content="./" />', f'<meta property="og:url" content="{PAGES_URL}" />')
    (out / "index.html").write_text(landing)

    app = (static / "app.html").read_text()
    app = app.replace('"/static/', '"../static/').replace('href="/"', 'href="../"')
    badge = BANNER.replace("LIVE_APP", f"{LIVE_URL}app")
    app = app.replace('<span class="badge badge-synthetic">Synthetic data</span>',
                      '<span class="badge badge-synthetic">Synthetic data</span>\n      ' + badge, 1)
    app = app.replace('<span id="healthPill" class="health-pill bad">', '<span id="healthPill" class="health-pill bad" hidden>')
    # no local FalkorDB Browser on Pages; canonical points at the Pages URL
    app = app.replace('id="browserLink"', 'id="browserLink" hidden')
    app = re.sub(r'l\.href = location\.origin \+ "/app";', f'l.href = "{PAGES_URL}app/";', app)
    shim = ('<script>window.SENTINEL_STATIC="../static";window.SENTINEL_DATA="../data";</script>\n'
            '  <script src="../static/js/replay.js"></script>\n  ')
    app = app.replace('<script type="module"', shim + '<script type="module"', 1)
    (out / "app").mkdir(exist_ok=True)
    (out / "app" / "index.html").write_text(app)
    (out / ".nojekyll").write_text("")
    (out / "404.html").write_text(NOT_FOUND)

    if not skip_export:
        from sentinel.export_static import main as export_main

        export_main(["--out", str(out / "data")])
    print(f"[pages] built {out}/ (landing /, replay /app/, data /data/)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--skip-export", action="store_true")
    a = ap.parse_args(argv)
    build(Path(a.out), a.skip_export)


if __name__ == "__main__":
    main()
