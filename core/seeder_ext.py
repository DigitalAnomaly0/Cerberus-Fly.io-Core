from __future__ import annotations
from typing import List, Dict, Any, Optional

from tools.search import run_search

class EvidenceSeeder:
    """Research-aware seeder: expand -> enrich_with_sources -> consolidate."""
    def __init__(self):
        pass

    def expand(self, claims: List[Dict[str,Any]], *, n_per_claim: int = 2, style: Optional[str] = None) -> List[Dict[str,Any]]:
        expanded: List[Dict[str,Any]] = []
        for c in claims:
            cid = c.get("id")
            base = c.get("text","")
            for k in range(n_per_claim):
                eid = f"{cid}-ex{k+1}" if cid else f"ex-{len(expanded)+1}"
                text = f"{base} — supporting argument {k+1}"
                if style:
                    text += f" [{style}]"
                expanded.append({"id": eid, "parent": cid, "text": text})
        return expanded

    def enrich_with_sources(self, items: List[Dict[str,Any]], *, search_provider: Optional[str] = None, search_max: int = 4) -> List[Dict[str,Any]]:
        out: List[Dict[str,Any]] = []
        for it in items:
            q = it.get("text") or ""
            results = run_search(q[:120], max_results=search_max, provider_name=search_provider)
            cites = [{"url": r["url"], "title": r.get("title",""), "provider": r.get("provider"), "rank": r.get("rank")} for r in results[:2]]
            it2 = dict(it)
            if cites:
                it2["citations"] = cites
            out.append(it2)
        return out

    def consolidate(self, expanded: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        return expanded
