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

# --- Optional Gemini support (guarded import) ---
_GEMINI_AVAILABLE = False
try:
    try:
        import google.genai as genai  # new SDK
        _GEMINI_SDK = "google-genai"
        _GEMINI_AVAILABLE = True
    except Exception:
        import google.generativeai as genai  # older SDK
        _GEMINI_SDK = "google-generativeai"
        _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_SDK = "unavailable"

app = FastAPI(title="Cerberus Runner", version="1.0.0")

# CORS (relaxed by default; tighten as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Access log middleware ---
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

# --- Config ---
CERB_KEY = os.getenv("CERBERUS_API_KEY", "").strip()
REQUIRE_TS = os.getenv("REQUIRE_TIMESTAMP", "false").lower() in ("1", "true", "yes", "on")
TS_SKEW_SEC = int(os.getenv("TIMESTAMP_SKEW_SECONDS", "300"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if _GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[warn] Gemini SDK configure failed: {e}")

# --- Models ---
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

class RunGeminiRequest(BaseModel):
    run_id: Optional[str] = None
    prompt: str = "Summarize Cerberus in one paragraph."
    model: str = "gemini-2.5-flash"

# --- Guards ---
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

# --- ZIP helper ---
def make_zip_from_payload(payload: Dict[str, Any], filename: str = "artifact.zip") -> Artifact:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        import json
        zf.writestr("payload.json", json.dumps(payload, indent=2, ensure_ascii=False))
        zf.writestr("README.txt", "Cerberus Runner\\n\\nThis ZIP was generated in-memory.\\n")
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    return Artifact(filename=filename, size_bytes=len(raw), sha256=sha, base64=b64)

# --- Routes ---
@app.get("/health")
def health():
    return {
        "status": "ok",
        "ts": int(time.time()),
        "require_timestamp": REQUIRE_TS,
        "has_api_key": bool(CERB_KEY),
        "gemini": {"configured": bool(GEMINI_API_KEY), "sdk": _GEMINI_SDK},
    }

@app.post("/run", response_model=RunJobResponse)
def run_job(
    req: RunJobRequest,
    x_api_key: Optional[str] = Header(None, convert_underscores=False),
    x_timestamp: Optional[str] = Header(None, convert_underscores=False),
):
    check_api_key(x_api_key)
    check_timestamp(x_timestamp)
    artifact = make_zip_from_payload(req.payload, filename="cerberus_artifact.zip")
    return RunJobResponse(run_id=req.run_id, artifact=artifact, logs=[])

@app.get("/llm/gemini-test")
def gemini_test(
    x_api_key: Optional[str] = Header(None, convert_underscores=False),
    x_timestamp: Optional[str] = Header(None, convert_underscores=False),
):
    check_api_key(x_api_key)
    check_timestamp(x_timestamp)
    if not (GEMINI_API_KEY and _GEMINI_AVAILABLE):
        return {"ok": False, "model": None, "text": "Gemini not configured"}
    try:
        if _GEMINI_SDK == "google-generativeai":
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content("Say 'pong'.")
            text = getattr(resp, "text", None) or (resp.candidates[0].content.parts[0].text if resp.candidates else "")
            return {"ok": True, "model": "gemini-2.0-flash", "text": text}
        else:
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_content(model="gemini-2.0-flash", contents="Say 'pong'.")
            try:
                text = resp.output_text
            except Exception:
                text = str(resp)
            return {"ok": True, "model": "gemini-2.0-flash", "text": text}
    except Exception as e:
        return {"ok": False, "model": None, "text": f"Gemini error: {e}"}

@app.post("/run/gemini", response_model=RunJobResponse)
def run_gemini(
    req: RunGeminiRequest,
    x_api_key: Optional[str] = Header(None, convert_underscores=False),
    x_timestamp: Optional[str] = Header(None, convert_underscores=False),
):
    check_api_key(x_api_key)
    check_timestamp(x_timestamp)
    text = "Gemini not configured."
    if GEMINI_API_KEY and _GEMINI_AVAILABLE:
        try:
            if _GEMINI_SDK == "google-generativeai":
                model = genai.GenerativeModel(req.model)
                resp = model.generate_content(req.prompt)
                text = getattr(resp, "text", None) or (resp.candidates[0].content.parts[0].text if resp.candidates else "")
            else:
                client = genai.Client(api_key=GEMINI_API_KEY)
                resp = client.models.generate_content(model=req.model, contents=req.prompt)
                try:
                    text = resp.output_text
                except Exception:
                    text = str(resp)
        except Exception as e:
            text = f"[Gemini error] {e}"
    payload = {"prompt": req.prompt, "model": req.model, "text": text}
    artifact = make_zip_from_payload(payload, filename="gemini_artifact.zip")
    return RunJobResponse(run_id=req.run_id, artifact=artifact, logs=[])

# Debug echo (no auth) — remove later if you want
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
