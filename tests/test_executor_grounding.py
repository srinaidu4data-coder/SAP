from __future__ import annotations

from sapilot.act.executor import GroundedExecutor
from sapilot.connect.gui import MockGuiSession
from sapilot.policy.tier import TierContext
from sapilot.schemas import (
    Action,
    ActionType,
    GuiElement,
    ObservationStatus,
    PlannedStep,
    ScreenSnapshot,
    Tier,
)


def _session() -> MockGuiSession:
    snap = ScreenSnapshot(
        tcode="F110",
        title="F110",
        elements=GuiElement(
            id="wnd[0]",
            type="GuiMainWindow",
            children=[
                GuiElement(id="wnd[0]/usr/btnPROPOSAL", type="GuiButton", text="Proposal"),
                GuiElement(id="wnd[0]/usr/btnSTART", type="GuiButton", text="Start"),
            ],
        ),
    )
    s = MockGuiSession(screens={"F110": snap}, initial="F110")
    s.tcode = "F110"
    return s


def test_grounding_error_on_invented_id():
    ctx = TierContext(Tier.T1_SANDBOX, "100", "D")
    ex = GroundedExecutor(ctx, gui=_session())
    step = PlannedStep(
        assessment="x",
        gap="y",
        action=Action(type=ActionType.PRESS, target="wnd[0]/usr/btnDOES_NOT_EXIST"),
        justification_ref="obs:0",
        confidence=0.9,
    )
    obs = ex.execute(step)
    assert obs.status == ObservationStatus.GROUNDING_ERROR


def test_valid_press_ok():
    ctx = TierContext(Tier.T1_SANDBOX, "100", "D")
    gui = _session()
    ex = GroundedExecutor(ctx, gui=gui)
    step = PlannedStep(
        assessment="press proposal",
        gap="need proposal",
        action=Action(type=ActionType.PRESS, target="wnd[0]/usr/btnPROPOSAL", expect="proposal runs"),
        justification_ref="playbook:f110_ach",
        confidence=0.8,
    )
    obs = ex.execute(step)
    assert obs.status == ObservationStatus.OK
    assert any(h.startswith("press:") for h in gui.history)


def test_t3_denies_press():
    ctx = TierContext(Tier.T3_OBSERVE, "800", "P")
    ex = GroundedExecutor(ctx, gui=_session())
    step = PlannedStep(
        assessment="x",
        gap="y",
        action=Action(type=ActionType.PRESS, target="wnd[0]/usr/btnPROPOSAL"),
        justification_ref="obs:0",
        confidence=0.5,
    )
    obs = ex.execute(step)
    assert obs.status in {ObservationStatus.DENIED, ObservationStatus.POLICY_VIOLATION}
