"""
Consultant loop: goal → process map → knowledge → SAP GUI → AI only when stuck.

This is the product path for "operate SAP GUI like a functional consultant"
on an arbitrary process (Treasury, PTP, a tcode nobody catalogued).
It is not a playbook runner.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sapilot.brain.router import ModelRouter, Role
from sapilot.exceptions import ApprovalRequired, PolicyViolation
from sapilot.policy.guard import authorize_write, bind_write_context, is_lab_mode
from sapilot.policy.tier import TierContext
from sapilot.report.journal import RunJournal
from sapilot.schemas import Tier
from sapilot.security.redaction import RedactionGate

log = logging.getLogger(__name__)

ALLOWED_KINDS = frozenset(
    {
        "read_table",
        "browse_table",
        "goto",
        "click",
        "double_click",
        "type",
        "key",
        "fill",
        "back",
        "screenshot",
        "se38",
        "save",
        "post",
        "inspect",
        "done",
        "fail",
    }
)
WRITE_KINDS = frozenset({"save", "post", "fill", "type", "se38"})

_SEED_TABLES: dict[str, list[dict[str, str]]] = {
    "treasur": [
        {"table": "T001", "why": "company codes"},
        {"table": "T012", "why": "house banks"},
        {"table": "T012K", "why": "house bank accounts"},
        {"table": "TZPA", "why": "TRM product types"},
        {"table": "VTBFHA", "why": "financial transactions"},
    ],
    "ptp": [
        {"table": "LFA1", "why": "vendor master"},
        {"table": "MARA", "why": "material"},
        {"table": "T001W", "why": "plants"},
        {"table": "EKKO", "why": "purchasing documents"},
    ],
    "otc": [
        {"table": "KNA1", "why": "customers"},
        {"table": "MVKE", "why": "material sales"},
        {"table": "VBAK", "why": "sales orders"},
    ],
    "payment": [
        {"table": "T042", "why": "payment program company data"},
        {"table": "T042Z", "why": "payment methods"},
        {"table": "REGUH", "why": "payment run headers"},
    ],
}


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[1] / "brain" / "prompts" / "consult.md"
    return path.read_text(encoding="utf-8")


@dataclass
class PlannedStep:
    id: str
    kind: str
    tcode: str = ""
    table: str = ""
    program: str = ""
    text: str = ""
    key: str = ""
    rx: float | None = None
    ry: float | None = None
    fields: list[str] = field(default_factory=list)
    why: str = ""
    write: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessPlan:
    process: str
    assessment: str
    tables: list[dict[str, Any]]
    master_data: list[dict[str, Any]]
    steps: list[PlannedStep]
    config_may_change: bool = False
    seed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "process": self.process,
            "assessment": self.assessment,
            "tables": self.tables,
            "master_data": self.master_data,
            "steps": [s.to_dict() for s in self.steps],
            "config_may_change": self.config_may_change,
            "seed": self.seed,
        }


@dataclass
class StepResult:
    id: str
    kind: str
    ok: bool
    detail: str = ""
    data: Any = None
    shot: str | None = None


@dataclass
class ConsultResult:
    goal: str
    outcome: str
    plan: ProcessPlan
    knowledge: dict[str, Any]
    steps: list[StepResult]
    journal: str
    shots: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "outcome": self.outcome,
            "plan": self.plan.to_dict(),
            "knowledge": self.knowledge,
            "steps": [asdict(s) for s in self.steps],
            "journal": self.journal,
            "shots": self.shots,
            "error": self.error,
        }


def seed_plan(goal: str) -> ProcessPlan:
    """Keyword seed used only when no API key is configured. Not a click script."""
    g = (goal or "").lower()
    key = next((k for k in _SEED_TABLES if k in g), "")
    tables = list(_SEED_TABLES.get(key) or [{"table": "T000", "why": "clients"}])
    steps = [
        PlannedStep(
            id=str(i + 1),
            kind="read_table",
            table=t["table"],
            why=t["why"],
        )
        for i, t in enumerate(tables)
    ]
    steps.append(
        PlannedStep(
            id=str(len(steps) + 1),
            kind="inspect",
            why="No API key — open SE16N so a human/LLM can continue from real rows.",
        )
    )
    if "se16" not in g:
        steps.insert(
            len(steps) - 1,
            PlannedStep(
                id="gui-se16n",
                kind="goto",
                tcode="SE16N",
                why="Land on table browse if RFC is empty.",
            ),
        )
    return ProcessPlan(
        process=key.upper() or "generic",
        assessment=(
            "No live model key; using a consultant seed of tables only. "
            "Set OPENAI_API_KEY or XAI_API_KEY for a real process map."
        ),
        tables=tables,
        master_data=[],
        steps=steps,
        seed=True,
    )


def _as_str_list(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    return [str(x) for x in raw if x]


def parse_plan(payload: dict[str, Any], *, seed: bool = False) -> ProcessPlan:
    steps: list[PlannedStep] = []
    for i, raw in enumerate(payload.get("steps") or []):
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in ALLOWED_KINDS:
            continue
        write = bool(raw.get("write")) or kind in WRITE_KINDS
        rx = raw.get("rx")
        ry = raw.get("ry")
        steps.append(
            PlannedStep(
                id=str(raw.get("id") or i + 1),
                kind=kind,
                tcode=str(raw.get("tcode") or "").strip().upper(),
                table=str(raw.get("table") or "").strip().upper(),
                program=str(raw.get("program") or "").strip().upper(),
                text=str(raw.get("text") or ""),
                key=str(raw.get("key") or "").strip().upper(),
                rx=float(rx) if rx is not None and rx != "" else None,
                ry=float(ry) if ry is not None and ry != "" else None,
                fields=_as_str_list(raw.get("fields")),
                why=str(raw.get("why") or ""),
                write=write,
            )
        )
    tables = [t for t in (payload.get("tables") or []) if isinstance(t, dict)]
    master = [m for m in (payload.get("master_data") or []) if isinstance(m, dict)]
    return ProcessPlan(
        process=str(payload.get("process") or "unknown"),
        assessment=str(payload.get("assessment") or ""),
        tables=tables,
        master_data=master,
        steps=steps,
        config_may_change=bool(payload.get("config_may_change")),
        seed=seed,
    )


def _loads_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                return obj if isinstance(obj, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


class ConsultLoop:
    def __init__(
        self,
        *,
        rfc: Any | None = None,
        journal: RunJournal | None = None,
        router: ModelRouter | None = None,
        shot_dir: str | None = None,
        dry_run: bool = False,
        max_steps: int = 30,
        max_llm: int = 8,
        approval_token: str | None = None,
    ) -> None:
        self.rfc = rfc
        self.journal = journal or RunJournal()
        self.redaction = RedactionGate()
        self.router = router or ModelRouter(self.redaction)
        self.shot_dir = shot_dir or str(self.journal.dir / "shots")
        Path(self.shot_dir).mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self.max_steps = max_steps
        self.max_llm = max_llm
        self.approval_token = approval_token or os.environ.get("SAPILOT_APPROVAL_TOKEN")
        self.knowledge: dict[str, Any] = {}
        self._op: Any = None
        self._hwnd: Any = None
        self._llm_used = 0
        self._bind_policy()

    def _bind_policy(self) -> None:
        tier = Tier.T1_SANDBOX if is_lab_mode() else Tier.T3_OBSERVE
        bind_write_context(
            TierContext(
                tier,
                os.environ.get("SAPILOT_CLIENT", "100"),
                "D" if is_lab_mode() else "P",
            ),
            approval_token=self.approval_token,
            source="consult",
        )

    def plan(self, goal: str) -> ProcessPlan:
        user = json.dumps(
            {
                "goal": goal,
                "rfc_available": self.rfc is not None,
                "dry_run": self.dry_run,
            },
            ensure_ascii=False,
        )
        try:
            raw = self.router.complete(Role.PLANNING, _prompt_text(), user, json_mode=True)
        except Exception as e:
            log.warning("planner unavailable (%s); using table seed", type(e).__name__)
            plan = seed_plan(goal)
            plan.assessment = (
                "Planner unavailable; using a consultant seed of tables only. "
                "Fix OPENAI_API_KEY / XAI_API_KEY for a live process map."
            )
            self.journal.append(
                "consult_plan_seed", {**plan.to_dict(), "error": type(e).__name__}
            )
            return plan
        payload = _loads_json(raw)
        kinds = {str(s.get("kind") or "") for s in (payload.get("steps") or []) if isinstance(s, dict)}
        if not payload or payload.get("action", {}).get("type") == "escalate" or not kinds:
            plan = seed_plan(goal)
            self.journal.append("consult_plan_seed", plan.to_dict())
            return plan
        plan = parse_plan(payload)
        if not plan.steps:
            plan = seed_plan(goal)
        self.journal.append("consult_plan", self.redaction.redact_payload(plan.to_dict()))
        return plan

    def stuck_plan(self, goal: str, reason: str, last: StepResult | None) -> ProcessPlan:
        if self._llm_used >= self.max_llm:
            return ProcessPlan(
                process="stuck",
                assessment="LLM budget exhausted",
                tables=[],
                master_data=[],
                steps=[
                    PlannedStep(
                        id="fail",
                        kind="fail",
                        why=f"max_llm={self.max_llm}; last: {reason}",
                    )
                ],
            )
        self._llm_used += 1
        user = json.dumps(
            {
                "mode": "stuck",
                "goal": goal,
                "reason": reason,
                "last_step": asdict(last) if last else None,
                "knowledge_keys": list(self.knowledge)[:40],
                "knowledge_preview": {
                    k: (v[:3] if isinstance(v, list) else v)
                    for k, v in list(self.knowledge.items())[:8]
                },
            },
            default=str,
            ensure_ascii=False,
        )[:12000]
        try:
            raw = self.router.complete(
                Role.ERROR_DIAGNOSIS,
                _prompt_text() + "\n\nYou are recovering from a stuck step.",
                user,
                json_mode=True,
            )
        except Exception as e:
            log.warning("stuck planner unavailable (%s)", type(e).__name__)
            return ProcessPlan(
                process="stuck",
                assessment="model call failed",
                tables=[],
                master_data=[],
                steps=[
                    PlannedStep(
                        id="fail",
                        kind="fail",
                        why=f"{reason}; llm: {type(e).__name__}",
                    )
                ],
            )
        payload = _loads_json(raw)
        plan = parse_plan(payload)
        if not plan.steps:
            plan.steps = [
                PlannedStep(id="fail", kind="fail", why=reason or "stuck, no recovery")
            ]
        self.journal.append(
            "consult_stuck",
            self.redaction.redact_payload({"reason": reason, "plan": plan.to_dict()}),
        )
        return plan

    def run(self, goal: str) -> ConsultResult:
        self.journal.append("consult_start", {"goal": goal, "dry_run": self.dry_run})
        plan = self.plan(goal)
        results: list[StepResult] = []
        shots: list[str] = []
        outcome = "RUNNING"
        error = ""
        queue = list(plan.steps)
        n = 0
        try:
            while queue and n < self.max_steps:
                step = queue.pop(0)
                n += 1
                if step.kind == "done":
                    results.append(StepResult(step.id, step.kind, True, step.why))
                    outcome = "DONE"
                    break
                if step.kind == "fail":
                    results.append(StepResult(step.id, step.kind, False, step.why))
                    outcome = "FAILED"
                    error = step.why
                    break
                try:
                    res = self._execute(step)
                except (PolicyViolation, ApprovalRequired) as e:
                    res = StepResult(step.id, step.kind, False, f"policy: {e}")
                    results.append(res)
                    outcome = "BLOCKED"
                    error = str(e)
                    break
                except Exception as e:
                    res = StepResult(step.id, step.kind, False, str(e)[:300])
                    results.append(res)
                    if self.dry_run:
                        outcome = "FAILED"
                        error = str(e)
                        break
                    rec = self.stuck_plan(goal, str(e), res)
                    queue = list(rec.steps) + queue
                    continue
                results.append(res)
                if res.shot:
                    shots.append(res.shot)
                if not res.ok and not self.dry_run:
                    rec = self.stuck_plan(goal, res.detail, res)
                    queue = list(rec.steps) + queue
            else:
                if outcome == "RUNNING":
                    outcome = "BUDGET" if n >= self.max_steps else "DONE"
        finally:
            self.journal.append(
                "consult_end",
                {"outcome": outcome, "steps": n, "error": error[:200]},
            )
        return ConsultResult(
            goal=goal,
            outcome=outcome,
            plan=plan,
            knowledge=self.knowledge,
            steps=results,
            journal=str(self.journal.path),
            shots=shots,
            error=error,
        )

    def _execute(self, step: PlannedStep) -> StepResult:
        if step.kind == "read_table":
            return self._read_table(step)
        if step.kind == "browse_table":
            return self._browse_table(step)
        if step.kind == "inspect":
            shot = self._screenshot(f"inspect_{step.id}")
            return StepResult(step.id, step.kind, True, step.why, shot=shot)
        if step.kind == "screenshot":
            shot = self._screenshot(f"shot_{step.id}")
            return StepResult(step.id, step.kind, True, "screenshot", shot=shot)
        if self.dry_run:
            return StepResult(step.id, step.kind, True, f"dry-run skipped {step.kind}")
        if step.kind == "goto":
            return self._goto(step)
        if step.kind == "se38":
            return self._se38(step)
        if step.kind == "back":
            self._hwnd_session().send_key("F3")
            time.sleep(0.4)
            return StepResult(step.id, step.kind, True, "F3")
        if step.kind == "key":
            authorize_write("send_vkey", target=step.key or "key", tcode=step.tcode)
            self._hwnd_session().send_key(step.key or step.text or "ENTER")
            return StepResult(step.id, step.kind, True, step.key or "ENTER")
        if step.kind in {"click", "double_click"}:
            return self._click(step)
        if step.kind == "type":
            authorize_write("set_text", target="gui_field", value=step.text, tcode=step.tcode)
            self._hwnd_session().type_text(step.text, clear=True)
            return StepResult(step.id, step.kind, True, "typed")
        if step.kind in {"save", "post"}:
            authorize_write(
                "press",
                target=f"btn{step.kind.capitalize()}",
                tcode=step.tcode,
                logical=step.kind,
            )
            self._hwnd_session().send_key("ENTER" if step.kind == "save" else "F8")
            shot = self._screenshot(step.kind)
            return StepResult(step.id, step.kind, True, step.kind, shot=shot)
        return StepResult(step.id, step.kind, False, f"unhandled kind {step.kind}")

    def _read_table(self, step: PlannedStep) -> StepResult:
        table = step.table
        if not table:
            return StepResult(step.id, step.kind, False, "read_table missing table")
        if self.rfc is not None:
            try:
                rows = self.rfc.read_table(
                    table, fields=step.fields or None, rowcount=25
                )
                self.knowledge[table] = rows
                self.journal.append(
                    "consult_table",
                    self.redaction.redact_payload(
                        {"table": table, "rows": len(rows), "channel": "rfc"}
                    ),
                )
                return StepResult(
                    step.id,
                    step.kind,
                    True,
                    f"{table}: {len(rows)} rows via RFC",
                    data={"table": table, "count": len(rows), "sample": rows[:5]},
                )
            except Exception as e:
                log.info("RFC read %s failed: %s", table, e)
                if self.dry_run:
                    return StepResult(step.id, step.kind, False, f"RFC {table}: {e}")
        if self.dry_run:
            return StepResult(step.id, step.kind, True, f"dry-run no RFC for {table}")
        return self._browse_table(step)

    def _browse_table(self, step: PlannedStep) -> StepResult:
        table = step.table
        if not table:
            return StepResult(step.id, step.kind, False, "browse_table missing table")
        authorize_write("start_transaction", tcode="SE16N")
        from sapilot.autobot.vision_operator import Op, open_table_browse

        op = self._vision_op()
        shot = open_table_browse(op, table, shot_name=f"se16n_{table}")
        self.knowledge.setdefault(table, {"channel": "se16n", "shot": shot})
        return StepResult(
            step.id, step.kind, True, f"{table} via SE16N", shot=shot
        )

    def _goto(self, step: PlannedStep) -> StepResult:
        tcode = step.tcode
        if not tcode:
            return StepResult(step.id, step.kind, False, "goto missing tcode")
        authorize_write("start_transaction", tcode=tcode)
        self._hwnd_session().start_transaction(tcode)
        shot = self._screenshot(f"goto_{tcode}")
        return StepResult(step.id, step.kind, True, f"/n{tcode}", shot=shot)

    def _se38(self, step: PlannedStep) -> StepResult:
        program = step.program or step.text
        if not program:
            return StepResult(step.id, step.kind, False, "se38 missing program")
        authorize_write("start_transaction", tcode="SE38")
        sess = self._hwnd_session()
        sess.start_transaction("SE38")
        time.sleep(0.4)
        sess.type_text(program, clear=True)
        shot = self._screenshot(f"se38_{program}")
        return StepResult(
            step.id,
            step.kind,
            True,
            f"SE38 {program} entered (not executed — execute is a write)",
            shot=shot,
        )

    def _click(self, step: PlannedStep) -> StepResult:
        if step.rx is None or step.ry is None:
            return StepResult(step.id, step.kind, False, "click needs rx, ry")
        op = self._vision_op()
        if step.kind == "double_click":
            op.double_click(step.rx, step.ry)
        else:
            op.click(step.rx, step.ry)
        return StepResult(step.id, step.kind, True, f"{step.rx},{step.ry}")

    def _hwnd_session(self) -> Any:
        from sapilot.connect.hwnd_input import bind_session

        if self._hwnd is None:
            self._hwnd = bind_session()
        return self._hwnd

    def _vision_op(self) -> Any:
        if self._op is None:
            from sapilot.autobot.vision_operator import Op

            hwnd = self._hwnd_session().hwnd
            self._op = Op.for_session(self.shot_dir, hwnd=hwnd)
        return self._op

    def _screenshot(self, name: str) -> str | None:
        if self.dry_run:
            return None
        try:
            return self._vision_op().screenshot(name)
        except Exception as e:
            log.info("screenshot skipped: %s", e)
            return None
