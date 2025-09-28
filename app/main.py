# app/main.py
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
    # google-genai (new SDK) OR google.generativeai (older)
    try:
        import google.genai as genai  # type: ignore
        _GEMINI_SDK = "google-genai"
        _GEMINI_AVAILABLE = True
    except Exception:  # pragma: no cover
        import google.generativeai as genai  # type: ignore
        _GEMINI_SDK = "google-generativeai"
        _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_SDK = "unavailable"

# --- App setup ---
app = FastAPI(title="Cerberus Runner", version="1.0.0")

# CORS (relaxed by default; adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your domains if you prefer
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Access log middleware (simple) ---
from starlette.middleware.base import BaseHTTPMiddleware

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        dur_ms = (time.time() - start) * 1000.0
        has_key = "present" if request.headers.get("x-api-key") else "missing"
        print(f"{request.method} {request.url.path} -> {response.status_code} in {dur_ms:.1f}ms headers:X-API-Key={has_key}")
        return response

app.add_middleware(AccessLogMiddleware)

# --- Config helpers ---
CERB_KEY = os.getenv("CERBERUS_API_KEY", "")
REQUIRE_TS = os.getenv("REQUIRE_TIMESTAMP", "false").lower() in ("1", "true", "yes", "on")
TS_SKEW_SEC = int(os.getenv("TIMESTAMP_SKEW_SECONDS", "300"))  # +/- 5 minutes

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if _GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        # new SDK
        if _GEMINI_SDK == "google-genai":
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[warn] Failed to configure Gemini SDK ({_GEMINI_SDK}): {e}")

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

# --- Auth / freshness guards ---
def check_api_key(x_api_key: Optional[str]) -> None:
    if not CERB_KEY:
        # If no server key configured, EVERYTHING would 403; make it explicit:
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
        raise HTTPException(status_code=401, detail="Invalid X-Timestamp; must be unix seconds")
    now = int(time.time())
    if abs(now - ts_client) > TS_SKEW_SEC:
        raise HTTPException(status_code=401, detail="Stale X-Timestamp")

# --- Helpers ---
def make_zip_from_payload(payload: Dict[str, Any], filename: str = "artifact.zip") -> Artifact:
    """
    Creates an in-memory ZIP that contains:
      - payload.json (the JSON you passed in)
      - README.txt   (simple note)
    Returns base64 + sha256/size metadata.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # payload.json
        import json
        zf.writestr("payload.json", json.dumps(payload, indent=2, ensure_ascii=False))
        # readme
        zf.writestr(
            "README.txt",
            "Cerberus Runner\n\nThis ZIP was generated in-memory and returned via the API.\n"
        )
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    return Artifact(
        filename=filename,
        size_bytes=len(raw),
        sha256=sha,
        base64=b64,
    )

# --- Routes ---
@app.get("/health")
def health():
    return {
        "status": "ok",
        "ts": int(time.time()),
        "require_timestamp": REQUIRE_TS,
        "has_api_key": bool(CERB_KEY),
        "gemini": {
            "configured": bool(GEMINI_API_KEY),
            "sdk": _GEMINI_SDK,
        },
    }

@app.post("/run", response_model=RunJobResponse)
def run_job(
    req: RunJobRequest,
    x_api_key: Optional[str] = Header(None, convert_underscores=False),
    x_timestamp: Optional[str] = Header(None, convert_underscores=False),
):
    check_api_key(x_api_key)
    check_timestamp(x_timestamp)

    # Do your real work here. For now, pack the payload into a ZIP.
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
        # Try a trivial prompt
        if _GEMINI_SDK == "google-generativeai":
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content("Say 'pong'.")
            text = getattr(resp, "text", None) or (resp.candidates[0].content.parts[0].text if resp.candidates else "")
            return {"ok": True, "model": "gemini-2.0-flash", "text": text}
        else:
            # google-genai style (adjust if your SDK differs)
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_content(model="gemini-2.0-flash", contents="Say 'pong'.")
            # Response shape may differ by SDK version; attempt generic extraction:
            text = None
            try:
                text = resp.output_text  # new SDK convenience
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

# --- Debug endpoint to inspect what GPT/clients send (no auth) ---
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

# --- Dev entrypoint (Fly will use the Docker CMD) ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
