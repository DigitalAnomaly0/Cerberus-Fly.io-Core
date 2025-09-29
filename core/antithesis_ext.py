from __future__ import annotations
from typing import List, Dict, Any
import statistics

class EvidenceAntithesis:
    """
    Verification + ranking utilities when provider doesn't implement them.
    """
    def oppose(self, items: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        # Not used here; oppose is handled by provider Anti.run in pipeline.
        return []

    def verify(self, claims: List[Dict[str,Any]], expanded: List[Dict[str,Any]], counters: List[Dict[str,Any]]) -> Dict[str,Any]:
        # Simple checks for missing citations, short texts, and coverage
        def toklen(t: str) -> int:
            import re
            return len(re.findall(r"[a-z0-9]+", (t or "").lower()))
        issues = {"claims": [], "expanded": []}
        claim_targets = {c.get("id"): 0 for c in claims}
        for ct in counters:
            target = ct.get("target") or ct.get("target_id")
            if target in claim_targets:
                claim_targets[target] += 1

        for c in claims:
            cid = c.get("id")
            tlen = toklen(c.get("text",""))
            errs = []
            if tlen < 6:
                errs.append("short_text")
            if not c.get("citations"):
                errs.append("missing_citations")
            if claim_targets.get(cid, 0) == 0:
                errs.append("no_counters")
            if errs:
                issues["claims"].append({"id": cid, "errors": errs})
        for ex in expanded:
            eid = ex.get("id")
            errs = []
            if not ex.get("citations"):
                errs.append("missing_citations")
            if errs:
                issues["expanded"].append({"id": eid, "errors": errs})
        summary = {
            "counts": {
                "claims": len(claims),
                "expanded": len(expanded),
                "counters": len(counters),
                "claims_with_issues": len(issues["claims"]),
                "expanded_with_issues": len(issues["expanded"]),
            },
            "pass": (len(issues["claims"]) + len(issues["expanded"])) == 0
        }
        return {"summary": summary, "issues": issues}

    def score_rank(self, claims: List[Dict[str,Any]], expanded: List[Dict[str,Any]], counters: List[Dict[str,Any]]) -> Dict[str,Any]:
        # Scoring rubric per claim:
        # support = min(1.0, expansions/3)
        # evidence = min(1.0, (claim_cites + expansion_cites)/4)
        # headwinds = min(1.0, counters/3)
        # score = 0.55*support + 0.35*evidence - 0.25*headwinds  (clamped to [0,1])
        ex_by_parent = {}
        for ex in expanded:
            p = ex.get("parent")
            ex_by_parent.setdefault(p, []).append(ex)
        counters_by_target = {}
        for ct in counters:
            t = ct.get("target") or ct.get("target_id")
            counters_by_target.setdefault(t, []).append(ct)

        rows = []
        for c in claims:
            cid = c.get("id")
            exp = ex_by_parent.get(cid, [])
            n_exp = len(exp)
            support = min(1.0, n_exp/3.0)

            claim_cites = len(c.get("citations", []))
            exp_cites = sum(len(e.get("citations", [])) for e in exp)
            evidence = min(1.0, (claim_cites + exp_cites)/4.0)

            n_ct = len(counters_by_target.get(cid, []))
            headwinds = min(1.0, n_ct/3.0)

            score = 0.55*support + 0.35*evidence - 0.25*headwinds
            score = max(0.0, min(1.0, score))
            rows.append({
                "claim_id": cid,
                "support": round(support,3),
                "evidence": round(evidence,3),
                "headwinds": round(headwinds,3),
                "score": round(score,3)
            })

        rows_sorted = sorted(rows, key=lambda r: r["score"], reverse=True)
        stats = {
            "avg_score": round(statistics.mean([r["score"] for r in rows_sorted]),3) if rows_sorted else 0.0
        }
        return {"stats": stats, "ranking": rows_sorted}
