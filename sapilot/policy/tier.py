"""Three-tier execution policy — derived from T000 + signed local policy, never from LLM."""

from __future__ import annotations

import hashlib
import hmac
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

import yaml

from sapilot.exceptions import PolicyViolation
from sapilot.schemas import Tier

F = TypeVar("F", bound=Callable[..., Any])

# Capability matrix
WRITE_CAPABILITIES = frozenset(
    {
        "gui_write",
        "post",
        "payment_run",
        "payment_medium",
        "config_write",
        "debug",
        "create_test_data",
        "apply_config",
    }
)

TIER_CAPABILITIES: dict[Tier, frozenset[str]] = {
    Tier.T1_SANDBOX: frozenset(
        {
            "read",
            "proposal",
            "dry_run",
            "gui_write",
            "post",
            "payment_run",
            "payment_medium",
            "config_write",
            "debug",
            "create_test_data",
            "apply_config",
            "propose_config",
        }
    ),
    Tier.T2_SUPERVISED: frozenset(
        {
            "read",
            "proposal",  # may require approval token
            "dry_run",
            "propose_config",
        }
    ),
    Tier.T3_OBSERVE: frozenset({"read"}),
}

TIER_RULES_TEXT = {
    Tier.T1_SANDBOX: (
        "Full autonomy: posting, config writes (SAPILOT_AUTOCFG transport only), "
        "debugging (ADT preferred; no field-value replace). Always journal diffs."
    ),
    Tier.T2_SUPERVISED: (
        "Read + proposal + dry-run. Writes require a human approval token. "
        "Config changes are proposals only. Payment run / Start Immediately blocked."
    ),
    Tier.T3_OBSERVE: (
        "Read-only. Investigate, diagnose, produce remediation plans. "
        "Zero writes, zero debug, no exceptions."
    ),
}


def _default_policy_path() -> Path:
    env = os.environ.get("SAPILOT_POLICY_PATH")
    if env:
        return Path(env)
    return Path(__file__).with_name("local_policy.yaml")


def load_policy(path: Path | None = None) -> dict[str, Any]:
    p = path or _default_policy_path()
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def verify_policy_signature(policy: dict[str, Any], secret: bytes | None = None) -> bool:
    """HMAC-SHA256 over canonical YAML body excluding `signature` field."""
    sig = (policy.get("signature") or "").strip()
    allow_unsigned = os.environ.get("SAPILOT_ALLOW_UNSIGNED_POLICY", "1") == "1"
    if not sig:
        return allow_unsigned
    body = {k: v for k, v in policy.items() if k != "signature"}
    canonical = yaml.safe_dump(body, sort_keys=True)
    key = secret or os.environ.get("SAPILOT_POLICY_HMAC_KEY", "sapilot-lab-key").encode()
    expected = hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def map_cccategory(cccategory: str | None, policy: dict[str, Any]) -> Tier:
    raw = (cccategory if cccategory is not None else "").upper()[:1] or " "
    mapping = policy.get("cccategory_map") or {}
    # YAML may have loaded blank key oddly; normalize
    normalized = {str(k).upper()[:1] if str(k).strip() else " ": v for k, v in mapping.items()}
    label = normalized.get(raw) or normalized.get(" ") or policy.get("defaults", {}).get(
        "unknown_client_tier", "T3_OBSERVE"
    )
    return Tier(label)


def derive_tier(
    mandt: str,
    cccategory: str | None,
    policy: dict[str, Any] | None = None,
    *,
    force_unsigned_ok: bool = False,
) -> Tier:
    """
    Derive execution tier.

    Rules (non-negotiable):
    1. Never accept tier from user input or LLM.
    2. Production (P / blank conservative) cannot be overridden to T1.
    3. Unsigned policy only when lab flag allows.
    """
    pol = policy if policy is not None else load_policy()
    if not force_unsigned_ok and not verify_policy_signature(pol):
        raise PolicyViolation("Local policy signature invalid or missing", tier=None)

    base = map_cccategory(cccategory, pol)
    overrides = pol.get("client_overrides") or {}
    if mandt in overrides:
        override = Tier(overrides[mandt])
        # Production never escalated to T1 via override
        if base == Tier.T3_OBSERVE and override == Tier.T1_SANDBOX:
            raise PolicyViolation(
                f"Client {mandt} maps to production/observe; cannot override to T1_SANDBOX",
                tier=str(base),
            )
        # Prefer more restrictive of base and override for safety on P
        if base == Tier.T3_OBSERVE:
            return Tier.T3_OBSERVE
        return override
    return base


class TierContext:
    """Runtime tier holder — immutable after derivation."""

    def __init__(self, tier: Tier, mandt: str, cccategory: str | None = None):
        self.tier = tier
        self.mandt = mandt
        self.cccategory = cccategory
        self.capabilities = TIER_CAPABILITIES[tier]

    def allows(self, capability: str) -> bool:
        return capability in self.capabilities

    def require(self, capability: str, action: str | None = None) -> None:
        if not self.allows(capability):
            raise PolicyViolation(
                f"Capability '{capability}' not allowed in {self.tier.value}",
                tier=self.tier.value,
                action=action,
            )

    def rules_text(self) -> str:
        return TIER_RULES_TEXT[self.tier]


def require_tier(*capabilities: str) -> Callable[[F], F]:
    """Decorator: function first arg or kw `tier_ctx: TierContext` must allow capabilities."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = kwargs.get("tier_ctx")
            if ctx is None:
                for a in args:
                    if isinstance(a, TierContext):
                        ctx = a
                        break
            if ctx is None:
                raise PolicyViolation("No TierContext provided for policy-gated call")
            for cap in capabilities:
                ctx.require(cap, action=fn.__name__)
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def tier_from_t000_row(row: dict[str, Any], policy: dict[str, Any] | None = None) -> TierContext:
    mandt = str(row.get("MANDT") or row.get("mandt") or "")
    cat = row.get("CCCATEGORY") or row.get("cccategory")
    tier = derive_tier(mandt, str(cat) if cat is not None else None, policy)
    return TierContext(tier=tier, mandt=mandt, cccategory=str(cat) if cat is not None else None)
