"""When a path fails, pick a *different* object. Never the same key again."""
from __future__ import annotations

from typing import Any, Iterable

# Failed name → other objects that answer the same business question.
# These are not retries. They are a different door.
_ALTERNATES: dict[str, list[str]] = {
    "FARR_D_REVENUE": ["DD02L", "VBREVE", "VBREVK", "VBRK", "VBRP"],
    "FARR_D_FULFILL": ["VBREVR", "LIKP", "VBFA", "VBRK"],
    "FARR_D_POB": ["VBREVE", "VBAP", "VBRP"],
    "FARR_D_DEFITEM": ["BSID", "BSEG", "VBRK"],
    "FARR_D_CONTRACT": ["VBAK", "VBRK", "VBREVK"],
    "FARR_D_INV_ITM": ["VBRP", "VBREVE"],
    "FARR_D_BILLING": ["VBRK", "VBRP"],
    "FARR_D_POSTING": ["BKPF", "BSEG", "ACDOCA"],
    "FARR_RAI_HD": ["VBRK", "VBREVE"],
    "FARR_RAI_IT": ["VBRP", "VBREVE"],
}

# After this many ABSENT tables in one family, stop guessing that prefix.
_FAMILY_MISS_LIMIT = 2


def family_of(table: str) -> str:
    name = (table or "").strip().upper()
    if name.startswith("FARR"):
        return "FARR"
    if name.startswith("VBREV"):
        return "VBREV"
    if name.startswith(("VBAK", "VBAP", "VBRK", "VBRP", "LIKP")):
        return "SD"
    return name[:4] if len(name) >= 4 else name


def already_seen(table: str, seen: Iterable[str]) -> bool:
    return (table or "").strip().upper() in {s.strip().upper() for s in seen}


def next_paths(failed: str, seen: Iterable[str]) -> list[str]:
    """Different tables that still speak to the same question."""
    name = (failed or "").strip().upper()
    have = {s.strip().upper() for s in seen}
    have.add(name)
    out: list[str] = []
    for cand in _ALTERNATES.get(name, []):
        if cand not in have:
            out.append(cand)
    if name.startswith("FARR") and "DD02L" not in have and "DD02L" not in out:
        out.insert(0, "DD02L")
    return out[:4]


def abandon_family(counts: list[dict[str, Any]], prefix: str = "FARR") -> bool:
    misses = [
        c
        for c in counts
        if str(c.get("table") or "").upper().startswith(prefix)
        and (c.get("rank") == "ABSENT" or "does not exist" in str(c.get("notes") or "").lower())
    ]
    return len(misses) >= _FAMILY_MISS_LIMIT


def drop_family(queue: list[str], prefix: str, keep: Iterable[str]) -> list[str]:
    keep_u = {s.strip().upper() for s in keep}
    pre = prefix.upper()
    return [t for t in queue if not t.upper().startswith(pre) or t.upper() in keep_u]


def known_good(prefix: str, beliefs: Iterable[dict[str, Any]]) -> list[str]:
    """Tables in this family we already proved exist (live or empty)."""
    pre = prefix.upper()
    out = []
    for b in beliefs:
        key = str(b.get("key") or b.get("table") or "").upper()
        if key.startswith(pre) and (b.get("kind") in {"live", "empty"}):
            out.append(key)
    return out
