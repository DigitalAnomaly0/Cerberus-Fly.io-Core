
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Any, Dict
import os, time, logging

from jobs.worker import process_job

log = logging.getLogger("cerberus.server")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

class JobRequest(BaseModel):
    job_name: str
    args: Dict[str, Any]

class JobResponse(BaseModel):
    job_name: str
    duration_ms: int
    artifacts: Any

app = FastAPI(title="Cerberus Job API", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/jobs/run", response_model=JobResponse)
def jobs_run(req: JobRequest, x_api_key: str | None = Header(default=None, alias="X-API-Key"), x_req_ts: str | None = Header(default=None, alias="X-Req-Ts")):
    t0 = time.perf_counter()

    # API key check (optional)
    required_key = os.getenv("CERBERUS_API_KEY")
    if required_key:
        if not x_api_key or x_api_key != required_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Timestamp freshness (optional)
    req_ts_enabled = str(os.getenv("REQUIRE_TIMESTAMP","")).lower() in ("1","true","yes","on")
    if req_ts_enabled:
        ts_raw = x_req_ts or (req.args.get("timestamp") if isinstance(req.args, dict) else None)
        if ts_raw is None:
            raise HTTPException(status_code=400, detail="Missing timestamp (X-Req-Ts or args.timestamp)")
        try:
            ts_val = int(str(ts_raw).strip())
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid timestamp format; must be epoch seconds")
        now = int(time.time())
        ttl = int(os.getenv("TIMESTAMP_TTL_SEC", "600"))  # default 10 minutes
        if abs(now - ts_val) > ttl:
            raise HTTPException(status_code=401, detail=f"Stale or future timestamp; allowed skew is +/-{ttl}s")

    try:
        resp = process_job({"job_name": req.job_name, "args": req.args})
    except Exception as e:
        log.exception("process_job failed")
        raise HTTPException(status_code=500, detail=str(e))

    dt = int((time.perf_counter() - t0) * 1000)
    return {"job_name": req.job_name, "duration_ms": dt, "artifacts": resp.get("artifacts", [])}
