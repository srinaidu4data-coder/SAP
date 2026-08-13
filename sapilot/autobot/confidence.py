"""
Statistical confidence for perception-driven actions.

When a target coordinate comes from a model (VLM eyeballing a screenshot,
OCR/fuzzy text matching) rather than an exact source (SAP GUI Scripting
control ID), we don't get a ground-truth guarantee — only a point estimate
that may be wrong. The self-consistency trick: ask for the same estimate
multiple times (independent samples, e.g. separate model calls or separate
OCR passes over slightly perturbed input) and use their agreement as a
confidence proxy. Tight cluster -> trustworthy; wide spread -> the estimator
itself doesn't know, so don't act on it blindly.

This mirrors conformal-prediction-style UQ for GUI grounding (predicted
point + calibrated spread) without needing a trained calibration model —
it's a cheap, dependency-free approximation good enough to gate retries and
human handoff.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ConfidenceResult:
    x: float
    y: float
    spread_px: float
    confidence: float
    samples: int

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.5


def confidence_from_samples(
    points: list[tuple[float, float]],
    *,
    tolerance_px: float = 15.0,
) -> ConfidenceResult:
    """
    Turn N independent (x, y) coordinate samples into a centroid + a
    confidence score in [0, 1].

    confidence = 1.0 when every sample lands within `tolerance_px` of the
    centroid (tight agreement); it decays toward 0 as the average distance
    from the centroid grows past that tolerance. `tolerance_px` should be
    set to roughly the smallest UI element you need to hit reliably (a
    checkbox or small icon needs a tighter tolerance than a wide button).
    """
    if not points:
        raise ValueError("confidence_from_samples requires at least one sample")

    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n

    if n == 1:
        return ConfidenceResult(x=cx, y=cy, spread_px=0.0, confidence=1.0, samples=1)

    distances = [math.hypot(px - cx, py - cy) for px, py in points]
    avg_spread = sum(distances) / n

    # 1.0 within tolerance, decaying linearly to 0 by 3x tolerance, floored at 0.
    if avg_spread <= tolerance_px:
        confidence = 1.0
    else:
        confidence = max(0.0, 1.0 - (avg_spread - tolerance_px) / (2 * tolerance_px))

    return ConfidenceResult(x=cx, y=cy, spread_px=avg_spread, confidence=confidence, samples=n)


def should_retry(result: ConfidenceResult, *, min_confidence: float = 0.5) -> bool:
    """Below this confidence: don't act, resample (e.g. zoomed crop) or escalate."""
    return result.confidence < min_confidence
