
#!/usr/bin/env python3
import json, pathlib, statistics, math, csv, collections, importlib, datetime

root = pathlib.Path(__file__).resolve().parents[1]

def read_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows

def read_parquet(path):
    try:
        pa = importlib.import_module("pyarrow.parquet")
        table = pa.read_table(path)
        cols = table.column_names
        return [dict(zip(cols, row)) for row in zip(*[table[col].to_pylist() for col in cols])]
    except Exception:
        try:
            pd = importlib.import_module("pandas")
            df = pd.read_parquet(path)
            return df.to_dict(orient="records")
        except Exception as e:
            raise SystemExit(f"Parquet support requires pyarrow or pandas: {e}")

def load_gold(manifest):
    art = manifest.get("artifact")
    p = root / art
    if not p.exists():
        raise SystemExit(f"Artifact not found: {p}")
    if p.suffix.lower() == ".csv":
        return read_csv(p)
    if p.suffix.lower() == ".parquet":
        return read_parquet(p)
    return read_csv(p)

def percentile(values, p):
    if not values: return None
    s = sorted(values); k = (len(s)-1) * p
    f = math.floor(k); c = math.ceil(k)
    if f == c: return s[int(k)]
    return s[f] * (c-k) + s[c] * (k-f)

def histogram_0_1(values, bins=20):
    if not values: return []
    lo, hi = 0.0, 1.0
    width = (hi - lo) / bins
    edges = [lo + i*width for i in range(bins+1)]
    counts = [0]*bins
    for v in values:
        try: v = float(v)
        except: continue
        if v >= 1.0: idx = bins-1
        elif v < 0.0: idx = 0
        else: idx = int((v - lo) / width)
        counts[idx]+=1
    return [{"bin":[edges[i], edges[i+1]], "n": counts[i]} for i in range(bins)]

def graph_components(nodes, edges):
    g = collections.defaultdict(list)
    for s,t,_ in edges: g[s].append(t); g[t].append(s)
    seen=set(); sizes=[]
    for n in nodes:
        if n in seen: continue
        q=[n]; seen.add(n); c=1
        while q:
            u=q.pop()
            for v in g.get(u,[]):
                if v not in seen: seen.add(v); q.append(v); c+=1
        sizes.append(c)
    sizes.sort(reverse=True)
    return sizes

