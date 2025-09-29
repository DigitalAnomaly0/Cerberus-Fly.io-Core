
from __future__ import annotations
from typing import List, Dict, Any, Optional
import random

from tools.search import run_search
from tools.http_fetch import HttpFetcher

class EvidenceGovernor:
    """
    Fallback governor that can:
    - plan(): derive sub-queries from a topic
    - research(): search + (optional) fetch top URLs
    - draft_claims(): emit n claims with citations

    Used when a real Governor doesn't expose advanced methods and enable_research=True.
    """
    def __init__(self, fetch_timeout: float = 8.0):
        self.fetcher = HttpFetcher(timeout=fetch_timeout)

    def plan(self, topic: str, *, n_objectives: int = 3) -> List[Dict[str, Any]]:
        seeds = ["history", "current debates", "counterpoints", "policy", "ethics", "data"]
        random.shuffle(seeds)
        qs = [f"{topic} {s}" for s in seeds[:max(1, n_objectives)]]
        return [{"objective_id": f"obj-{i+1}", "query": q} for i, q in enumerate(qs)]

    def research(self, objectives: List[Dict[str,Any]], *, search_max: int = 6, fetch_max_per_obj: int = 2, provider_name: Optional[str] = None) -> Dict[str, Any]:
        search_results: List[Dict[str,Any]] = []
        fetches: List[Dict[str,Any]] = []
        for obj in objectives:
            q = obj["query"]
            rs = run_search(q, max_results=search_max, provider_name=provider_name)
            for r in rs:
                r["objective_id"] = obj["objective_id"]
            search_results.extend(rs)
            for r in rs[:fetch_max_per_obj]:
                url = r["url"]
                try:
                    fr = self.fetcher.fetch(url)
                    fetches.append({
                        "objective_id": obj["objective_id"],
                        "url": url,
                        "status": fr.status,
                        "content_type": fr.content_type,
                        "encoding": fr.encoding,
                        "content_hash": fr.content_hash,
                        "bytes": fr.bytes,
                        "title": fr.title,
                        "text_preview": fr.text_preview[:500],
                        "fetched_at": fr.fetched_at
                    })
                except Exception as e:
                    fetches.append({"objective_id": obj["objective_id"], "url": url, "error": str(e)})
        return {"search_results": search_results, "fetches": fetches}

    def draft_claims(self, topic: str, research: Dict[str,Any], *, n: int = 5) -> List[Dict[str,Any]]:
        grouped = {}
        for r in research.get("search_results", []):
            grouped.setdefault(r["objective_id"], []).append(r)
        claims: List[Dict[str,Any]] = []
        obj_ids = list(grouped.keys()) or ["obj-1"]
        for i in range(n):
            oid = obj_ids[i % len(obj_ids)]
            picked = grouped.get(oid, [])[:2]
            label = ", ".join([p.get("title") or p["url"] for p in picked]) if picked else "initial analysis"
            text = f"{topic}: Key point {i+1} — synthesized from {label}."
            claims.append({
                "id": f"cl-{i+1}",
                "text": text,
                "objective_id": oid,
                "citations": [
                    {"url": p["url"], "title": p.get("title",""), "provider": p.get("provider"), "rank": p.get("rank")}
                    for p in picked
                ]
            })
        return claims
