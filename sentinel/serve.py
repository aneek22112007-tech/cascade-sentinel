"""Production entrypoint: one process that is deployable on any free Docker host.

    python -m sentinel.serve

Database selection (decided *before* sentinel.config is imported):

* ``FALKORDB_URL`` (or ``FALKORDB_HOST``) set  -> use that external FalkorDB.
* ``FALKORDB_LITE`` set                          -> FalkorDBLite embedded file (in-process client).
* nothing set                                    -> start the redis-server + FalkorDB module that
  ship inside the ``falkordblite`` wheel as a child process on 127.0.0.1, so the whole
  app (graph + API + UI) runs in a single container with no separate database service.

Then: auto-seed every tenant whose graph is empty (``SEED_ON_START=always`` forces a
clean reseed, ``never`` skips), and serve FastAPI on ``$PORT`` (default 8000).
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import tempfile
import time

_child: subprocess.Popen | None = None


def _log(msg: str) -> None:
    print(f"[serve] {msg}", flush=True)


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def _embedded_binaries() -> tuple[str, str]:
    try:
        import redislite  # shipped by the falkordblite wheel
    except ImportError as exc:  # pragma: no cover - depends on install
        raise SystemExit(
            "No FALKORDB_URL/FALKORDB_HOST set and falkordblite is not installed.\n"
            "Either `pip install falkordblite` (Python 3.12+, glibc 2.39+) for embedded mode,\n"
            "or point FALKORDB_URL at a FalkorDB instance (redis://host:6379)."
        ) from exc
    base = os.path.dirname(redislite.__file__)
    server = os.path.join(base, "bin", "redis-server")
    module = getattr(redislite, "__falkordb_module__", "") or os.path.join(base, "bin", "falkordb.so")
    if not (os.path.exists(server) and os.path.exists(module)):
        raise SystemExit(f"embedded FalkorDB binaries missing: {server} / {module}")
    return server, module


def start_embedded() -> int:
    """Spawn redis-server --loadmodule falkordb.so on localhost; return its port."""
    global _child
    port = int(os.getenv("EMBEDDED_FALKORDB_PORT", "6379"))
    if _port_open("127.0.0.1", port):
        _log(f"something already listens on 127.0.0.1:{port}; reusing it")
        return port
    server, module = _embedded_binaries()
    data_dir = os.getenv("EMBEDDED_FALKORDB_DIR") or tempfile.mkdtemp(prefix="falkordb-")
    os.makedirs(data_dir, exist_ok=True)
    cmd = [
        server,
        "--port", str(port),
        "--bind", "127.0.0.1",
        "--protected-mode", "no",
        "--dir", data_dir,
        "--save", "",
        "--appendonly", "no",
        "--loadmodule", module,
        # small free instances (512 MB, shared CPU): cap the graph worker pool
        *os.getenv("EMBEDDED_FALKORDB_MODULE_ARGS", "THREAD_COUNT 2 OMP_THREAD_COUNT 2").split(),
    ]
    _log(f"starting embedded FalkorDB on 127.0.0.1:{port} (data {data_dir})")
    _child = subprocess.Popen(cmd, stdout=subprocess.DEVNULL if os.getenv("EMBEDDED_QUIET", "1") == "1" else None)
    atexit.register(stop_embedded)
    deadline = time.time() + 30
    while time.time() < deadline:
        if _child.poll() is not None:
            raise SystemExit(f"embedded redis-server exited with code {_child.returncode}")
        if _port_open("127.0.0.1", port):
            return port
        time.sleep(0.2)
    raise SystemExit("embedded FalkorDB did not start within 30s")


def stop_embedded() -> None:
    global _child
    if _child and _child.poll() is None:
        _child.terminate()
        try:
            _child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _child.kill()
    _child = None


def choose_backend() -> str:
    try:  # respect a local .env exactly like sentinel.config does
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover
        pass
    if os.getenv("FALKORDB_URL"):
        return "external-url"
    if os.getenv("FALKORDB_HOST"):
        return "external-host"
    if os.getenv("FALKORDB_LITE"):
        return "lite-file"
    port = start_embedded()
    os.environ["FALKORDB_HOST"] = "127.0.0.1"
    os.environ["FALKORDB_PORT"] = str(port)
    return "embedded"


def wait_for_db(timeout: float = 60.0) -> None:
    from sentinel.db import ping, reset_client

    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            if ping() == 1:
                return
        except Exception as exc:  # noqa: BLE001 - surface the last error below
            last = exc
            reset_client()
        time.sleep(1)
    raise SystemExit(f"FalkorDB not reachable: {last}")


def auto_seed() -> None:
    from sentinel import config
    from sentinel.db import delete_graph, query
    from sentinel.seed.loader import load_tenant

    mode = os.getenv("SEED_ON_START", "if-empty").lower()
    if mode == "never":
        _log("SEED_ON_START=never; skipping seed")
        return
    for tenant in config.TENANTS:
        n = 0
        if mode != "always":
            try:
                n = int(query(tenant, "MATCH (n) RETURN count(n)").rows[0][0])
            except Exception:  # empty / missing graph
                n = 0
        if n:
            _log(f"tenant {tenant}: {n} nodes already present; keeping state")
            continue
        _log(f"tenant {tenant}: seeding")
        delete_graph(tenant)
        load_tenant(tenant)


def main() -> None:
    backend = choose_backend()
    _log(f"database backend: {backend}")
    wait_for_db()
    auto_seed()

    import uvicorn

    port = int(os.getenv("PORT") or os.getenv("API_PORT") or "8000")
    host = os.getenv("HOST", "0.0.0.0")
    _log(f"serving on http://{host}:{port}  (landing /, dashboard /app, health /healthz)")
    # uvicorn handles SIGTERM gracefully; atexit then stops the embedded DB child.
    uvicorn.run("sentinel.api.main:app", host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info"),
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
