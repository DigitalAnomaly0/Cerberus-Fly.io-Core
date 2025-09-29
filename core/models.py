from typing import List, Dict, Any, Optional
import random, hashlib

from tools.search import run_search
from tools.http_fetch import HttpFetcher

def _id(prefix: str, text: str) -> str:
    h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]
    return f"{prefix}-{h}"

def _toklen(t: str) -> int:
    import re
    return len(re.findall(r"[a-z0-9]+", (t or "").lower()))

class DemoGovernor:
    """Demo governor with advanced methods and legacy run() for backward-compat."""
    def __init__(self):
        self.fetcher = HttpFetcher(timeout=8.0)

    def plan(self, topic: str, *, n_objectives: int = 3) -> List[Dict[str, Any]]:
        seeds = ["history", "current debates", "counterpoints", "policy", "ethics", "data"]
        rnd = random.Random(hash(topic) & 0xffffffff)
        rnd.shuffle(seeds)
        qs = [f"{topic} {s}" for s in seeds[:max(1, n_objectives)]]
        return [{"objective_id": f"obj-{i+1}", "query": q} for i, q in enumerate(qs)]

    def research(self, objectives: List[Dict[str,Any]], *, search_max: int = 6, fetch_max_per_obj: int = 0, provider_name: Optional[str] = None, fetch_timeout: float = 8.0) -> Dict[str, Any]:
        search_results: List[Dict[str,Any]] = []
        fetches: List[Dict[str,Any]] = []
        self.fetcher.timeout = fetch_timeout
        for obj in objectives:
            rs = run_search(obj["query"], max_results=search_max, provider_name=provider_name)
            for r in rs:
                r["objective_id"] = obj["objective_id"]
            search_results.extend(rs)
            for r in rs[:fetch_max_per_obj]:
                url = r["url"]
                try:
                    fr = self.fetcher.fetch(url)
                    fetches.append({
                        "objective_id": obj["objective_id"],
                        "url": url, "status": fr.status, "content_type": fr.content_type,
                        "encoding": fr.encoding, "content_hash": fr.content_hash, "bytes": fr.bytes,
                        "title": fr.title, "text_preview": fr.text_preview[:500], "fetched_at": fr.fetched_at
                    })
                except Exception as e:
                    fetches.append({"objective_id": obj["objective_id"], "url": url, "error": str(e)})
        return {"search_results": search_results, "fetches": fetches}

    def draft_claims(self, topic: str, research: Dict[str,Any], *, n: int = 5, style: Optional[str] = None) -> List[Dict[str,Any]]:
        grouped = {}
        for r in research.get("search_results", []):
            grouped.setdefault(r["objective_id"], []).append(r)
        obj_ids = list(grouped.keys()) or [None]
        claims: List[Dict[str,Any]] = []
        for i in range(n):
            oid = obj_ids[i % len(obj_ids)]
            picked = (grouped.get(oid, [])[:2] if oid else [])
            base = f"{topic} claim {i+1}"
            if style: base += f" [{style}]"
            text = base
            claim = {
                "id": _id("cl", f"{topic}-{i+1}-{oid or 'none'}"),
                "text": text,
                "objective_id": oid,
                "citations": [
                    {"url": p["url"], "title": p.get("title",""), "provider": p.get("provider"), "rank": p.get("rank")}
                    for p in picked
                ]
            }
            claims.append(claim)
        return claims

    def run(self, topic: str, seed: int = 42, n: int = 5, **kwargs) -> List[Dict[str, Any]]:
        if kwargs.get("enable_research"):
            objectives = self.plan(topic, n_objectives=3)
            research = self.research(objectives,
                                     search_max=int(kwargs.get("search_max", 6)),
                                     fetch_max_per_obj=int(kwargs.get("fetch_max", 0)),
                                     provider_name=kwargs.get("search_provider"),
                                     fetch_timeout=float(kwargs.get("fetch_timeout", 8.0)))
            return self.draft_claims(topic, research, n=n, style=kwargs.get("style"))
        rnd = random.Random(seed)
        out = []
        for i in range(n):
            text = f"{topic} claim {i+1}"
            out.append({"id": _id("cl", text), "text": text})
        return out

