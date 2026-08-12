"""Action schema validators."""

from __future__ import annotations

from sapilot.exceptions import GroundingError
from sapilot.schemas import Action, ActionType, PlannedStep, ScreenSnapshot

GUI_ACTIONS = {
    ActionType.SET_TEXT,
    ActionType.PRESS,
    ActionType.SELECT,
    ActionType.SET_FOCUS,
    ActionType.SEND_VKEY,
}


def validate_planned_step(step: PlannedStep, screen: ScreenSnapshot | None) -> None:
    action = step.action
    if not step.justification_ref:
        raise ValueError("justification_ref required")
    if action.type in GUI_ACTIONS and action.type != ActionType.SEND_VKEY:
        if screen is None:
            raise GroundingError("No screen snapshot for GUI action")
        if not action.target or not screen.has_element(action.target):
            raise GroundingError(
                f"target '{action.target}' not in current screen snapshot (GROUNDING_ERROR)"
            )
    if action.type == ActionType.SEND_VKEY:
        # target may be vkey number in value
        if action.value == "" and action.target == "":
            raise ValueError("sendVKey requires value or target vkey")
