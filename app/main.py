from __future__ import annotations

import base64
import hashlib
import io
import os
import time
import zipfile
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Cerberus Runner", version="1.0.2")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Access log
from starlette.middleware.base import BaseHTTPMiddleware

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        resp = await call_next(request)
        dur = (time.time() - start) * 1000
        has_key = "present" if request.headers.get("x-api-key") else "missing"
        print(f"{request.method} {request.url.path} -> {resp.status_code} in {dur:.1f}ms headers:X-API-Key={has_key}")
        return resp

app.add_middleware(AccessLogMiddleware)

# Config
CERB_KEY = os.getenv("CERBERUS_API_KEY", "").strip()
REQUIRE_TS = os.getenv("REQUIRE_TIMESTAMP", "false").lower() in ("1", "true", "yes", "on")
TS_SKEW_SEC = int(os.getenv("TIMESTAMP_SKEW_SECONDS", "300"))

# Models
class RunJobRequest(BaseModel):
    run_id: Optional[str] = None
    stage: str = Field(default="synthesis")
    payload: Dict[str, Any] = Field(default_factory=dict)

class Artifact(BaseModel):
    filename: str
    mime: str = "application/zip"
    size_bytes: int
    sha256: str
    base64: str

class RunJobResponse(BaseModel):
    run_id: Optional[str] = None
    artifact: Artifact
    logs: list[str] = Field(default_factory=list)

# Guards
def check_api_key(x_api_key: Optional[str]) -> None:
    if not CERB_KEY:
        raise HTTPException(status_code=500, detail="Server missing CERBERUS_API_KEY")
    if not x_api_key or x_api_key.strip() != CERB_KEY:
        raise HTTPException(status_code=403, detail="Forbidden (bad or missing API key)")

def check_timestamp(x_timestamp: Optional[str]) -> None:
    if not REQUIRE_TS:
        return
    if not x_timestamp:
        raise HTTPException(status_code=401, detail="Missing X-Timestamp")
    try:
        ts_client = int(x_timestamp)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid X-Timestamp")
    now = int(time.time())
    if abs(now - ts_client) > TS_SKEW_SEC:
        raise HTTPException(status_code=401, detail="Stale X-Timestamp")

# Helpers
def make_zip_from_payload(payload: Dict[str, Any], filename: str = "artifact.zip") -> Artifact:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        import json
        zf.writestr("payload.json", json.dumps(payload, indent=2, ensure_ascii=False))
        zf.writestr("README.txt", "Cerberus Runner\n\nThis ZIP was generated in-memory.\n")
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    return Artifact(filename=filename, size_bytes=len(raw), sha256=sha, base64=b64)

# Routes
@app.get("/health")
def health():
    return {
        "status": "ok",
        "ts": int(time.time()),
        "require_timestamp": REQUIRE_TS,
        "has_api_key": bool(CERB_KEY),
    }

@app.post("/run", response_model=RunJobResponse)
def run_job(
    req: RunJobRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
):
    check_api_key(x_api_key)
    check_timestamp(x_timestamp)
    artifact = make_zip_from_payload(req.payload, filename="cerberus_artifact.zip")
    return RunJobResponse(run_id=req.run_id, artifact=artifact, logs=[])

# Open echo — good for quick manual tests
@app.post("/debug/echo")
async def debug_echo(request: Request):
    body = await request.body()
    return {
        "received_headers": {
            k: v for k, v in request.headers.items()
            if k.lower().startswith("x-") or k.lower() in ("content-type", "accept")
        },
        "method": request.method,
        "url": str(request.url),
        "body_preview": body[:500].decode("utf-8", errors="ignore"),
    }

# Secured echo — forces Actions to send the API key for troubleshooting
@app.post("/debug/echo-secure")
async def debug_echo_secure(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    check_api_key(x_api_key)
    body = await request.body()
    return {
        "received_headers": {
            k: v for k, v in request.headers.items()
            if k.lower().startswith("x-") or k.lower() in ("content-type", "accept")
        },
        "ok": True,
        "body_preview": body[:500].decode("utf-8", errors="ignore"),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
