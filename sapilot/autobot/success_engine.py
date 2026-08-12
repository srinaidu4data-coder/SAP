"""
Research-backed agent success engine.

Synthesizes industry patterns for *reliable* autonomous agents (2024–2026):
  • Plan → Execute → Reflect → Verify (OpenSearch plan-execute-reflect; PDCA)
  • Never claim success without a grounded verifier (agent failure-mode research)
  • Deterministic tools first; LLM only for replan when tools exist
  • Fail closed on tool misuse; max retries then escalate (no infinite thrash)
  • Pre-action authorization (WriteGuard / policy)
  • Multi-channel cascade: knowledge (RFC/twin) → action (GUI COM) → invent (twin)

References encoded as design rules (not marketing):
  - SAP GUI Scripting: StartTransaction / okcd only (SAP Help, community)
  - Hybrid RPA when scripting blocked (UiPath AA pattern)
  - BAPI/RFC for headless create/read when available
  - Closed-loop verification after every state change
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger(__name__)


class Channel(str, Enum):
    """Execution preference order for super-success (research cascade)."""

    KNOWLEDGE = "knowledge"  # RFC_READ_TABLE / twin tables
    BAPI = "bapi"  # future / mock BAPI creates
    GUI = "gui"  # StartTransaction + field fill
    TWIN = "twin"  # invent missing data
    HUMAN = "human"  # escalate


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    RETRY = "retry"
    FAILED = "failed"
    SKIPPED = "skipped"
    ESCALATED = "escalated"


@dataclass
class SuccessCriteria:
    """Published before run — verifier must satisfy all blockers."""

    id: str
    description: str
    check: Callable[[dict[str, Any]], bool]
    severity: str = "blocker"  # blocker | warning
    evidence_key: str = ""


@dataclass
class PlanStep:
    id: str
    action: str  # gather | remediate | navigate | verify | invent | note
    params: dict[str, Any] = field(default_factory=dict)
    channel: Channel = Channel.KNOWLEDGE
    max_attempts: int = 3
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    reflections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        d["status"] = self.status.value
        d.pop("check", None)
        return d


@dataclass
class MissionPlan:
    mission_id: str
    title: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    criteria: list[SuccessCriteria] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    reflections: list[str] = field(default_factory=list)
    success_score: float = 0.0
    verified: bool = False
    outcome: str = "RUNNING"  # SUCCESS | PARTIAL | FAIL | ESCALATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "title": self.title,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "criteria": [
                {
                    "id": c.id,
                    "description": c.description,
                    "severity": c.severity,
                }
                for c in self.criteria
            ],
            "context_keys": list(self.context.keys()),
            "reflections": self.reflections,
            "success_score": self.success_score,
            "verified": self.verified,
            "outcome": self.outcome,
        }


class SuccessEngine:
    """
    Closed-loop executor: plan is fixed up front; each step is executed,
    reflected on, and verified. Success is only declared if verifiers pass.
    """

    def __init__(
        self,
        *,
        max_replans: int = 2,
        max_step_attempts: int = 3,
        on_log: Callable[[str], None] | None = None,
    ):
        self.max_replans = max_replans
        self.max_step_attempts = max_step_attempts
        self.on_log = on_log or (lambda m: log.info(m))
        self._handlers: dict[str, Callable[[PlanStep, MissionPlan], dict[str, Any]]] = {}

    def register(self, action: str, handler: Callable[[PlanStep, MissionPlan], dict[str, Any]]) -> None:
        self._handlers[action] = handler

    def say(self, msg: str) -> None:
        self.on_log(msg)

    def run_plan(self, plan: MissionPlan) -> MissionPlan:
        self.say(f"PLAN {plan.mission_id}: {len(plan.steps)} steps — goal: {plan.goal}")
        replan_count = 0

        while True:
            for step in plan.steps:
                if step.status in (StepStatus.OK, StepStatus.SKIPPED):
                    continue
                self._execute_step(step, plan)
                if step.status == StepStatus.FAILED and replan_count < self.max_replans:
                    reflection = self._reflect_failure(step, plan)
                    plan.reflections.append(reflection)
                    recovery = self._propose_recovery(step, plan)
                    if recovery:
                        self.say(f"REFLECT+REPLAN: {reflection[:120]}")
                        plan.steps.extend(recovery)
                        replan_count += 1
                        # continue loop from recovery steps
                        break
                elif step.status == StepStatus.FAILED:
                    plan.outcome = "FAIL"
                    plan.verified = False
                    self._score(plan)
                    return plan
            else:
                # all steps processed without replan break
                break

        # Final verification — never claim success without this
        plan.verified, verify_notes = self.verify(plan)
        plan.reflections.extend(verify_notes)
        self._score(plan)
        if plan.verified and plan.success_score >= 0.99:
            plan.outcome = "SUCCESS"
        elif plan.success_score >= 0.7:
            plan.outcome = "PARTIAL"
        else:
            plan.outcome = "FAIL"
        self.say(
            f"VERIFY {plan.mission_id}: verified={plan.verified} "
            f"score={plan.success_score:.2f} outcome={plan.outcome}"
        )
        return plan

    def _execute_step(self, step: PlanStep, plan: MissionPlan) -> None:
        handler = self._handlers.get(step.action)
        if not handler:
            step.status = StepStatus.FAILED
            step.error = f"No handler for action {step.action!r}"
            return

        step.status = StepStatus.RUNNING
        while step.attempts < min(step.max_attempts, self.max_step_attempts):
            step.attempts += 1
            self.say(
                f"  EXEC {step.id} ({step.action}/{step.channel.value}) "
                f"attempt {step.attempts}/{step.max_attempts}"
            )
            try:
                evidence = handler(step, plan) or {}
                step.evidence.update(evidence)
                plan.context.update(evidence.get("context_update") or {})
                # Step-level success flag from handler
                if evidence.get("ok", True) is False:
                    step.error = str(evidence.get("error") or "handler returned ok=False")
                    step.reflections.append(f"attempt {step.attempts}: {step.error}")
                    step.status = StepStatus.RETRY
                    time.sleep(0.05)
                    continue
                step.status = StepStatus.OK
                step.error = ""
                return
            except Exception as e:
                step.error = str(e)
                step.reflections.append(f"attempt {step.attempts}: {e}")
                step.status = StepStatus.RETRY
                self.say(f"  RETRY {step.id}: {e}")
                time.sleep(0.05)

        step.status = StepStatus.FAILED
        self.say(f"  FAIL {step.id}: {step.error}")

    def _reflect_failure(self, step: PlanStep, plan: MissionPlan) -> str:
        """Research: reflection adapts the plan from intermediate results."""
        return (
            f"Step {step.id} failed after {step.attempts} attempts via {step.channel.value}: "
            f"{step.error}. Prefer next channel in cascade (knowledge→gui→twin)."
        )

    def _propose_recovery(self, step: PlanStep, plan: MissionPlan) -> list[PlanStep]:
        """
        Cascade recovery (research hybrid):
          knowledge fail → twin invent → re-gather → re-verify
          gui fail → skip gui, twin already has data → re-verify
        """
        rid = f"recover_{step.id}_{int(time.time()) % 10000}"
        if step.action in {"gather", "verify", "fingerprint"} and step.channel == Channel.KNOWLEDGE:
            return [
                PlanStep(
                    id=f"{rid}_invent",
                    action="invent",
                    params=dict(step.params),
                    channel=Channel.TWIN,
                    max_attempts=1,
                ),
                PlanStep(
                    id=f"{rid}_regather",
                    action="gather",
                    params=dict(step.params),
                    channel=Channel.KNOWLEDGE,
                    max_attempts=2,
                ),
                PlanStep(
                    id=f"{rid}_refingerprint",
                    action="fingerprint",
                    params=dict(step.params),
                    channel=Channel.KNOWLEDGE,
                    max_attempts=1,
                ),
            ]
        if step.action == "navigate":
            # Product is ONLINE GUI — do NOT convert GUI failure into a soft skip-success.
            # Only note + re-verify data; mission still fails gui_online criterion when required.
            step.reflections.append(
                "GUI navigate failed — will not mark as success; online path is mandatory for product"
            )
            return [
                PlanStep(
                    id=f"{rid}_note",
                    action="note",
                    params={
                        "text": (
                            "ONLINE GUI failed. Enable sapgui/user_scripting=TRUE, "
                            "log into Vista, SAPILOT_SHOW_MOUSE=1. Twin data is support-only."
                        )
                    },
                    channel=Channel.KNOWLEDGE,
                    max_attempts=1,
                )
            ]
        if step.action == "remediate":
            return [
                PlanStep(
                    id=f"{rid}_invent",
                    action="invent",
                    params=dict(step.params),
                    channel=Channel.TWIN,
                    max_attempts=2,
                )
            ]
        return []

    def verify(self, plan: MissionPlan) -> tuple[bool, list[str]]:
        """Grounded verification — success only if all blocker criteria pass."""
        notes: list[str] = []
        blockers_ok = True
        ctx = plan.context
        for c in plan.criteria:
            try:
                ok = bool(c.check(ctx))
            except Exception as e:
                ok = False
                notes.append(f"criterion {c.id} raised: {e}")
            notes.append(f"{'PASS' if ok else 'FAIL'} {c.id}: {c.description}")
            if not ok and c.severity == "blocker":
                blockers_ok = False
        # Also require no failed steps that were mandatory
        hard_fail_steps = [
            s
            for s in plan.steps
            if s.status == StepStatus.FAILED and s.action in {"gather", "remediate", "invent", "verify"}
        ]
        if hard_fail_steps:
            blockers_ok = False
            notes.append(f"hard-fail steps: {[s.id for s in hard_fail_steps]}")
        return blockers_ok, notes

    def _score(self, plan: MissionPlan) -> None:
        """Success score 0–1: steps OK + criteria passed (research: multi-signal success)."""
        steps = [s for s in plan.steps if s.status != StepStatus.SKIPPED]
        if not steps:
            step_score = 0.0
        else:
            ok_n = sum(1 for s in steps if s.status == StepStatus.OK)
            step_score = ok_n / len(steps)

        if not plan.criteria:
            crit_score = 1.0 if plan.context.get("pack_ready") else 0.0
        else:
            passed = 0
            for c in plan.criteria:
                try:
                    if c.check(plan.context):
                        passed += 1
                except Exception:
                    pass
            crit_score = passed / len(plan.criteria)

        # Weight verification higher than mere step completion
        plan.success_score = round(0.35 * step_score + 0.65 * crit_score, 4)
        if not plan.verified and plan.outcome == "RUNNING":
            plan.verified, _ = self.verify(plan)
