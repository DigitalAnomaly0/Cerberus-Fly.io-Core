
from __future__ import annotations
import os, re, time, hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .errors import FetchError, TimeoutError
from .util import now_iso, sha256_bytes, strip_html

@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    encoding: str
    content_hash: str
    bytes: int
    title: str
    text_preview: str
    fetched_at: str

class HttpFetcher:
    def __init__(self, timeout: float = 12.0, user_agent: Optional[str] = None):
        self.timeout = timeout
        self.ua = user_agent or "CerberusFetcher/1.0 (+https://example.com/bot)"
    def fetch(self, url: str) -> FetchResult:
        import requests
        try:
            r = requests.get(url, headers={"User-Agent": self.ua}, timeout=self.timeout)
        except requests.Timeout:
            raise TimeoutError(f"timeout fetching {url}")
        except Exception as e:
            raise FetchError(url, message=str(e))
        ct = r.headers.get("Content-Type","")
        enc = r.encoding or "utf-8"
        content = r.content or b""
        chash = sha256_bytes(content)
        status = r.status_code
        title = ""
        text_preview = ""
        if b"<html" in content[:2048].lower():
            # naive title and preview
            try:
                html = content.decode(enc, errors="ignore")
            except Exception:
                html = content.decode("utf-8", errors="ignore")
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I|re.S)
            title = (m.group(1).strip() if m else "")
            text_preview = strip_html(html)[:800]
        return FetchResult(
            url=url, status=status, content_type=ct, encoding=enc, content_hash=chash,
            bytes=len(content), title=title, text_preview=text_preview, fetched_at=now_iso()
        )
