
import os, sys, json, base64, io, zipfile, importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
WS = ROOT.parent
try:
    import sys as _sys
    from pathlib import Path as _Path
    p3 = sorted((_Path(WS)).glob('P3-core-wiring-*'))[-1]
    _sys.path.append(str(p3))
except Exception:
    pass


RESULTS = {"tests": [], "summary": {"passed": 0, "failed": 0}}

def _record(name, ok, detail=None):
    RESULTS["tests"].append({"name": name, "ok": ok, "detail": detail or {}})
    RESULTS["summary"]["passed" if ok else "failed"] += 1

def test_provider_interfaces():
    rt = importlib.import_module("core.runtime")
    Gov, Sd, Anti, mode = rt.get_providers()
    g, s, a = Gov(), Sd(), Anti()
    g_ok = all(hasattr(g, m) for m in ("run","plan","research","draft_claims"))
    s_ok = all(hasattr(s, m) for m in ("run","expand","enrich_with_sources","consolidate"))
    a_ok = all(hasattr(a, m) for m in ("run","verify","score_rank"))
    ok = g_ok and s_ok and a_ok
    _record("provider_interfaces", ok, {"mode": mode})

def test_reports_and_linkages():
    # Use SEARCH_PROVIDER=dummy to avoid external deps
    os.environ.setdefault("SEARCH_PROVIDER", "dummy")
    worker = importlib.import_module("jobs.worker")
    resp = worker.process_job({"job_name":"core","args":{
        "topic":"Contract Test Topic",
        "n": 5,
        "enable_research": True,
        "search_max": 6,
        "fetch_max": 0,
        "n_per_claim": 2,
        "style": "concise"
    }})
    art = resp["artifacts"][0]
    zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(art["base64"])), "r")
    names = set(zf.namelist())
    req = {"reports/verity.json","reports/ranking.json","reports/budgets.json","reports/ledger.jsonl","reports/vars.json"}
    reports_ok = req.issubset(names)

    import json as _j
    claims = _j.loads(zf.read("data/claims.json"))
    expanded = _j.loads(zf.read("data/expanded.json"))
    counters = _j.loads(zf.read("data/counters.json"))
    claim_ids = {c["id"] for c in claims}
    exp_ids = {e["id"] for e in expanded}
    parent_ok = all(e.get("parent") in claim_ids for e in expanded)
    target_ok = all(ct.get("target") in claim_ids.union(exp_ids) for ct in counters)
    cited_claims = sum(1 for c in claims if c.get("citations"))
    cited_exp = sum(1 for e in expanded if e.get("citations"))
    citations_ok = cited_claims >= max(1, int(0.6*len(claims))) and cited_exp >= max(1, int(0.6*len(expanded)))
    ok = reports_ok and parent_ok and target_ok and citations_ok
    _record("reports_and_linkages", ok, {"reports_present": sorted(list(req.intersection(names))),
                                         "cited_claims": cited_claims, "cited_expanded": cited_exp})

if __name__ == "__main__":
    test_provider_interfaces()
    test_reports_and_linkages()
    print(json.dumps(RESULTS, indent=2))
