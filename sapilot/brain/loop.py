"""ReAct loop: observe → plan → critique → validate → act → verify → govern → journal."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sapilot.act.executor import GroundedExecutor
from sapilot.brain.critic import Critic
from sapilot.brain.governor import Governor
from sapilot.brain.router import ModelRouter, Role
from sapilot.exceptions import BudgetExceeded, LoopDetected, PolicyViolation
from sapilot.observe.screen import flatten_elements
from sapilot.policy.tier import TierContext, TIER_RULES_TEXT
from sapilot.report.journal import RunJournal
from sapilot.schemas import (
    Action,
    ActionType,
    ObservationStatus,
    PlannedStep,
    TerminalOutcome,
)
from sapilot.security.redaction import RedactionGate

log = logging.getLogger(__name__)


def _load_planner_prompt(tier: str, rules: str) -> str:
    path = Path(__file__).with_name("prompts") / "planner.md"
    text = path.read_text(encoding="utf-8")
    return text.replace("{{TIER}}", tier).replace("{{TIER_RULES}}", rules)


class AgentLoop:
    def __init__(
        self,
        tier_ctx: TierContext,
        executor: GroundedExecutor,
        governor: Governor,
        journal: RunJournal,
        router: ModelRouter | None = None,
        redaction: RedactionGate | None = None,
        knowledge: dict[str, Any] | None = None,
    ):
        self.tier_ctx = tier_ctx
        self.executor = executor
        self.governor = governor
        self.journal = journal
        self.redaction = redaction or RedactionGate()
        self.router = router or ModelRouter(self.redaction)
        self.critic = Critic(self.router)
        self.knowledge = knowledge or {}
        self.system_prompt = _load_planner_prompt(
            tier_ctx.tier.value, TIER_RULES_TEXT[tier_ctx.tier]
        )

    def run(self, goal: str, max_steps: int | None = None) -> TerminalOutcome:
        if max_steps is not None:
            self.governor.budget.max_steps = max_steps
        self.journal.append("run_start", {"goal": goal, "tier": self.tier_ctx.tier.value})
        outcome = TerminalOutcome.RUNNING
        try:
            while outcome == TerminalOutcome.RUNNING:
                self.governor.tick_step()
                obs = self._observe()
                self.journal.append("observe", self.redaction.redact_payload(obs))

                step = self._plan(goal, obs)
                self.journal.append("plan", self.redaction.redact_payload(step.model_dump()))

                verdict = self.critic.review(
                    step, self.tier_ctx.tier, self.executor.last_screen, goal
                )
                self.journal.append("critique", verdict.model_dump())
                if verdict.verdict.value == "BLOCK":
                    self.journal.append("blocked", {"reasons": verdict.reasons})
                    outcome = TerminalOutcome.ESCALATE
                    break

                result = self.executor.execute(step)
                self.governor.add_sap_round_trip()
                self.journal.append("action_result", self.redaction.redact_payload(result.model_dump()))

                if result.status in (
                    ObservationStatus.POLICY_VIOLATION,
                    ObservationStatus.DENIED,
                ):
                    raise PolicyViolation(
                        result.message or result.policy_reason or "denied",
                        tier=self.tier_ctx.tier.value,
                        action=step.action.target or step.action.type.value,
                    )

                state = {
                    "status": result.status.value,
                    "target": step.action.target,
                    "type": step.action.type.value,
                    "screen_title": (result.screen.title if result.screen else ""),
                }
                try:
                    self.governor.observe_state(state)
                except LoopDetected as e:
                    self.journal.append("loop", {"error": str(e)})
                    if "strategy switch" in str(e).lower() and self.governor.strategy_switches < 2:
                        continue
                    outcome = TerminalOutcome.ESCALATE
                    break

                ctx = {
                    "last_status": result.status.value,
                    "goal": goal,
                    "knowledge": self.knowledge,
                }
                if result.status == ObservationStatus.DONE:
                    outcome = TerminalOutcome.SUCCESS
                    break
                if result.status == ObservationStatus.ESCALATED:
                    outcome = TerminalOutcome.ESCALATE
                    break

                outcome = self.governor.evaluate_terminal(ctx)

        except BudgetExceeded as e:
            self.journal.append("budget_exceeded", {"error": str(e)})
            outcome = TerminalOutcome.ESCALATE
        except PolicyViolation as e:
            self.journal.append("policy_violation", {"error": str(e)})
            outcome = TerminalOutcome.HARD_FAIL
        except LoopDetected as e:
            self.journal.append("loop_terminal", {"error": str(e)})
            outcome = TerminalOutcome.ESCALATE

        self.journal.append("run_end", {"outcome": outcome.value})
        return outcome

    def _observe(self) -> dict[str, Any]:
        screen = self.executor.observe_screen()
        flat = flatten_elements(screen.elements) if screen else []
        status = ""
        if self.executor.gui is not None:
            status = self.executor.gui.status_bar_text()
        return {
            "screen": screen.model_dump(mode="json") if screen else None,
            "elements_flat": flat[:300],
            "status_bar": status,
            "budget": self.governor.budget_public(),
            "knowledge_keys": list(self.knowledge.keys()),
        }

    def _plan(self, goal: str, observation: dict[str, Any]) -> PlannedStep:
        user = json.dumps(
            {
                "goal": goal,
                "observation": observation,
                "knowledge": self.redaction.redact_payload(self.knowledge),
            },
            default=str,
        )
        raw = self.router.complete(Role.PLANNING, self.system_prompt, user)
        for entry in self.router.call_log[-1:]:
            self.governor.add_tokens(int(entry.get("tokens") or 0))
        data = json.loads(raw)
        action_data = data.get("action") or {}
        at = _parse_action_type(action_data.get("type", "escalate"))
        value = action_data.get("value", "") or ""
        target = action_data.get("target", "") or ""
        # enter / sendVKey without value → Enter
        if at == ActionType.SEND_VKEY and value == "" and (target == "" or not target.isdigit()):
            if str(action_data.get("type", "")).lower() in {"enter", "sendvkey", "vkey"} or target == "":
                value = "0"
        return PlannedStep(
            assessment=data.get("assessment", ""),
            gap=data.get("gap", ""),
            action=Action(
                type=at,
                target=target,
                value=value,
                expect=action_data.get("expect", "") or "",
                meta=action_data.get("meta") or {},
            ),
            justification_ref=data.get("justification_ref") or "model:unspecified",
            confidence=float(data.get("confidence") or 0.5),
        )


def _parse_action_type(raw: object) -> ActionType:
    """Accept setText, SET_TEXT, ActionType.SET_TEXT, etc."""
    t = str(raw or "escalate").strip()
    # strip enum-style prefixes from model output
    if "." in t:
        t = t.split(".")[-1]
    key = t.lower().replace("-", "").replace("_", "")
    aliases = {
        "settext": ActionType.SET_TEXT,
        "press": ActionType.PRESS,
        "select": ActionType.SELECT,
        "setfocus": ActionType.SET_FOCUS,
        "sendvkey": ActionType.SEND_VKEY,
        "vkey": ActionType.SEND_VKEY,
        "enter": ActionType.SEND_VKEY,  # value should be 0; executor uses value/target
        "readtable": ActionType.READ_TABLE,
        "readconfig": ActionType.READ_CONFIG,
        "resolvemessage": ActionType.RESOLVE_MESSAGE,
        "checkauth": ActionType.CHECK_AUTH,
        "setbreakpoint": ActionType.SET_BREAKPOINT,
        "readvariables": ActionType.READ_VARIABLES,
        "proposeconfig": ActionType.PROPOSE_CONFIG,
        "applyconfig": ActionType.APPLY_CONFIG,
        "verify": ActionType.VERIFY,
        "escalate": ActionType.ESCALATE,
        "done": ActionType.DONE,
    }
    if key in aliases:
        return aliases[key]
    # match enum value e.g. setText
    for a in ActionType:
        if a.value.lower().replace("_", "") == key or a.name.lower().replace("_", "") == key:
            return a
    return ActionType.ESCALATE
