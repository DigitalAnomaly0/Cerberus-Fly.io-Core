
import hashlib, base64, json, os
from typing import Dict, Any

from packager import pack as pack_artifact
from core.pipeline import run_pipeline as run_pipeline_demo
from core.pipeline_runtime import run_pipeline_runtime
from core.runtime import get_providers
from core.models import DemoGovernor, DemoSeeder, DemoAntithesis
from analytics.reports import generate_reports
from tools.search import run_search, get_provider
from tools.http_fetch import HttpFetcher

def _pack(job_name: str, args: Dict[str, Any], result: Dict[str, Any], meta_extra=None):
    extra_files = {}
    # Inject any precomputed extra files (e.g., research outputs)
    for k in (result.get("_extra_files") or {}):
        extra_files[k] = result["_extra_files"][k]

    # Ensure reports/vars.json is present (fallback)
    if "reports/vars.json" not in extra_files:
        env_used = {k: os.getenv(k) for k in ('CERBERUS_IMPL','CERBERUS_PROFILE','SEARCH_PROVIDER','SERPAPI_KEY','BING_SUBSCRIPTION_KEY','BING_ENDPOINT')}
        vars_doc = {
            "schema_version": "fallback-1",
            "profile_name": str(args.get("profile") or env_used.get("CERBERUS_PROFILE") or "baseline"),
            "sources": {},  # detailed sources emitted by pipeline when available
            "resolved": {k:v for k,v in args.items() if k not in ("topic",)},
            "environment": env_used
        }
        extra_files["reports/vars.json"] = json.dumps(vars_doc, indent=2).encode("utf-8")

    if result:
        if "claims" in result:
            extra_files["data/claims.json"] = json.dumps(result["claims"], indent=2).encode("utf-8")
        if "expanded" in result:
            extra_files["data/expanded.json"] = json.dumps(result["expanded"], indent=2).encode("utf-8")
        if "counters" in result:
            extra_files["data/counters.json"] = json.dumps(result["counters"], indent=2).encode("utf-8")
        if "dam_duplicate" in result:
            extra_files["data/dam_duplicate.json"] = json.dumps(result["dam_duplicate"], indent=2).encode("utf-8")
        # Summary
        summary = ["# Cerberus Job Summary"]
        if "provider_mode" in result:
            summary.append("Provider mode: " + str(result.get("provider_mode")))
        if "topic" in result:
            summary.append("Topic: " + str(result["topic"]))
        if "counts" in result:
            summary.append("Counts: " + json.dumps(result["counts"]))
        if result.get("_research_meta"):
            summary.append("Research: " + json.dumps(result["_research_meta"]))
        extra_files["reports/summary.md"] = "\n".join(summary).encode("utf-8")

        # Analytics reports (only if core datasets exist)
        if any(k in result for k in ("claims","expanded","counters","dam_duplicate")):
            claims = result.get("claims") or []
            expanded = result.get("expanded") or []
            counters = result.get("counters") or []
            dam_dup = result.get("dam_duplicate") or {"groups":[]}
            for path, blob in generate_reports(claims, expanded, counters, dam_dup).items():
                extra_files[path] = blob

    bundle = pack_artifact(job_name, args, extra_files=extra_files, meta_extra=meta_extra or {})
    zip_bytes = bundle["zip_bytes"]
    sha = hashlib.sha256(zip_bytes).hexdigest()
    b64 = base64.b64encode(zip_bytes).decode("ascii")
    artifact = {
        "filename": bundle["filename"],
        "mime": "application/zip",
        "size_bytes": len(zip_bytes),
        "sha256": sha,
        "base64": b64,
    }
    job_id = bundle["manifest"]["run_id"]
    return {"job_id": job_id, "status": "done", "message": "ok", "artifacts": [artifact]}

def _maybe_run_research(args: Dict[str, Any]) -> Dict[str, bytes] | None:
    if not args.get("enable_research"):
        return None
    topic = args.get("topic") or ""
    query = args.get("search_query") or topic
    max_results = int(args.get("search_max", 8))
    fetch_max = int(args.get("fetch_max", 5))
    provider_name = args.get("search_provider")  # defaults to env or dummy
    results = run_search(query, max_results=max_results, provider_name=provider_name)
    # serialize search results
    extra = {"research/search_results.json": json.dumps({"query": query, "results": results}, indent=2).encode("utf-8")}
    # fetch top K
    fetcher = HttpFetcher(timeout=float(args.get("fetch_timeout", 8.0)))
    errors = []
    lines = []
    for r in results[:fetch_max]:
        url = r["url"]
        rec = {"url": url, "provider": r.get("provider"), "fetched_at": None}
        try:
            fr = fetcher.fetch(url)
            rec.update({
                "status": fr.status,
                "content_type": fr.content_type,
                "encoding": fr.encoding,
                "content_hash": fr.content_hash,
                "bytes": fr.bytes,
                "title": fr.title,
                "text_preview": fr.text_preview[:400],
                "fetched_at": fr.fetched_at,
            })
        except Exception as e:
            rec["error"] = str(e)
            errors.append({"url": url, "error": str(e)})
        lines.append(json.dumps(rec, ensure_ascii=False))
    extra["research/fetches.jsonl"] = ("\n".join(lines)).encode("utf-8")
    if errors:
        extra["research/errors.jsonl"] = ("\n".join(json.dumps(e) for e in errors)).encode("utf-8")
    return extra

