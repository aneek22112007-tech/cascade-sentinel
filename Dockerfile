# Cascade Sentinel: graph + API + UI in ONE container.
# Debian trixie (glibc 2.41) so the falkordblite wheel (manylinux_2_39) installs: it ships
# redis-server + the FalkorDB module, which sentinel.serve starts on 127.0.0.1 when no
# FALKORDB_URL is given. Set FALKORDB_URL=redis://host:6379 to use an external FalkorDB.
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_PROVIDER=none \
    PORT=8000 \
    SEED_ON_START=if-empty

RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sentinel ./sentinel
COPY static ./static
COPY tests ./tests

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[embedded]"

# HF Spaces runs as uid 1000; keep everything it touches writable.
RUN useradd -m -u 1000 sentinel && chown -R sentinel /app
USER sentinel
ENV SENTINEL_STATIC_DIR=/app/static \
    EMBEDDED_FALKORDB_DIR=/tmp/falkordb

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

CMD ["python", "-m", "sentinel.serve"]
