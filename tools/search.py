
from __future__ import annotations
import os, time, random, json
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
from dataclasses import dataclass
import threading

from .errors import ProviderError, RateLimitError, TimeoutError
from .util import now_iso

@dataclass
class SearchResult:
    rank: int
    title: str
    url: str
    snippet: str
    provider: str
    fetched_at: str

@runtime_checkable
class SearchProvider(Protocol):
    name: str
    def search(self, query: str, *, max_results: int = 10, timeout: float = 8.0) -> List[SearchResult]: ...

# --- Rate limiter (token bucket) ---
class TokenBucket:
    def __init__(self, capacity: int, refill_per_sec: float):
        self.capacity = capacity
        self.refill = refill_per_sec
        self.tokens = capacity
        self.last = time.time()
        self.lock = threading.Lock()

    def take(self, n=1) -> bool:
        with self.lock:
            now = time.time()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False

# --- Providers ---
class DummySearchProvider:
    name = "dummy"
    def search(self, query: str, *, max_results: int = 10, timeout: float = 8.0) -> List[SearchResult]:
        random.seed(hash(query) & 0xffffffff)
        results: List[SearchResult] = []
        for i in range(max_results):
            k = i + 1
            results.append(SearchResult(
                rank=k,
                title=f"{query} — reference #{k}",
                url=f"https://example.com/{query.replace(' ','-')}/{k}",
                snippet=f"Synthetic result for '{query}', item {k}.",
                provider=self.name,
                fetched_at=now_iso(),
            ))
        return results

class SerpApiProvider:
    name = "serpapi"
    def __init__(self):
        key = os.getenv("SERPAPI_KEY")
        if not key:
            raise ProviderError("SERPAPI_KEY not set", provider=self.name)
        self.key = key
        self.bucket = TokenBucket(capacity=5, refill_per_sec=0.5)

    def search(self, query: str, *, max_results: int = 10, timeout: float = 8.0) -> List[SearchResult]:
        if not self.bucket.take():
            raise RateLimitError("rate limited")
        import requests
        params = {"engine":"google", "q":query, "num":max_results, "api_key": self.key}
        r = requests.get("https://serpapi.com/search", params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        results: List[SearchResult] = []
        organic = data.get("organic_results", [])[:max_results]
        for i, item in enumerate(organic, 1):
            results.append(SearchResult(
                rank=i,
                title=item.get("title") or "",
                url=item.get("link") or "",
                snippet=item.get("snippet") or "",
                provider=self.name,
                fetched_at=now_iso(),
            ))
        return results

class BingWebProvider:
    name = "bing"
    def __init__(self):
        key = os.getenv("BING_SUBSCRIPTION_KEY")
        if not key:
            raise ProviderError("BING_SUBSCRIPTION_KEY not set", provider=self.name)
        self.key = key
        self.endpoint = os.getenv("BING_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
        self.bucket = TokenBucket(capacity=7, refill_per_sec=0.7)

    def search(self, query: str, *, max_results: int = 10, timeout: float = 8.0) -> List[SearchResult]:
        if not self.bucket.take():
            raise RateLimitError("rate limited")
        import requests
        headers = {"Ocp-Apim-Subscription-Key": self.key}
        params = {"q": query, "count": max_results, "mkt": "en-US", "textDecorations": True, "textFormat": "Raw"}
        r = requests.get(self.endpoint, headers=headers, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        web_pages = (data.get("webPages") or {}).get("value") or []
        results: List[SearchResult] = []
        for i, item in enumerate(web_pages[:max_results], 1):
            results.append(SearchResult(
                rank=i,
                title=item.get("name") or "",
                url=item.get("url") or "",
                snippet=item.get("snippet") or "",
                provider=self.name,
                fetched_at=now_iso(),
            ))
        return results

# --- Factory ---
def get_provider(name: Optional[str] = None) -> SearchProvider:
    name = (name or os.getenv("SEARCH_PROVIDER") or "dummy").lower()
    if name == "dummy":
        return DummySearchProvider()
    if name == "serpapi":
        return SerpApiProvider()
    if name == "bing":
        return BingWebProvider()
    raise ProviderError(f"unknown provider: {name}", provider=name)

def run_search(query: str, *, max_results: int = 10, provider_name: Optional[str] = None, timeout: float = 8.0) -> List[Dict[str,Any]]:
    prov = get_provider(provider_name)
    results = prov.search(query, max_results=max_results, timeout=timeout)
    return [r.__dict__ for r in results]
