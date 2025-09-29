
import math, statistics, re, collections
from typing import List, Dict, Any

# ---------- text helpers ----------
def _norm_text(t: str):
    import re
    return re.findall(r"[a-z0-9]+", (t or "").lower())

def _bow(text: str) -> Dict[str, int]:
    from collections import Counter
    return dict(Counter(_norm_text(text)))

def _cosine(a: Dict[str,int], b: Dict[str,int]) -> float:
    dot = sum(a.get(k,0)*b.get(k,0) for k in set(a)|set(b))
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    return (dot/(na*nb)) if na and nb else 0.0

# ---------- main entry ----------
def generate_reports(claims: List[Dict[str,Any]]|None, expanded: List[Dict[str,Any]]|None,
                     counters: List[Dict[str,Any]]|None, dam_duplicate: Dict[str,Any]|None) -> Dict[str, bytes]:
    claims = claims or []
    expanded = expanded or []
    counters = counters or []
    dam_duplicate = dam_duplicate or {"groups": []}

    # index helpers
    def _index(items, text_key="text"):
        idx = {}
        for it in items:
            i = it.get("id") or it.get("uid") or f"anon-{len(idx)}"
            idx[i] = {**it, "_text": it.get(text_key,"")}
        return idx

    claims_idx = _index(claims)
    expanded_idx = _index(expanded)
    counters_idx = _index(counters)

    parent_map = collections.defaultdict(list)
    for ex in expanded:
        p = ex.get("parent") or ex.get("parent_id")
        if p:
            parent_map[p].append(ex.get("id"))

    target_map = collections.defaultdict(list)
    for ct in counters:
        t = ct.get("target") or ct.get("target_id")
        if t:
            target_map[t].append(ct.get("id"))

    # 1) coverage
    coverage_rows = []
    for cid, c in claims_idx.items():
        n_expand = len(parent_map.get(cid, []))
        n_counter = len(target_map.get(cid, []))
        coverage_rows.append({
            "claim_id": cid,
            "text": c["_text"],
            "expanded_count": n_expand,
            "counters_count": n_counter,
            "has_expand": n_expand > 0,
            "has_counter": n_counter > 0,
        })
    coverage_stats = {
        "claims_total": len(claims_idx),
        "claims_with_expansion": sum(1 for x in coverage_rows if x["has_expand"]),
        "claims_with_counters": sum(1 for x in coverage_rows if x["has_counter"]),
        "avg_expansions_per_claim": (statistics.mean([x["expanded_count"] for x in coverage_rows]) if coverage_rows else 0),
        "avg_counters_per_claim": (statistics.mean([x["counters_count"] for x in coverage_rows]) if coverage_rows else 0),
    }

    # 2) graph
    nodes, edges = {}, []
    def _add_node(i, kind, text):
        nodes[i] = {"id": i, "kind": kind, "text": text}

    for cid, c in claims_idx.items():
        _add_node(cid, "claim", c["_text"])
        for exid in parent_map.get(cid, []):
            ex = expanded_idx.get(exid, {"_text":""})
            _add_node(exid, "expanded", ex["_text"])
            edges.append({"src": cid, "dst": exid, "type": "expands"})
        for ctid in target_map.get(cid, []):
            ct = counters_idx.get(ctid, {"_text":""})
            _add_node(ctid, "counter", ct["_text"])
            edges.append({"src": ctid, "dst": cid, "type": "counters"})

    deg_in = collections.Counter()
    deg_out = collections.Counter()
    for e in edges:
        deg_out[e["src"]] += 1
        deg_in[e["dst"]] += 1
    graph_stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "avg_in_degree": (statistics.mean(deg_in.values()) if deg_in else 0.0),
        "avg_out_degree": (statistics.mean(deg_out.values()) if deg_out else 0.0),
        "top_targets_by_counters": sorted(
            [{"id": nid, "in_degree": deg_in[nid], "kind": nodes[nid]["kind"], "text": nodes[nid]["text"][:140]}
             for nid in deg_in], key=lambda x: x["in_degree"], reverse=True)[:5],
    }

    # 3) similarity (claims only)
    bows = {cid: _bow(c["_text"]) for cid,c in claims_idx.items()}
    sim_rows = []
    cid_list = list(claims_idx.keys())
    for i in range(len(cid_list)):
        for j in range(i+1, len(cid_list)):
            c1, c2 = cid_list[i], cid_list[j]
            sim = _cosine(bows[c1], bows[c2])
            if sim >= 0.4:
                sim_rows.append({"a": c1, "b": c2, "cosine": round(sim,3)})

    # 4) balance
    balance = {
        "claims_without_counters": [x for x in coverage_rows if not x["has_counter"]],
        "claims_without_expansion": [x for x in coverage_rows if not x["has_expand"]],
    }

    # 5) redundancy
    groups = (dam_duplicate or {}).get("groups", [])
    redundancy = {
        "total_items_considered": len(claims_idx) + len(expanded_idx) + len(counters_idx),
        "duplicate_groups": len(groups),
        "avg_group_size": (statistics.mean([len(g.get("members",[])) for g in groups]) if groups else 0),
        "redundancy_index": (sum(len(g.get("members",[]))-1 for g in groups) / max(1, len(claims_idx)+len(expanded_idx)+len(counters_idx)))
    }

    # 6) quality heuristics (simple lexical)
    def _quality(text: str):
        toks = _norm_text(text)
        length = len(toks)
        uniq = len(set(toks))
        stop = len([t for t in toks if t in {"the","of","and","to","in","a","is","for","that","on","with","as"}])
        return {"len_tokens": length, "uniq_tokens": uniq, "stop_ratio": (stop/length if length else 0.0)}

    quality_rows = []
    def _accum(items, kind):
        for it in items:
            q = _quality(it.get("text","") or it.get("content",""))
            q["id"] = it.get("id") or it.get("uid")
            q["kind"] = kind
            quality_rows.append(q)
    _accum(list(claims_idx.values()), "claim")
    _accum(list(expanded_idx.values()), "expanded")
    _accum(list(counters_idx.values()), "counter")

    # 7) counter efficacy
    efficacy = []
    for cid, c in claims_idx.items():
        ec = len(target_map.get(cid, []))
        ex = len(parent_map.get(cid, []))
        efficacy.append({"claim_id": cid, "counter_per_expansion": (ec / (1+ex))})

    # return as bytes for packager extra_files
    import json
    def dump(obj): return json.dumps(obj, indent=2).encode("utf-8")
    return {
        "reports/coverage.json": dump({"stats": coverage_stats, "rows": coverage_rows}),
        "reports/graph.json": dump({"stats": graph_stats, "nodes": list(nodes.values()), "edges": edges}),
        "reports/similar_claims.json": dump(sim_rows),
        "reports/balance.json": dump(balance),
        "reports/redundancy.json": dump(redundancy),
        "reports/quality.json": dump(quality_rows),
        "reports/counter_efficacy.json": dump(efficacy),
    }
