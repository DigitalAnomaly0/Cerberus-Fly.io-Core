import json

from typing import Dict, Any, Optional
from .runtime import get_providers
from .dedupe import group_duplicates
from core.governor_ext import EvidenceGovernor
from core import config
import yaml, time

def run_pipeline_runtime(topic: str, seed_governor: int = 42, seed_seeder: int = 7, n: int = 5, **kwargs) -> Dict[str, Any]:
    kwargs, profile_name = _apply_profile(kwargs)
    bt = BudgetTracker(profile=profile_name)
    env_used = {k: os.getenv(k) for k in ('CERBERUS_IMPL','CERBERUS_PROFILE','SEARCH_PROVIDER','SERPAPI_KEY','BING_SUBSCRIPTION_KEY','BING_ENDPOINT')}
    normalized_args, arg_sources = config.normalize_args(kwargs, profile_name, env_used)
    Gov, Sd, Anti, mode = get_providers()
    gov = Gov()

    enable_research = bool(normalized_args.get('enable_research'))
    search_max = int(normalized_args.get('search_max'))
    fetch_max = int(normalized_args.get('fetch_max'))
    provider_name = normalized_args.get('search_provider')

    claims = None
    meta = {"provider_mode": mode}

    bt.start('plan_research')
    if hasattr(gov, "plan") and hasattr(gov, "research") and hasattr(gov, "draft_claims"):
        objectives = gov.plan(topic)
        research = gov.research(objectives, search_max=search_max, fetch_max_per_obj=max(0, fetch_max), provider_name=provider_name)
        claims = gov.draft_claims(topic, research, n=n)
        meta["path"] = "real_provider_advanced"
        meta["objectives"] = objectives
        bt.end('plan_research', objectives=len(objectives), search=search_max, fetch=fetch_max)
    elif enable_research:
        eg = EvidenceGovernor(fetch_timeout=float(kwargs.get("fetch_timeout", 8.0)))
        objectives = eg.plan(topic)
        research = eg.research(objectives, search_max=search_max, fetch_max_per_obj=max(0, fetch_max), provider_name=provider_name)
        claims = eg.draft_claims(topic, research, n=n)
        meta["path"] = "evidence_governor"
        meta["objectives"] = objectives
        bt.end('plan_research', objectives=len(objectives), search=search_max, fetch=fetch_max)
    else:
        claims = gov.run(topic=topic, seed=seed_governor, n=n)
        meta["path"] = "legacy_gov_run"
        bt.end('plan_research', objectives=0)

    sd = Sd()
    # Prefer advanced seeder methods when available
    expanded = None
    if hasattr(sd, "expand"):
        expanded = sd.expand(claims, n_per_claim=int(normalized_args.get('n_per_claim')), style=normalized_args.get('style'))
        if hasattr(sd, "enrich_with_sources") and bool(kwargs.get("enable_research")):
            expanded = sd.enrich_with_sources(expanded, search_provider=provider_name, search_max=int(normalized_args.get('search_max')))
        if hasattr(sd, "consolidate"):
            expanded = sd.consolidate(expanded)
    else:
        try:
            from core.seeder_ext import EvidenceSeeder
            if bool(kwargs.get("enable_research")):
                es = EvidenceSeeder()
                expanded = es.expand(claims, n_per_claim=int(normalized_args.get('n_per_claim')), style=normalized_args.get('style'))
                expanded = es.enrich_with_sources(expanded, search_provider=provider_name, search_max=int(normalized_args.get('search_max')))
                expanded = es.consolidate(expanded)
        except Exception:
            expanded = None
    if expanded is None:
        expanded = sd.run(claims, seed=seed_seeder)
    bt.end('expand', expanded=len(expanded))

    anti = Anti()
    bt.start('counters')
    counters = anti.run(claims + expanded)
    bt.end('counters', counters=len(counters))

    # Verification + Ranking (prefer provider's methods; else fallback)
    extra_reports = {}
    verifier = getattr(anti, "verify", None)
    ranker = getattr(anti, "score_rank", None)
    try:
        if callable(verifier) and callable(ranker):
            verity = anti.verify(claims, expanded, counters)
            ranking = anti.score_rank(claims, expanded, counters)
        else:
            from core.antithesis_ext import EvidenceAntithesis
            ea = EvidenceAntithesis()
            verity = ea.verify(claims, expanded, counters)
            ranking = ea.score_rank(claims, expanded, counters)
        extra_reports["reports/verity.json"] = json.dumps(verity, indent=2).encode("utf-8")
        extra_reports["reports/ranking.json"] = json.dumps(ranking, indent=2).encode("utf-8")
    except Exception:
        extra_reports = {}


    dam_dup = group_duplicates(claims + expanded + counters)

    try:
        extra_reports["reports/budgets.json"] = json.dumps(bt.to_report(), indent=2).encode("utf-8")
    except Exception:
        pass
    try:
        lr = ledger_entry(meta.get('provider_mode',''), topic, {"claims": len(claims), "expanded": len(expanded), "counters": len(counters)}, profile_name, None)
        s = json.dumps(lr, separators=(",", ":"))
        import hashlib
        h = hashlib.sha256(s.encode("utf-8")).hexdigest()
        extra_reports["reports/ledger.jsonl"] = (s+"\n").encode("utf-8")
        extra_reports["reports/vars.json"] = json.dumps({
            "schema_version": config.SCHEMA_VERSION,
            "profile_name": profile_name,
            "sources": arg_sources,
            "resolved": normalized_args,
            "environment": env_used
        }, indent=2).encode("utf-8")
        extra_reports["ledger/last_hash.txt"] = h.encode("utf-8")
    except Exception:
        pass

    return {
        "topic": topic,
        "provider_mode": mode,
        "claims": claims,
        "expanded": expanded,
        "counters": counters,
        "dam_duplicate": dam_dup,
        "counts": {
            "claims": len(claims),
            "expanded": len(expanded),
            "counters": len(counters),
            "dup_groups": dam_dup["total_groups"]
        },
        "meta": meta,
        "_extra_files": extra_reports if extra_reports else None
    }

import os
from core.budgets import BudgetTracker, ledger_entry
def _apply_profile(kwargs: dict):
    prof_name = str(kwargs.get("profile") or os.getenv("CERBERUS_PROFILE") or "baseline")
    try:
        from pathlib import Path
        here = Path(__file__).resolve().parents[1]
        ypath = here / "profiles" / "profiles.yaml"
        data = yaml.safe_load(ypath.read_text(encoding="utf-8")) if ypath.exists() else {}
    except Exception:
        data = {}
    layer = data.get(prof_name) or {}
    out = dict(layer); out.update(kwargs)
    return out, prof_name
