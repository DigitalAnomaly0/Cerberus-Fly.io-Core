from __future__ import annotations
from typing import Dict, Any, Tuple

SCHEMA_VERSION = "2025-09-28.1"

# Simple spec with defaults and bounds (lightweight; not full JSON Schema validation)
SPEC: Dict[str, Dict[str, Any]] = {
    "n": {"type": int, "default": 5, "min": 1, "max": 100},
    "enable_research": {"type": bool, "default": True},
    "search_provider": {"type": str, "enum": ["dummy","serpapi","bing"]},
    "search_max": {"type": int, "default": 6, "min": 1, "max": 25},
    "fetch_max": {"type": int, "default": 1, "min": 0, "max": 25},
    "fetch_timeout": {"type": float, "default": 8.0, "min": 1.0, "max": 60.0},
    "n_per_claim": {"type": int, "default": 2, "min": 1, "max": 10},
    "style": {"type": str, "default": None},
    "seed_gov": {"type": int, "default": 42},
    "seed_seed": {"type": int, "default": 7},
    "profile": {"type": str, "enum": ["baseline","micro_iterations","heavy_verification"], "default": "baseline"},
}

def _coerce(name: str, value: Any, spec: Dict[str, Any]):
    t = spec.get("type")
    if t and value is not None:
        try:
            if t is bool and isinstance(value, str):
                v = value.strip().lower()
                if v in ("1","true","yes","on"): return True
                if v in ("0","false","no","off"): return False
            return t(value)
        except Exception:
            return spec.get("default")
    return value

def normalize_args(kwargs: Dict[str, Any], profile_name: str, env: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Returns (resolved_args, sources) where sources[k] indicates 'arg' | 'profile' | 'env' | 'default'
    """
    out: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for k, spec in SPEC.items():
        if k in kwargs and kwargs[k] is not None:
            out[k] = _coerce(k, kwargs[k], spec)
            sources[k] = "arg"
        elif k in ("search_provider",) and env.get("SEARCH_PROVIDER"):
            out[k] = _coerce(k, env.get("SEARCH_PROVIDER"), spec)
            sources[k] = "env"
        elif k in kwargs.get("_profile_layer", {}):
            out[k] = _coerce(k, kwargs["_profile_layer"][k], spec)
            sources[k] = "profile"
        else:
            out[k] = spec.get("default")
            sources[k] = "default"

        # clip ranges
        if out[k] is not None:
            if "min" in spec: out[k] = max(spec["min"], out[k])
            if "max" in spec: out[k] = min(spec["max"], out[k])
            if "enum" in spec and out[k] not in spec["enum"]:
                out[k] = spec.get("default")

    return out, sources
