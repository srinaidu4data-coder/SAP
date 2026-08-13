"""
Single policy choke-point for ALL SAP GUI writes.

Every write path (ScenarioRunner, GuiDriver, inject, mega goto, SE16N form fill)
MUST call authorize_write() before mutating SAP. Fail closed when tier unknown.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from sapilot.exceptions import ApprovalRequired, PolicyViolation
from sapilot.policy.approval import ApprovalGate
from sapilot.policy.denylist import assert_allowed, approval_scopes_for
from sapilot.policy.tier import TierContext
from sapilot.schemas import Action, ActionType, Tier

log = logging.getLogger(__name__)

_lock = threading.RLock()
_tls = threading.local()


def is_lab_mode() -> bool:
    """Lab allows unsigned policy + default T1 when unbound. Prod fails closed to T3."""
    env = (os.environ.get("SAPILOT_ENV") or os.environ.get("SAPILOT_ENVIRONMENT") or "").lower()
    if env in {"prod", "production", "qa", "quality", "p"}:
        return False
    if os.environ.get("SAPILOT_LAB", "").strip() == "0":
        return False
    # Explicit prod flag
    if os.environ.get("SAPILOT_STRICT_POLICY", "").strip() in {"1", "true", "yes"}:
        return False
    # Default: lab if ALLOW_UNSIGNED or SAPILOT_LAB unset/1
    if os.environ.get("SAPILOT_LAB", "1").strip() in {"1", "true", "yes"}:
        return True
    if os.environ.get("SAPILOT_ALLOW_UNSIGNED_POLICY", "").strip() in {"1", "true", "yes"}:
        return True
    return False


def _op_to_action_type(op: str) -> ActionType:
    m = {
        "set_text": ActionType.SET_TEXT,
        "setText": ActionType.SET_TEXT,
        "press": ActionType.PRESS,
        "select": ActionType.SELECT,
        "send_vkey": ActionType.SEND_VKEY,
        "sendVKey": ActionType.SEND_VKEY,
        "start_transaction": ActionType.SEND_VKEY,  # navigation still gated
        "tcode": ActionType.SEND_VKEY,
        "goto": ActionType.SEND_VKEY,
        "inject": ActionType.SET_TEXT,
        "apply_config": ActionType.APPLY_CONFIG,
    }
    return m.get(op, ActionType.SET_TEXT)


@dataclass
class WriteContext:
    """Bound policy context for the current thread / run."""

    tier_ctx: TierContext
    approval_token: str | None = None
    approval: ApprovalGate = field(default_factory=ApprovalGate)
    source: str = "unbound"
    hard_fail: bool = True  # denylist always raises

    def authorize(
        self,
        op: str,
        *,
        target: str = "",
        value: str = "",
        tcode: str = "",
        logical: str = "",
        confidence: float | None = None,
    ) -> None:
        """
        Raise PolicyViolation / ApprovalRequired if write not allowed.
        Also hard-blocks tcode pollution in data fields.
        """
        # Mission-critical: never put /nTCODE into business fields
        if op in {"set_text", "setText", "inject"} and value:
            target_l = (target or "").lower()
            is_okcd = "okcd" in target_l or "ok_code" in target_l
            if not is_okcd:
                try:
                    from sapilot.mission.precision import (
                        MissionAbort,
                        assert_never_tcode_in_data_field,
                        is_tcode_command,
                    )

                    assert_never_tcode_in_data_field(target, value)
                    if is_tcode_command(value):
                        raise PolicyViolation(
                            "tcode_in_data_field",
                            tier=self.tier_ctx.tier.value,
                            action=target or op,
                        )
                except MissionAbort as e:
                    raise PolicyViolation(
                        str(e),
                        tier=self.tier_ctx.tier.value,
                        action=target or op,
                    ) from e

        action = Action(
            type=_op_to_action_type(op),
            target=target or op,
            value=value or "",
            meta={
                "logical": logical or op,
                "tcode": tcode or "",
                "source": self.source,
                "guard": True,
            },
        )

        # 1) Denylist (global + tier) — always hard raise
        assert_allowed(self.tier_ctx.tier, action)

        # 2) Capability matrix
        if op in {
            "set_text",
            "setText",
            "press",
            "select",
            "send_vkey",
            "sendVKey",
            "inject",
        }:
            # T3: zero writes
            if self.tier_ctx.tier == Tier.T3_OBSERVE:
                raise PolicyViolation(
                    "T3_OBSERVE: zero GUI writes (fail closed)",
                    tier=self.tier_ctx.tier.value,
                    action=op,
                )
            # T2: requires approval for gui_write scopes
            if self.tier_ctx.tier == Tier.T2_SUPERVISED:
                scopes = approval_scopes_for(self.tier_ctx.tier, action) or ["gui_write"]
                for scope in scopes:
                    self.approval.require(
                        self.tier_ctx.tier,
                        scope,
                        self.approval_token,
                        capability_needs_approval=True,
                        confidence=confidence,
                    )
                return
            # T1: allow with capability check, but a low-confidence grounding
            # still has to clear the confidence gate — routine-action tier
            # doesn't mean "act on a guess."
            self.tier_ctx.require("gui_write", action=op)
            if confidence is not None:
                self.approval.require(
                    self.tier_ctx.tier,
                    "gui_write",
                    self.approval_token,
                    capability_needs_approval=False,
                    confidence=confidence,
                )
            return

        if op in {"start_transaction", "tcode", "goto"}:
            if self.tier_ctx.tier == Tier.T3_OBSERVE:
                # Navigation is still a write channel — deny in T3 fail-closed
                raise PolicyViolation(
                    "T3_OBSERVE: transaction navigation denied",
                    tier=self.tier_ctx.tier.value,
                    action=tcode or op,
                )
            if self.tier_ctx.tier == Tier.T2_SUPERVISED:
                self.approval.require(
                    self.tier_ctx.tier,
                    "gui_write",
                    self.approval_token,
                    capability_needs_approval=True,
                    confidence=confidence,
                )
            elif confidence is not None:
                self.approval.require(
                    self.tier_ctx.tier,
                    "gui_write",
                    self.approval_token,
                    capability_needs_approval=False,
                    confidence=confidence,
                )
            return


def bind_write_context(
    tier_ctx: TierContext,
    *,
    approval_token: str | None = None,
    approval: ApprovalGate | None = None,
    source: str = "explicit",
) -> WriteContext:
    """Bind policy for this thread. Call at start of every live run."""
    ctx = WriteContext(
        tier_ctx=tier_ctx,
        approval_token=approval_token,
        approval=approval or ApprovalGate(),
        source=source,
    )
    _tls.ctx = ctx
    log.info("WriteGuard bound tier=%s source=%s", tier_ctx.tier.value, source)
    return ctx


def clear_write_context() -> None:
    if hasattr(_tls, "ctx"):
        del _tls.ctx


def get_write_context() -> WriteContext | None:
    return getattr(_tls, "ctx", None)


def default_write_context() -> WriteContext:
    """
    Fail-closed default:
      - lab → T1_SANDBOX
      - non-lab → T3_OBSERVE (all writes blocked until explicitly bound)
    """
    from sapilot.policy.tier import TierContext as TC

    if is_lab_mode():
        tier = Tier.T1_SANDBOX
        client = os.environ.get("SAPILOT_CLIENT", "100")
        cat = "D"
    else:
        tier = Tier.T3_OBSERVE
        client = os.environ.get("SAPILOT_CLIENT", "000")
        cat = "P"
    return WriteContext(
        tier_ctx=TC(tier, client, cat),
        source="default_lab" if is_lab_mode() else "default_fail_closed",
    )


def authorize_write(
    op: str,
    *,
    target: str = "",
    value: str = "",
    tcode: str = "",
    logical: str = "",
    confidence: float | None = None,
) -> None:
    """
    THE single choke-point. All SAP write surfaces call this.
    Raises PolicyViolation or ApprovalRequired — never soft-deny.

    `confidence`: optional grounding-confidence score in [0, 1] for the
    target this write is about to act on (see sapilot.autobot.confidence).
    Pass it whenever the target coordinate came from a model prediction
    rather than an exact SAP GUI Scripting control ID — omit it (default)
    for exact-ID writes, which need no confidence gate at all.
    """
    with _lock:
        ctx = get_write_context()
        if ctx is None:
            ctx = default_write_context()
            # Do not silently bind non-lab defaults into TLS for reuse after bind
            if is_lab_mode():
                _tls.ctx = ctx
        ctx.authorize(op, target=target, value=value, tcode=tcode, logical=logical, confidence=confidence)
