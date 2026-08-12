from __future__ import annotations

import pytest

from sapilot.exceptions import PolicyViolation
from sapilot.policy.denylist import assert_allowed, is_denied
from sapilot.policy.tier import derive_tier, load_policy, TierContext
from sapilot.schemas import Action, ActionType, Tier


def test_production_maps_to_t3():
    pol = load_policy()
    tier = derive_tier("800", "P", pol)
    assert tier == Tier.T3_OBSERVE


def test_sandbox_maps_to_t1():
    pol = load_policy()
    tier = derive_tier("100", "D", pol)
    assert tier == Tier.T1_SANDBOX


def test_cannot_override_prod_to_t1():
    pol = load_policy()
    pol = {**pol, "client_overrides": {"800": "T1_SANDBOX"}}
    with pytest.raises(PolicyViolation):
        derive_tier("800", "P", pol)


def test_start_immediately_denied_t2():
    action = Action(
        type=ActionType.PRESS,
        target="wnd[0]/usr/btnSTART",
        meta={"logical": "f110.start_immediately"},
    )
    denied, reason = is_denied(Tier.T2_SUPERVISED, action)
    assert denied
    assert reason


def test_start_allowed_pattern_still_global_safe_t1_payment():
    # T1 does not deny btnSTART via tier patterns
    action = Action(type=ActionType.PRESS, target="wnd[0]/usr/btnSTART")
    denied, _ = is_denied(Tier.T1_SANDBOX, action)
    assert not denied


def test_debugger_replace_always_denied():
    action = Action(type=ActionType.PRESS, target="debug.replace")
    with pytest.raises(PolicyViolation):
        assert_allowed(Tier.T1_SANDBOX, action)


def test_t3_cannot_write():
    ctx = TierContext(Tier.T3_OBSERVE, mandt="800", cccategory="P")
    with pytest.raises(PolicyViolation):
        ctx.require("payment_run")
