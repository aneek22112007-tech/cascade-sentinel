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

BANNER = (
    '<div class="replay-banner" role="status" style="position:sticky;top:0;z-index:1000;'
    "background:#3b2f14;color:#ffe8a3;border-bottom:1px solid #7a651f;font:500 13px/1.4 system-ui,sans-serif;"
    'padding:8px 16px;text-align:center">Static replay of recorded FalkorDB runs. Run locally for the live graph: '
    '<code>pip install -e ".[embedded]" &amp;&amp; python -m sentinel.serve</code> · '
    '<a style="color:#ffd8a8" href="https://github.com/aneek22112007-tech/cascade-sentinel">GitHub</a></div>'
)


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
    (out / "index.html").write_text(landing)

    app = (static / "app.html").read_text()
    app = app.replace('"/static/', '"../static/').replace('href="/"', 'href="../"')
    app = re.sub(r"(<body[^>]*>)", r"\1\n  " + BANNER, app, count=1)
    shim = ('<script>window.SENTINEL_STATIC="../static";window.SENTINEL_DATA="../data";</script>\n'
            '  <script src="../static/js/replay.js"></script>\n  ')
    app = app.replace('<script type="module"', shim + '<script type="module"', 1)
    (out / "app").mkdir(exist_ok=True)
    (out / "app" / "index.html").write_text(app)
    (out / ".nojekyll").write_text("")
    (out / "404.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=./">'
                                  '<title>Cascade Sentinel</title><a href="./">Cascade Sentinel</a>')

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
