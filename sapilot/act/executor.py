"""Grounded executor — validates then executes; rejects ungrounded / denied actions."""

from __future__ import annotations

import logging
from typing import Any

from sapilot.act.actions import GUI_ACTIONS, validate_planned_step
from sapilot.connect.gui import GuiSessionBase, MockGuiSession
from sapilot.connect.rfc import RfcClientBase
from sapilot.exceptions import GroundingError, PolicyViolation
from sapilot.policy.approval import ApprovalGate
from sapilot.policy.denylist import approval_scopes_for, assert_allowed
from sapilot.policy.tier import TierContext
from sapilot.schemas import (
    Action,
    ActionType,
    Observation,
    ObservationStatus,
    PlannedStep,
    ScreenSnapshot,
)

log = logging.getLogger(__name__)


class GroundedExecutor:
    def __init__(
        self,
        tier_ctx: TierContext,
        gui: GuiSessionBase | None = None,
        rfc: RfcClientBase | None = None,
        approval: ApprovalGate | None = None,
        approval_token: str | None = None,
    ):
        self.tier_ctx = tier_ctx
        self.gui = gui
        self.rfc = rfc
        self.approval = approval or ApprovalGate()
        self.approval_token = approval_token
        self.last_screen: ScreenSnapshot | None = None

    def observe_screen(self) -> ScreenSnapshot | None:
        if self.gui is None:
            return None
        self.last_screen = self.gui.snapshot()
        return self.last_screen

    def execute(self, step: PlannedStep) -> Observation:
        action = step.action
        screen = self.last_screen
        if action.type in GUI_ACTIONS and self.gui is not None:
            screen = self.observe_screen()

        # 1) Grounding + schema
        try:
            validate_planned_step(step, screen)
        except GroundingError as e:
            return Observation(
                status=ObservationStatus.GROUNDING_ERROR,
                message=str(e),
                screen=screen,
            )
        except ValueError as e:
            return Observation(
                status=ObservationStatus.GROUNDING_ERROR,
                message=str(e),
                screen=screen,
            )

        # 2) Denylist — HARD FAIL (POLICY_VIOLATION), never soft continue
        try:
            assert_allowed(self.tier_ctx.tier, action)
        except PolicyViolation as e:
            return Observation(
                status=ObservationStatus.POLICY_VIOLATION,
                message=str(e),
                policy_reason=e.reason or "denylist",
                screen=screen,
            )

        # 3) Tier capabilities + approval
        try:
            self._check_capability(action)
            for scope in approval_scopes_for(self.tier_ctx.tier, action):
                self.approval.require(
                    self.tier_ctx.tier,
                    scope,
                    self.approval_token,
                    capability_needs_approval=True,
                )
        except PolicyViolation as e:
            return Observation(
                status=ObservationStatus.POLICY_VIOLATION,
                message=str(e),
                policy_reason=e.reason,
                screen=screen,
            )
        except Exception as e:
            from sapilot.exceptions import ApprovalRequired

            if isinstance(e, ApprovalRequired):
                return Observation(
                    status=ObservationStatus.DENIED,
                    message=str(e),
                    policy_reason="approval_required",
                    screen=screen,
                )
            raise

        # 4) Act
        try:
            data = self._dispatch(action)
        except PolicyViolation as e:
            return Observation(
                status=ObservationStatus.POLICY_VIOLATION,
                message=str(e),
                policy_reason=getattr(e, "reason", None) or "policy",
                screen=self.observe_screen() if self.gui else screen,
            )
        except Exception as e:
            log.exception("Action failed")
            return Observation(
                status=ObservationStatus.SAP_ERROR,
                message=str(e),
                screen=self.observe_screen() if self.gui else screen,
            )

        new_screen = self.observe_screen() if self.gui else screen
        if action.type == ActionType.ESCALATE:
            return Observation(
                status=ObservationStatus.ESCALATED,
                message=action.value or step.assessment,
                screen=new_screen,
                data=data,
            )
        if action.type == ActionType.DONE:
            return Observation(
                status=ObservationStatus.DONE,
                message=action.value or "done",
                screen=new_screen,
                data=data,
            )
        return Observation(
            status=ObservationStatus.OK,
            message=f"executed {action.type.value}",
            screen=new_screen,
            data=data,
        )

    def _check_capability(self, action: Action) -> None:
        mapping = {
            ActionType.APPLY_CONFIG: "apply_config",
            ActionType.PROPOSE_CONFIG: "propose_config",
            ActionType.SET_BREAKPOINT: "debug",
            ActionType.READ_VARIABLES: "debug",
            ActionType.PRESS: "gui_write",
            ActionType.SET_TEXT: "gui_write",
            ActionType.SELECT: "gui_write",
            ActionType.SEND_VKEY: "gui_write",
        }
        logical = action.meta.get("logical", "")
        if logical in {"f110.payment_run", "f110.start_immediately"}:
            self.tier_ctx.require("payment_run", action=logical)
            return
        if logical == "f110.payment_medium":
            self.tier_ctx.require("payment_medium", action=logical)
            return
        cap = mapping.get(action.type)
        if cap:
            # T3: even gui_write blocked
            self.tier_ctx.require(cap, action=action.type.value)

    def _dispatch(self, action: Action) -> dict[str, Any]:
        if action.type in {
            ActionType.READ_TABLE,
            ActionType.READ_CONFIG,
            ActionType.RESOLVE_MESSAGE,
            ActionType.CHECK_AUTH,
            ActionType.VERIFY,
            ActionType.PROPOSE_CONFIG,
            ActionType.ESCALATE,
            ActionType.DONE,
        }:
            return self._knowledge_or_meta(action)

        if self.gui is None:
            raise RuntimeError("No GUI session for action")

        if action.type == ActionType.SET_TEXT:
            # Mission-critical choke-point: never put /nTCODE into data fields
            target_l = (action.target or "").lower()
            val = (action.value or "").strip()
            is_okcd = "okcd" in target_l or "ok_code" in target_l
            if not is_okcd and val:
                from sapilot.mission.precision import (
                    MissionAbort,
                    assert_never_tcode_in_data_field,
                    is_tcode_command,
                )

                try:
                    assert_never_tcode_in_data_field(action.target or "", val)
                except MissionAbort as e:
                    raise PolicyViolation("tcode_in_data_field", action=str(e)) from e
                if is_tcode_command(val):
                    raise PolicyViolation(
                        "tcode_in_data_field",
                        action=(
                            f"PRECISION ABORT: refused tcode-like value {val!r} "
                            f"in non-okcd field {action.target!r}"
                        ),
                    )

            el = self.gui.find_by_id(action.target)
            mouse_hit = False
            try:
                from sapilot.connect.mouse import click_sap_component, mouse_enabled

                if mouse_enabled() and not isinstance(self.gui, MockGuiSession):
                    mouse_hit = click_sap_component(el)
            except Exception:
                pass
            if hasattr(el, "text"):
                el.text = action.value
            else:
                el.Text = action.value
            result: dict[str, Any] = {
                "set": action.target,
                "value": action.value,
                "mouse": mouse_hit,
            }
            # Auto-navigate when command field gets a bare tcode (models often forget Enter)
            if is_okcd and val:
                tcode = val[2:] if val.lower().startswith("/n") else val
                if tcode and len(tcode) <= 20 and " " not in tcode:
                    try:
                        self.gui.start_transaction(tcode)
                        result["started_transaction"] = tcode.upper()
                        result["auto_enter"] = True
                    except Exception as e:
                        result["auto_enter_error"] = str(e)
            return result
        if action.type == ActionType.SEND_VKEY:
            vkey = int(action.value or action.target or "0")
            # If Enter after OK-code with a transaction, start it (mock + live pattern)
            if vkey == 0 and hasattr(self.gui, "values"):
                ok_val = ""
                for k, v in list(getattr(self.gui, "values", {}).items()):
                    if "okcd" in k.lower():
                        ok_val = str(v).strip()
                if ok_val and len(ok_val) <= 20 and not ok_val.startswith("/"):
                    # bare tcode in command field
                    try:
                        self.gui.start_transaction(ok_val)
                        return {"vkey": vkey, "started_transaction": ok_val.upper()}
                    except Exception:
                        pass
            self.gui.send_vkey(vkey)
            return {"vkey": vkey}
        if action.type == ActionType.PRESS:
            el = self.gui.find_by_id(action.target)
            mouse_hit = False
            try:
                from sapilot.connect.mouse import click_sap_component, mouse_enabled

                if mouse_enabled() and not isinstance(self.gui, MockGuiSession):
                    mouse_hit = click_sap_component(el)
            except Exception:
                pass
            if isinstance(self.gui, MockGuiSession):
                self.gui.press(action.target)
            else:
                try:
                    el.Press()
                except Exception:
                    if not mouse_hit:
                        raise
            return {"pressed": action.target, "mouse": mouse_hit}
        if action.type == ActionType.SET_FOCUS:
            el = self.gui.find_by_id(action.target)
            el.SetFocus()
            return {"focus": action.target}
        if action.type == ActionType.SELECT:
            el = self.gui.find_by_id(action.target)
            if hasattr(el, "Select"):
                el.Select()
            elif hasattr(el, "press"):
                el.press()
            return {"selected": action.target}
        if action.type == ActionType.APPLY_CONFIG:
            self.tier_ctx.require("apply_config")
            return {"applyConfig": "delegated", "target": action.target}
        if action.type == ActionType.SET_BREAKPOINT:
            self.tier_ctx.require("debug")
            return {"breakpoint": action.target, "note": "ADT path preferred"}
        if action.type == ActionType.READ_VARIABLES:
            self.tier_ctx.require("debug")
            return {"variables": {}}
        raise ValueError(f"Unsupported action type {action.type}")

    def _knowledge_or_meta(self, action: Action) -> dict[str, Any]:
        if action.type == ActionType.READ_TABLE and self.rfc is not None:
            table = action.target
            rows = self.rfc.read_table(table, rowcount=int(action.meta.get("rowcount", 100)))
            return {"table": table, "rows": rows, "count": len(rows)}
        if action.type == ActionType.CHECK_AUTH:
            # Caller should drive SU53 via GUI; here we only flag
            return {"must_run": "SU53"}
        return {"action": action.type.value, "target": action.target, "value": action.value}
