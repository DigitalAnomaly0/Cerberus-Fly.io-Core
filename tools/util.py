
import json, hashlib, time, datetime, re
from typing import Any

def safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)

def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_text(t: str) -> str:
    return sha256_bytes(t.encode("utf-8", errors="ignore"))

def strip_html(html: str) -> str:
    if not html:
        return ""
    # very naive tag stripper
    return re.sub(r"<[^>]+>", " ", html)
