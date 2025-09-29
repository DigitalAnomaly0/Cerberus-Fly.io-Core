
from typing import List, Dict, Any
import re, hashlib

def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[^a-z0-9 ]+', '', s)
    return s

def group_duplicates(items: List[Dict[str, Any]], text_key: str = "text") -> Dict[str, Any]:
    index = {}
    for i, it in enumerate(items):
        t = normalize_text(it.get(text_key, ""))
        if not t:
            continue
        h = hashlib.sha256(t.encode('utf-8')).hexdigest()[:12]
        index.setdefault(h, {"norm": t, "members": []})
        index[h]["members"].append({"idx": i, "id": it.get("id"), "text": it.get(text_key)})
    groups = []
    for h, data in index.items():
        if len(data["members"]) > 1:
            groups.append({"key": h, "norm": data["norm"], "members": data["members"]})
    return {"type": "dam_duplicate", "groups": groups, "total_groups": len(groups)}
