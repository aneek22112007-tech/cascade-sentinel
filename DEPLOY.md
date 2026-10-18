# Deploying Cascade Sentinel

## GitHub Pages (live site, static)

https://aneek22112007-tech.github.io/cascade-sentinel/ is served from the `gh-pages` branch:

- `/` is the 3D landing page.
- `/app/` is the real dashboard plus `static/js/replay.js`, which answers its API calls from JSON.
- `/data/*.json` holds runs recorded from a real FalkorDB by `python -m sentinel.export_static`. It drives reset → run 2024 → close_episode → run 2025 for both tenants and records graph_snapshot, recommendations, explain (with Cypher) for every recommendation, and every memory layer.

To refresh it:

```bash
python -m sentinel.build_pages --out site          # needs a reachable FalkorDB (or run sentinel.serve first)
git worktree add /tmp/ghp gh-pages && cp -a site/. /tmp/ghp/ && cd /tmp/ghp && git add -A && git commit -m "pages: refresh" && git push
```

`deploy/github-pages-workflow.yml` does the same in CI with a FalkorDB service container. Copy it into `.github/workflows/` to use it; that needs a token with the `workflow` scope.

## Full live app (container)

The Docker image is **self-contained**: FastAPI, the UI, and FalkorDB all run in one container.
`python -m sentinel.serve` (the image `CMD`) does this:

1. **Picks a database.**
   - `FALKORDB_URL` is set (for example `redis://default:pw@host:6379`, or `rediss://` for TLS): it uses that external FalkorDB.
   - Otherwise, it starts the `redis-server` and FalkorDB module bundled in the `falkordblite` wheel on `127.0.0.1:6379` inside the container.
2. **Auto-seeds** both tenants (`demo` = Rajpur and `district_b` = Kalinagar) when their graphs are empty. To change this, set `SEED_ON_START=always` (reseed on every boot) or `never`.
3. **Serves** on `$PORT` (default `8000`): the landing page at `/`, the dashboard at `/app`, the REST API at `/api/...`, and health checks at `/healthz` (liveness + DB ping) and `/health`.

There's no separate DB service and no persistent disk. A free-tier restart simply reseeds, so the demo starts from a clean Season 2024 every time.

| Env var | Default | Meaning |
|---|---|---|
| `PORT` | `8000` | HTTP port (Render, Railway, and Fly inject it; on HF Spaces set it to `7860`) |
| `FALKORDB_URL` | unset | External FalkorDB. If unset, the embedded one is used |
| `SEED_ON_START` | `if-empty` | `if-empty` \| `always` \| `never` |
| `SENTINEL_ADMIN_TOKEN` | unset | If set, POST routes (reset/run/close/approve) need the `X-Sentinel-Token` header |
| `LLM_PROVIDER` | `none` | Rationale text only. Decisions never read it |

## Render (one click, free)

`render.yaml` is in the repo root.

1. Go to https://dashboard.render.com, then **New +** > **Blueprint**, and connect `aneek22112007-tech/cascade-sentinel`.
2. Click **Apply**. Render builds the Dockerfile, injects `PORT`, and health-checks `/healthz`.
3. The URL is `https://cascade-sentinel.onrender.com` (live now; `/healthz` → `{"ok":true,"db":true}`). The first build takes about 3–5 min. Free instances sleep after 15 min idle, and the first request after that takes about 30–60 s to wake.

You can also skip the Blueprint and create a manual **New > Web Service** with Runtime Docker, Instance Free, and Health Check Path `/healthz`.

## Railway

1. Go to https://railway.com/new, then **Deploy from GitHub repo** > `cascade-sentinel`. Railway detects the `Dockerfile` automatically.
2. Open **Settings > Networking > Generate Domain**. Railway injects `PORT`, and the app listens on it.
3. (Optional) Under **Variables**, add `SEED_ON_START=if-empty`, plus `FALKORDB_URL` if you'd rather use a Railway FalkorDB service.

## Hugging Face Spaces (Docker)

1. Go to https://huggingface.co/new-space and choose SDK **Docker** > **Blank**.
2. Push this repo to the Space (`git remote add space https://huggingface.co/spaces/<user>/cascade-sentinel && git push space main`), and put this header at the very top of the Space's `README.md`:
   ```yaml
   ---
   title: Cascade Sentinel
   emoji: 🌡️
   colorFrom: red
   colorTo: indigo
   sdk: docker
   app_port: 7860
   ---
   ```
3. In **Settings > Variables**, add `PORT=7860`. The image already runs as uid 1000, which Spaces requires.

## Fly.io

```bash
fly launch --no-deploy --copy-config=false   # accept the Dockerfile; internal port 8000
fly deploy
```

## External FalkorDB (optional)

Create a free instance at https://app.falkordb.cloud and set
`FALKORDB_URL=redis://default:<password>@<host>:<port>` on the host. On first boot the app seeds the `sentinel_demo` and `sentinel_district_b` graphs.

## Local checks

```bash
docker build -t cascade-sentinel . && docker run --rm -p 8000:8000 cascade-sentinel
# No Docker: Python 3.12+
pip install -e ".[embedded]" && python -m sentinel.serve
curl localhost:8000/healthz      # {"ok":true,"db":true}
curl -XPOST "localhost:8000/api/demo/run/2024?sse=false" | head -c 300
```
