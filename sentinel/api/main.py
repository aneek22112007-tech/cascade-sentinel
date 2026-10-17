"""FastAPI entrypoint. Routes land in Phase 5; health is enough for the container to boot."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from sentinel import config
from sentinel.db import ping

app = FastAPI(title="Cascade Sentinel", version="0.1.0")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"ok": True, "ping": ping(), "tenant_default": config.DEFAULT_TENANT})