def process_job(job_payload: Dict[str, Any]) -> Dict[str, Any]:
    job_name = (job_payload.get("job_name") or "").lower()
    args = job_payload.get("args") or {}
    topic = args.get("topic", "Sample Topic")
    n = int(args.get("n", 5))

    pre_extra = _maybe_run_research(args) or {}

    # DEMO JOBS
    if job_name in ("demo_governor", "demo_seeder", "demo_antithesis", "demo_core", "full_demo"):
        if job_name == "demo_governor":
            gov = DemoGovernor()
            claims = gov.run(topic=topic, seed=int(args.get("seed", 42)), n=n)
            result = {"topic": topic, "claims": claims, "counts": {"claims": len(claims)}}
            if pre_extra:
                result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
                result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
            return _pack(job_name, args, result, meta_extra={"demo":"governor"})
        elif job_name == "demo_seeder":
            gov = DemoGovernor()
            base = gov.run(topic=topic, seed=int(args.get("seed_gov", 42)), n=n)
            sd = DemoSeeder()
            expanded = sd.run(base, seed=int(args.get("seed_seed", 7)))
            result = {"topic": topic, "claims": base, "expanded": expanded,
                      "counts": {"claims": len(base), "expanded": len(expanded)}}
            if pre_extra:
                result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
                result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
            return _pack(job_name, args, result, meta_extra={"demo":"seeder"})
        elif job_name == "demo_antithesis":
            gov = DemoGovernor()
            base = gov.run(topic=topic, seed=int(args.get("seed_gov", 42)), n=n)
            at = DemoAntithesis()
            counters = at.run(base)
            result = {"topic": topic, "claims": base, "counters": counters,
                      "counts": {"claims": len(base), "counters": len(counters)}}
            if pre_extra:
                result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
                result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
            return _pack(job_name, args, result, meta_extra={"demo":"antithesis"})
        else:
            # demo_core/full_demo
            result = run_pipeline_demo(topic=topic, seed_governor=int(args.get("seed_gov", 42)), seed_seeder=int(args.get("seed_seed", 7)), n=n)
            if pre_extra:
                result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
                result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
            return _pack(job_name, args, result, meta_extra={"demo":"core"})

    # RUNTIME JOBS (REAL or DEMO fallback via runtime selector)
    if job_name in ("core", "pipeline"):
        args_rt = dict(args); [args_rt.pop(k, None) for k in ("topic","n")]; result = run_pipeline_runtime(topic=topic, seed_governor=int(args.get("seed_gov", 42)), seed_seeder=int(args.get("seed_seed", 7)), n=n, **args_rt)
        if pre_extra:
            result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
            result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
        return _pack(job_name, args, result, meta_extra={"provider_mode": result.get("provider_mode")})

    if job_name == "governor":
        Gov, Sd, Anti, mode = get_providers()
        gov = Gov()
        claims = gov.run(topic=topic, seed=int(args.get("seed_gov", 42)), n=n)
        result = {"topic": topic, "provider_mode": mode, "claims": claims, "counts": {"claims": len(claims)}}
        if pre_extra:
            result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
            result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
        return _pack(job_name, args, result, meta_extra={"provider_mode": mode})

    if job_name == "seeder":
        Gov, Sd, Anti, mode = get_providers()
        gov = Gov()
        base = gov.run(topic=topic, seed=int(args.get("seed_gov", 42)), n=n)
        sd = Sd()
        expanded = sd.run(base, seed=int(args.get("seed_seed", 7)))
        result = {"topic": topic, "provider_mode": mode, "claims": base, "expanded": expanded,
                  "counts": {"claims": len(base), "expanded": len(expanded)}}
        if pre_extra:
            result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
            result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
        return _pack(job_name, args, result, meta_extra={"provider_mode": mode})

    if job_name == "antithesis":
        Gov, Sd, Anti, mode = get_providers()
        gov = Gov()
        base = gov.run(topic=topic, seed=int(args.get("seed_gov", 42)), n=n)
        at = Anti()
        counters = at.run(base)
        result = {"topic": topic, "provider_mode": mode, "claims": base, "counters": counters,
                  "counts": {"claims": len(base), "counters": len(counters)}}
        if pre_extra:
            result["_extra_files"] = {**(result.get("_extra_files") or {}), **pre_extra}
            result["_research_meta"] = {"search_results": len(json.loads(pre_extra["research/search_results.json"])["results"])}
        return _pack(job_name, args, result, meta_extra={"provider_mode": mode})

    # Fallback (should not happen due to validation)
    return _pack(job_name, args, {"topic": topic}, meta_extra={})
