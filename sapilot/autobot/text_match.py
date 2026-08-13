"""
Shared fuzzy text matching — used by the OCR targeting tier and by the
trainer's replay-time fallback when a recorded control id no longer exists
on the live screen. Deliberately dependency-free (difflib is stdlib) so
neither caller needs an ML model just to compare two short label strings.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TypeVar

T = TypeVar("T")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def similarity(a: str, b: str) -> float:
    """Ratio in [0, 1]; 1.0 = identical after normalization."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    # Bonus for exact substring containment (e.g. "LIFNR" inside "RF02K-LIFNR")
    # — a common case for SAP field-name tails matched against full names.
    if na in nb or nb in na:
        ratio = max(ratio, 0.85)
    return ratio


def best_match(
    target: str,
    candidates: list[tuple[str, T]],
    *,
    min_score: float = 0.55,
) -> tuple[T, float] | None:
    """
    candidates: list of (comparison_text, payload). Returns the
    highest-scoring (payload, score) pair, or None if nothing clears
    min_score.
    """
    best: tuple[T, float] | None = None
    for text, payload in candidates:
        score = similarity(target, text)
        if best is None or score > best[1]:
            best = (payload, score)
    if best is None or best[1] < min_score:
        return None
    return best
