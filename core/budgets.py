from __future__ import annotations
import time, json, hashlib
from typing import Dict, Any, Optional

class BudgetTracker:
    def __init__(self, profile: str = "baseline"):
        self.profile = profile
        self.t0 = time.perf_counter()
        self.spans = []
        self.stack = []
        self.counts = {}

    def start(self, name: str):
        self.stack.append((name, time.perf_counter()))

    def end(self, name: str, **counts):
        if not self.stack or self.stack[-1][0] != name:
            return
        _, s = self.stack.pop()
        d = time.perf_counter() - s
        rec = {"name": name, "duration_s": round(d, 6)}
        if counts:
            rec["counts"] = counts
            for k, v in counts.items():
                self.counts[k] = self.counts.get(k, 0) + int(v or 0)
        self.spans.append(rec)

    def to_report(self) -> Dict[str, Any]:
        total = time.perf_counter() - self.t0
        return {"profile": self.profile, "total_duration_s": round(total, 6), "spans": self.spans, "totals": self.counts}

def ledger_entry(run_id: str, topic: str, counts: Dict[str,int], profile: str, pass_verity: Optional[bool]) -> Dict[str, Any]:
    line = {"run_id": run_id, "topic": topic, "counts": counts, "profile": profile, "pass_verity": pass_verity, "ts": int(time.time())}
    return line