class DemoSeeder:
    def expand(self, claims: List[Dict[str,Any]], *, n_per_claim: int = 2, style: Optional[str] = None, **kw) -> List[Dict[str,Any]]:
        expanded: List[Dict[str,Any]] = []
        for c in claims:
            for k in range(n_per_claim):
                txt = f"{c['text']} — supporting argument {k+1}"
                if style: txt += f" [{style}]"
                expanded.append({"id": f"{c['id']}-ex{k+1}", "parent": c["id"], "text": txt})
        return expanded

    def enrich_with_sources(self, items: List[Dict[str,Any]], *, search_provider: Optional[str] = None, search_max: int = 4, **kw) -> List[Dict[str,Any]]:
        out = []
        for it in items:
            q = it.get("text") or ""
            rs = run_search(q[:120], max_results=search_max, provider_name=search_provider)
            cites = [{"url": r["url"], "title": r.get("title",""), "provider": r.get("provider"), "rank": r.get("rank")} for r in rs[:2]]
            it2 = dict(it)
            if cites: it2["citations"] = cites
            out.append(it2)
        return out

    def consolidate(self, expanded: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        return expanded

    def run(self, claims: List[Dict[str,Any]], seed: int = 7, **kwargs) -> List[Dict[str,Any]]:
        ex = self.expand(claims, n_per_claim=int(kwargs.get("n_per_claim", 2)), style=kwargs.get("style"))
        if kwargs.get("enable_research"):
            ex = self.enrich_with_sources(ex, search_provider=kwargs.get("search_provider"), search_max=int(kwargs.get("search_max", 4)))
        return self.consolidate(ex)

class DemoAntithesis:
    def run(self, items: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        counters = []
        targets = [it.get("id") for it in items]
        for t in targets:
            if not t: continue
            text = f"Counter to [{t}]: challenges the assertion"
            counters.append({"id": _id("ct", f"{t}-counter"), "text": text, "target": t})
        return counters

    def verify(self, claims: List[Dict[str,Any]], expanded: List[Dict[str,Any]], counters: List[Dict[str,Any]]) -> Dict[str,Any]:
        issues = {"claims": [], "expanded": []}
        claim_targets = {c.get("id"): 0 for c in claims}
        for ct in counters:
            tgt = ct.get("target")
            if tgt in claim_targets:
                claim_targets[tgt] += 1
        for c in claims:
            errs = []
            if _toklen(c.get("text","")) < 6: errs.append("short_text")
            if not c.get("citations"): errs.append("missing_citations")
            if claim_targets.get(c.get("id"), 0) == 0: errs.append("no_counters")
            if errs: issues["claims"].append({"id": c.get("id"), "errors": errs})
        for e in expanded:
            errs = []
            if not e.get("citations"): errs.append("missing_citations")
            if errs: issues["expanded"].append({"id": e.get("id"), "errors": errs})
        summary = {
            "counts": {"claims": len(claims), "expanded": len(expanded), "counters": len(counters),
                       "claims_with_issues": len(issues["claims"]), "expanded_with_issues": len(issues["expanded"]) },
            "pass": (len(issues["claims"]) + len(issues["expanded"])) == 0
        }
        return {"summary": summary, "issues": issues}

    def score_rank(self, claims: List[Dict[str,Any]], expanded: List[Dict[str,Any]], counters: List[Dict[str,Any]]) -> Dict[str,Any]:
        ex_by_parent = {}
        for e in expanded:
            ex_by_parent.setdefault(e.get("parent"), []).append(e)
        ct_by_target = {}
        for c in counters:
            ct_by_target.setdefault(c.get("target"), []).append(c)
        rows = []
        for c in claims:
            cid = c.get("id")
            n_exp = len(ex_by_parent.get(cid, []))
            support = min(1.0, n_exp/3.0)
            claim_cites = len(c.get("citations", []))
            exp_cites = sum(len(e.get("citations", [])) for e in ex_by_parent.get(cid, []))
            evidence = min(1.0, (claim_cites + exp_cites)/4.0)
            n_ct = len(ct_by_target.get(cid, []))
            headwinds = min(1.0, n_ct/3.0)
            score = 0.55*support + 0.35*evidence - 0.25*headwinds
            score = max(0.0, min(1.0, score))
            rows.append({"claim_id": cid, "support": round(support,3), "evidence": round(evidence,3), "headwinds": round(headwinds,3), "score": round(score,3)})
        rows_sorted = sorted(rows, key=lambda r: r["score"], reverse=True)
        import statistics
        stats = {"avg_score": round(statistics.mean([r["score"] for r in rows_sorted]),3) if rows_sorted else 0.0}
        return {"stats": stats, "ranking": rows_sorted}
