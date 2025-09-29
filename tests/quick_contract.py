
import os, sys, json, base64, io, zipfile, time
from pathlib import Path
import importlib.machinery, importlib.util

ROOT = Path(__file__).resolve().parents[1]
WS = ROOT.parent

def load_module(name: str, path: Path):
    raise NotImplementedError('unused')
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, str(path)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run_and_pack(args: dict) -> dict:
    import importlib
    # Purge core.* before importing
    for k in list(sys.modules.keys()):
        if k.startswith('core'):
            sys.modules.pop(k, None)
    # Put ROOT first so we import P17 core/
    sys.path.insert(0, str(ROOT))
    pr = importlib.import_module('core.pipeline_runtime')
    res = pr.run_pipeline_runtime(**args)

    # Merge datasets
    extra_files = {}
    for k in ("claims","expanded","counters","dam_duplicate"):
        if k in res and res[k] is not None:
            extra_files[f"data/{k}.json"] = json.dumps(res[k], indent=2).encode("utf-8")

    # Merge extras from runtime
    for k, v in (res.get("_extra_files") or {}).items():
        extra_files[k] = v

    # Analytics
    sys.path.append(str(ROOT))
    ar = __import__("analytics.reports", fromlist=["*"])
    claims = res.get("claims") or []
    expanded = res.get("expanded") or []
    counters = res.get("counters") or []
    dam_dup = res.get("dam_duplicate") or {"groups":[]}
    for path, b in ar.generate_reports(claims, expanded, counters, dam_dup).items():
        extra_files[path] = b

    # Pack using packager from P3
    p3 = sorted(WS.glob("P3-core-wiring-*"))[-1]
    sys.path.append(str(p3))
    pg = __import__("packager")
    pkg = pg.pack(job_name="core", args=args, extra_files=extra_files, meta_extra=res.get("meta") or {})
    # save artifact beside workspace for convenience
    out_path = ROOT.parent / ('contract_artifact_' + pkg['filename'])
    with open(out_path, 'wb') as f:
        f.write(pkg['zip_bytes'])
    return {"artifact": pkg, "artifact_path": str(out_path)}

def assert_contract(pkg: dict) -> dict:
    zdata = pkg["zip_bytes"]
    zf = zipfile.ZipFile(io.BytesIO(zdata), "r")
    names = set(zf.namelist())

    req_reports = {"reports/verity.json","reports/ranking.json","reports/budgets.json","reports/ledger.jsonl","reports/vars.json"}
    ok_reports = req_reports.issubset(names)

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

    ok = ok_reports and parent_ok and target_ok and citations_ok
    return {
        "ok": ok, "ok_reports": ok_reports, "parent_ok": parent_ok, "target_ok": target_ok,
        "cited_claims": cited_claims, "cited_exp": cited_exp, "names_count": len(names)
    }

if __name__ == "__main__":
    os.environ["SEARCH_PROVIDER"] = "dummy"
    args = {
        "topic":"Quick Contract Topic",
        "n": 5,
        "enable_research": True,
        "search_max": 6,
        "fetch_max": 0,
        "n_per_claim": 2,
        "style": "concise"
    }
    result = run_and_pack(args)
    status = assert_contract(result["artifact"])
    out = {
        "passed": bool(status["ok"]),
        "detail": status,
        "artifact_filename": result["artifact"]["filename"],
        "ts": int(time.time())
    }
    out['artifact_path'] = result.get('artifact_path')
    print(json.dumps(out, indent=2))
