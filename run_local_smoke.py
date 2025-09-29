
import os, sys, json, base64, io, zipfile, importlib
ROOT = __file__.rsplit('/', 1)[0]
if ROOT not in sys.path: sys.path.insert(0, ROOT)

os.environ.setdefault("SEARCH_PROVIDER", "dummy")
worker = importlib.import_module("jobs.worker")
resp = worker.process_job({"job_name":"core","args":{
    "topic":"Consolidated Smoke",
    "n": 5,
    "enable_research": True,
    "search_max": 6,
    "fetch_max": 0,
    "n_per_claim": 2,
    "style": "concise"
}})
art = resp["artifacts"][0]
print(json.dumps({"ok": True, "artifact": art["filename"]}))
