"""Load and evaluate tier-keyed destructive action denylist."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import yaml

from sapilot.exceptions import PolicyViolation
from sapilot.schemas import Action, ActionType, Tier


def _default_path() -> Path:
    return Path(__file__).with_name("denylist.yaml")


def load_denylist(path: Path | None = None) -> dict[str, Any]:
    p = path or _default_path()
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _match(patterns: list[str], candidate: str) -> bool:
    cand = candidate or ""
    for pat in patterns:
        if fnmatch.fnmatch(cand, pat) or fnmatch.fnmatch(cand.lower(), pat.lower()):
            return True
        # bare logical names
        if pat == cand:
            return True
    return False


def is_denied(
    tier: Tier,
    action: Action,
    denylist: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Return (denied, reason)."""
    dl = denylist if denylist is not None else load_denylist()
    candidates = [
        action.target or "",
        action.type.value,
        action.meta.get("logical", ""),
        action.meta.get("tcode", ""),
    ]
    # tcode: prefix convenience
    tcode = action.meta.get("tcode")
    if tcode:
        candidates.append(f"tcode:{tcode}")

    for rule in dl.get("global_deny") or []:
        patterns = rule.get("patterns") or []
        for c in candidates:
            if _match(patterns, c):
                return True, rule.get("reason", "Globally denied")

    tier_rules = (dl.get("tiers") or {}).get(tier.value) or {}
    if tier_rules.get("deny_all_writes") and action.type in {
        ActionType.SET_TEXT,
        ActionType.PRESS,
        ActionType.SELECT,
        ActionType.APPLY_CONFIG,
        ActionType.SET_BREAKPOINT,
        ActionType.SEND_VKEY,
    }:
        # Allow pure navigation vkeys? Still a write channel — deny in T3
        return True, tier_rules.get("reason", "Writes denied for tier")

    patterns = tier_rules.get("patterns") or []
    for c in candidates:
        if _match(patterns, c):
            return True, tier_rules.get("reason", f"Denied for {tier.value}")

    return False, ""


def assert_allowed(tier: Tier, action: Action, denylist: dict[str, Any] | None = None) -> None:
    denied, reason = is_denied(tier, action, denylist)
    if denied:
        raise PolicyViolation(reason, tier=tier.value, action=action.target or action.type.value)


def approval_scopes_for(tier: Tier, action: Action, denylist: dict[str, Any] | None = None) -> list[str]:
    """Return approval scopes that apply to this action in T2."""
    if tier != Tier.T2_SUPERVISED:
        return []
    dl = denylist if denylist is not None else load_denylist()
    tier_rules = (dl.get("tiers") or {}).get(tier.value) or {}
    scopes = tier_rules.get("approval_required") or []
    candidates = [action.target or "", action.type.value, action.meta.get("logical", "")]
    matched = []
    for scope in scopes:
        for c in candidates:
            if _match([scope], c) or scope == c:
                matched.append(scope)
    return matched
