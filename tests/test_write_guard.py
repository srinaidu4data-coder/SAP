"""Single write choke-point + hard-fail denylist + portable approvals + journal chain."""

from __future__ import annotations

import os

import pytest

from sapilot.exceptions import PolicyViolation
from sapilot.policy.approval import ApprovalGate
from sapilot.policy.guard import (
    authorize_write,
    bind_write_context,
    clear_write_context,
    is_lab_mode,
)
from sapilot.policy.tier import TierContext
from sapilot.report.journal import RunJournal
from sapilot.schemas import Action, ActionType, Tier


@pytest.fixture(autouse=True)
def _clean_guard():
    clear_write_context()
    yield
    clear_write_context()


def test_lab_mode_default():
    assert is_lab_mode() is True


def test_t3_blocks_set_text():
    bind_write_context(TierContext(Tier.T3_OBSERVE, "800", "P"), source="test")
    with pytest.raises(PolicyViolation):
        authorize_write("set_text", target="LIFNR", value="0000100001")


def test_t3_blocks_goto():
    bind_write_context(TierContext(Tier.T3_OBSERVE, "800", "P"), source="test")
    with pytest.raises(PolicyViolation):
        authorize_write("goto", tcode="F110", target="F110")


def test_t1_allows_set_text():
    bind_write_context(TierContext(Tier.T1_SANDBOX, "100", "D"), source="test")
    authorize_write("set_text", target="LIFNR", value="0000100001")


def test_tcode_pollution_hard_abort():
    bind_write_context(TierContext(Tier.T1_SANDBOX, "100", "D"), source="test")
    with pytest.raises(PolicyViolation):
        authorize_write("set_text", target="wnd[0]/usr/ctxtRF02K-LIFNR", value="/nF110")


def test_inject_blocks_tcode():
    bind_write_context(TierContext(Tier.T1_SANDBOX, "100", "D"), source="test")
    with pytest.raises(PolicyViolation):
        authorize_write("inject", target="LIFNR", value="/nF110")


def test_t2_requires_approval_token():
    bind_write_context(TierContext(Tier.T2_SUPERVISED, "200", "Q"), source="test")
    with pytest.raises(Exception):  # ApprovalRequired or PolicyViolation
        authorize_write("set_text", target="LIFNR", value="1")


def test_t2_with_portable_token():
    gate = ApprovalGate()
    tok = gate.issue("gui_write")
    # New gate instance — portable HMAC must still verify
    gate2 = ApprovalGate(secret=gate.secret)
    assert gate2.verify(tok.token, "gui_write")
    bind_write_context(
        TierContext(Tier.T2_SUPERVISED, "200", "Q"),
        approval_token=tok.token,
        approval=gate2,
        source="test",
    )
    authorize_write("set_text", target="LIFNR", value="0000100001")


def test_journal_hash_chain(tmp_path):
    j = RunJournal(run_id="testchain", base=tmp_path)
    j.append("a", {"x": 1})
    j.append("b", {"y": 2})
    ok, errs = j.verify_chain()
    assert ok, errs
    # tamper
    lines = j.path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"x": 1', '"x": 99')
    j.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok2, errs2 = j.verify_chain()
    assert not ok2
    assert errs2


def test_executor_denylist_is_policy_violation_not_soft_denied():
    from sapilot.act.executor import GroundedExecutor
    from sapilot.connect.gui import MockGuiSession
    from sapilot.schemas import (
        GuiElement,
        ObservationStatus,
        PlannedStep,
        ScreenSnapshot,
    )

    snap = ScreenSnapshot(
        tcode="F110",
        title="t",
        elements=GuiElement(
            id="wnd[0]",
            children=[GuiElement(id="debug.replace", type="GuiButton")],
        ),
    )
    gui = MockGuiSession({"F110": snap}, "F110")
    gui.tcode = "F110"
    ex = GroundedExecutor(TierContext(Tier.T1_SANDBOX, "100", "D"), gui=gui)
    step = PlannedStep(
        assessment="x",
        gap="y",
        action=Action(type=ActionType.PRESS, target="debug.replace"),
        justification_ref="t",
        confidence=0.9,
    )
    obs = ex.execute(step)
    assert obs.status == ObservationStatus.POLICY_VIOLATION
