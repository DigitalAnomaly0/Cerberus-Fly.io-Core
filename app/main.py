from fastapi import FastAPI, Header, HTTPException, Request
from typing import Optional
import time

app = FastAPI()

CERB_KEY = "dummy"

def check_api_key(x_api_key: Optional[str]):
    if not CERB_KEY:
        raise HTTPException(status_code=500, detail="Server missing CERBERUS_API_KEY")
    if not x_api_key or x_api_key.strip() != CERB_KEY:
        raise HTTPException(status_code=403, detail="Forbidden (bad or missing API key)")

@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time()), "has_api_key": bool(CERB_KEY)}

@app.post("/run")
def run_job(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
):
    check_api_key(x_api_key)
    return {"ok": True, "message": "Job executed"}

@app.post("/debug/echo")
async def debug_echo(request: Request):
    body = await request.body()
    return {"received_headers": dict(request.headers), "body": body.decode()}