def main():
    manifest = json.loads((root/"gold"/"manifest.json").read_text(encoding="utf-8"))
    run_status = json.loads((root/"config"/"run_status.json").read_text(encoding="utf-8"))
    schema_versions = json.loads((root/"config"/"schema_versions.json").read_text(encoding="utf-8"))
    last_checks = json.loads((root/"reports"/"last_checks.json").read_text(encoding="utf-8"))
    prev_p = root/"reports"/"ui"/"report_prev.json"
    prev = json.loads(prev_p.read_text(encoding="utf-8")) if prev_p.exists() else {}

    gold_rows = load_gold(manifest)
    scores = []
    by_type = collections.defaultdict(list)
    for r in gold_rows:
        try: s = float(r.get("dai_score"))
        except Exception: continue
        scores.append(s); by_type[r.get("node_type","unknown")].append(s)

    by_type_means = {k: (sum(v)/len(v) if v else None) for k,v in by_type.items()}

    # Taxonomy
    list_cov = []; by_issue_stats = []
    list_p = root/"taxonomy"/"list_map.csv"
    if list_p.exists():
        issue_to_ids = collections.defaultdict(list)
        for row in read_csv(list_p):
            issue_to_ids[row["issue"]].append(row["node_id"])
        score_map = {}
        for r in gold_rows:
            nid = r.get("node_id")
            if not nid: continue
            try: score_map[nid] = float(r.get("dai_score"))
            except: pass
        for issue, ids in issue_to_ids.items():
            vals = [score_map[i] for i in ids if i in score_map]
            if vals:
                by_issue_stats.append({"issue": issue, "n": len(vals), "mean_dai": sum(vals)/len(vals)})
        by_issue_stats.sort(key=lambda x: (-x["n"], x["issue"]))
        list_cov = by_issue_stats

    # Citations
    edge_counts={}; top_nodes=[]; components=[]
    edges_p = root/"citations"/"edges.csv"
    if edges_p.exists():
        edges_rows = read_csv(edges_p)
        edge_counts = dict(collections.Counter([r["type"] for r in edges_rows]))
        indeg = collections.Counter([r["target"] for r in edges_rows])
        top_nodes = [{"node_id": nid, "indegree": indeg[nid]} for nid,_ in indeg.most_common(10)]
        nodes = set([r.get("node_id") for r in gold_rows if r.get("node_id")])
        edgelist = [(r["source"], r["target"], r["type"]) for r in edges_rows if r["source"] in nodes and r["target"] in nodes]
        components = [{"size": s} for s in graph_components(nodes, edgelist)[:10]]

    # Expectations
    datasets = last_checks.get("datasets", [])
    total_checks = sum(len(d.get("checks", [])) for d in datasets)
    passed_checks = sum(sum(1 for c in d.get("checks", []) if c.get("ok")) for d in datasets)
    rpr = (passed_checks / total_checks * 100.0) if total_checks else 0.0
    summary = [{"table": d["dataset"],
                "pass": sum(1 for c in d.get("checks", []) if c.get("ok")),
                "fail": sum(1 for c in d.get("checks", []) if not c.get("ok"))}
               for d in datasets]

    # Deltas vs previous
    prev_nodes = prev.get("sizes", {}).get("nodes_total")
    prev_mean = prev.get("dai_stats", {}).get("overall", {}).get("mean")
    deltas = {
        "against_prev": {
            "nodes_added": (len(gold_rows) - prev_nodes) if isinstance(prev_nodes,int) else None,
            "nodes_removed": None,
            "mean_dai_delta": ((sum(scores)/len(scores)) - prev_mean) if (scores and isinstance(prev_mean,(int,float))) else None,
            "expectation_new_fails": None
        }
    }

    report = {
      "title": "DAI Run Report",
      "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
      "bundle": {
        "dai_version": manifest.get("version"),
        "gold_manifest": "gold/manifest.json",
        "checks_green": bool(run_status.get("checks_green", False))
      },
      "schema": {
        "silver": schema_versions.get("silver", {}),
        "gold": schema_versions.get("gold", {}),
        "registry": {"subjects": []}
      },
      "sizes": {
        "nodes_total": len(gold_rows),
        "by_type": {k: len(v) for k,v in by_type.items()}
      },
      "dai_stats": {
        "overall": {
          "mean": (sum(scores)/len(scores)) if scores else None,
          "median": statistics.median(scores) if scores else None,
          "p10": percentile(scores, 0.10),
          "p90": percentile(scores, 0.90),
          "min": min(scores) if scores else None,
          "max": max(scores) if scores else None
        },
        "by_type": {k: {"mean": v} for k,v in by_type_means.items() if v is not None},
        "histogram": histogram_0_1(scores, bins=20)
      },
      "expectations": {
        "rpr_percent": rpr,
        "summary": summary
      },
      "taxonomy": {
        "list_coverage": list_cov,
        "by_issue_hist": []
      },
      "citations": {
        "edge_counts": edge_counts,
        "top_nodes": top_nodes,
        "components": components
      },
      "deltas": deltas,
      "performance": json.loads((root/'reports'/'stage_times.json').read_text(encoding='utf-8')) if (root/'reports'/'stage_times.json').exists() else {},
      "raw_tabs": {
        "sample_gold_head": gold_rows[:50],
        "schema_diff": {}
      },
      "top_risks": {
        "checks_largest_impact": [],
        "issues_lowest_mean_dai": [
            rec for rec in list_cov if rec.get("n",0) >= 2
        ][:10]
      }
    }

    out = root/"reports"/"ui"/"report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", out)

if __name__ == "__main__":
    main()
