from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os, time, base64, io, zipfile, json, hashlib, datetime

app = FastAPI(title="Cerberus Stateless Runner", version="0.4.0")

API_KEY = os.getenv("CERBERUS_API_KEY", "")
REQUIRE_TIMESTAMP = os.getenv("REQUIRE_TIMESTAMP", "true").lower() == "true"
# --- add near the top ---
from fastapi import Request

# --- add anywhere in the FastAPI route section ---
@app.post("/debug/echo")
async def debug_echo(request: Request):
    body = await request.body()
    # Return a trimmed view so we don't log huge payloads
    return {
        "received_headers": {k: v for k, v in request.headers.items() if k.lower().startswith("x-") or k.lower() in ["content-type", "accept"]},
        "method": request.method,
        "url": str(request.url),
        "body_preview": body[:500].decode("utf-8", errors="ignore"),
    }

def _require_auth_and_fresh(req: Request):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: CERBERUS_API_KEY not set")
    key = req.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if REQUIRE_TIMESTAMP:
        ts = req.headers.get("X-Timestamp")
        try:
            ts = int(ts)
        except Exception:
            raise HTTPException(status_code=400, detail="Missing or invalid X-Timestamp")
        now = int(time.time())
        if abs(now - ts) > 60:
            raise HTTPException(status_code=401, detail="Stale request")

def _zip_in_memory(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()

@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time())}

@app.post("/run")
async def run_job(request: Request):
    _require_auth_and_fresh(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    payload = body.get("payload", {})
    stage = body.get("stage", "synthesis")

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_id = body.get("run_id") or ts

    files = {
        f"README.txt": f"Cerberus run {run_id} ({stage})\nGenerated in-memory; not stored.\n".encode(),
        f"results/output.json": (json.dumps({"run_id": run_id, "stage": stage, "payload": payload}, indent=2)).encode(),
        f"logs/summary.txt": f"Run {run_id}\nUTC: {ts}\nFiles: 2\n".encode(),
    }

    zip_bytes = _zip_in_memory(files)
    digest = hashlib.sha256(zip_bytes).hexdigest()
    b64 = base64.b64encode(zip_bytes).decode()

    filename = f"cerberus_{run_id}_{stage}.zip"
    return JSONResponse(
        {
            "run_id": run_id,
            "artifact": {
                "filename": filename,
                "mime": "application/zip",
                "size_bytes": len(zip_bytes),
                "sha256": digest,
                "base64": b64,
            },
            "logs": [],
        }
    )

# --- Gemini Support ---
# Requires: GEMINI_API_KEY in environment (set via Fly secrets)
try:
    from google import genai
    from google.genai import types as genai_types
    _HAS_GENAI = True
except Exception:
    _HAS_GENAI = False

def _gemini_client():
    if not _HAS_GENAI:
        raise HTTPException(status_code=501, detail="google-genai not available")
    # Client reads GEMINI_API_KEY from env automatically
    try:
        client = genai.Client()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini client init failed: {e}")
    return client

@app.get("/llm/gemini-test")
def gemini_test(request: Request):
    _require_auth_and_fresh(request)
    if not _HAS_GENAI:
        raise HTTPException(status_code=501, detail="Gemini SDK not installed")
    # Soft check for key
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not set")
    client = _gemini_client()
    try:
        resp = client.models.generate_content(model="gemini-2.5-flash", contents="ping")
        txt = getattr(resp, "text", None) or "ok"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini call failed: {e}")
    return {"ok": True, "model": "gemini-2.5-flash", "text": txt[:200]}

@app.post("/run/gemini")
async def run_gemini(request: Request):
    _require_auth_and_fresh(request)
    if not _HAS_GENAI:
        raise HTTPException(status_code=501, detail="Gemini SDK not installed")
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not set")
    try:
        body = await request.json()
    except Exception:
        body = {}
    prompt = body.get("prompt", "Summarize Cerberus in one paragraph.")
    model = body.get("model", "gemini-2.5-flash")

    client = _gemini_client()
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        text = getattr(resp, "text", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini call failed: {e}")

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_id = body.get("run_id") or ts

    files = {
        "README.txt": f"Cerberus (Gemini-assisted) run {run_id}\nModel: {model}\n".encode(),
        "results/gemini_prompt.txt": prompt.encode(),
        "results/gemini_response.txt": text.encode(),
    }
    zip_bytes = _zip_in_memory(files)
    digest = hashlib.sha256(zip_bytes).hexdigest()
    b64 = base64.b64encode(zip_bytes).decode()
    filename = f"cerberus_{run_id}_gemini.zip"
    return JSONResponse(
        {
            "run_id": run_id,
            "artifact": {
                "filename": filename,
                "mime": "application/zip",
                "size_bytes": len(zip_bytes),
                "sha256": digest,
                "base64": b64,
            },
            "logs": [],
        }
    )
