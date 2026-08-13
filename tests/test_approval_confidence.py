from __future__ import annotations

import pytest

from sapilot.exceptions import ApprovalRequired
from sapilot.policy.approval import ApprovalGate
from sapilot.schemas import Tier


def _gate(tmp_path) -> ApprovalGate:
    return ApprovalGate(secret=b"test-secret-for-confidence-gate")


def test_t1_sandbox_high_confidence_needs_no_token(tmp_path):
    gate = _gate(tmp_path)
    gate.require(
        Tier.T1_SANDBOX,
        "gui_write",
        None,
        capability_needs_approval=False,
        confidence=0.95,
    )  # should not raise


def test_t1_sandbox_low_confidence_requires_token(tmp_path):
    gate = _gate(tmp_path)
    with pytest.raises(ApprovalRequired):
        gate.require(
            Tier.T1_SANDBOX,
            "gui_write",
            None,
            capability_needs_approval=False,
            confidence=0.2,
        )


def test_t1_sandbox_low_confidence_passes_with_valid_token(tmp_path):
    gate = _gate(tmp_path)
    tok = gate.issue("gui_write")
    gate.require(
        Tier.T1_SANDBOX,
        "gui_write",
        tok.token,
        capability_needs_approval=False,
        confidence=0.2,
    )  # should not raise


def test_t1_sandbox_no_confidence_supplied_is_unaffected(tmp_path):
    gate = _gate(tmp_path)
    gate.require(
        Tier.T1_SANDBOX,
        "gui_write",
        None,
        capability_needs_approval=False,
        confidence=None,
    )  # unchanged legacy behavior — no confidence signal, no gate


def test_t2_low_confidence_gates_even_without_capability_flag(tmp_path):
    gate = _gate(tmp_path)
    with pytest.raises(ApprovalRequired):
        gate.require(
            Tier.T2_SUPERVISED,
            "gui_write",
            None,
            capability_needs_approval=False,
            confidence=0.1,
        )


def test_t2_capability_flag_still_gates_regardless_of_confidence(tmp_path):
    gate = _gate(tmp_path)
    with pytest.raises(ApprovalRequired):
        gate.require(
            Tier.T2_SUPERVISED,
            "gui_write",
            None,
            capability_needs_approval=True,
            confidence=0.99,
        )
