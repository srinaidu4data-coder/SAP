"""Governor — budgets, novelty, terminal predicates."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from sapilot.exceptions import BudgetExceeded, LoopDetected
from sapilot.schemas import BudgetState, TerminalOutcome


class Governor:
    def __init__(
        self,
        budget: BudgetState | None = None,
        novelty_window: int = 5,
        success_fn: Callable[[dict[str, Any]], bool] | None = None,
        hard_fail_fn: Callable[[dict[str, Any]], bool] | None = None,
        escalate_fn: Callable[[dict[str, Any]], bool] | None = None,
    ):
        self.budget = budget or BudgetState()
        self.novelty_window = novelty_window
        self._state_hashes: list[str] = []
        self._started = time.monotonic()
        self.success_fn = success_fn
        self.hard_fail_fn = hard_fail_fn
        self.escalate_fn = escalate_fn
        self.strategy_switches = 0

    def tick_step(self) -> None:
        self.budget.steps_used += 1
        self.budget.wall_seconds_used = time.monotonic() - self._started
        self._check_budgets()

    def add_tokens(self, n: int) -> None:
        self.budget.tokens_used += n
        self._check_budgets()

    def add_sap_round_trip(self) -> None:
        self.budget.sap_round_trips += 1
        self._check_budgets()

    def record_remediation(self, signature: str) -> None:
        c = self.budget.remediation_counts.get(signature, 0) + 1
        self.budget.remediation_counts[signature] = c
        if c > self.budget.max_remediation_per_signature:
            raise LoopDetected(
                f"Remediation attempts for {signature} exceeded "
                f"{self.budget.max_remediation_per_signature}"
            )

    def observe_state(self, state: dict[str, Any]) -> None:
        h = hashlib.sha256(
            json.dumps(state, sort_keys=True, default=str).encode()
        ).hexdigest()
        self._state_hashes.append(h)
        window = self._state_hashes[-self.novelty_window :]
        if len(window) >= self.novelty_window and len(set(window)) == 1:
            self.strategy_switches += 1
            if self.strategy_switches >= 2:
                raise LoopDetected("State hash novelty check failed after strategy switch")
            # First detection: caller should switch strategy
            raise LoopDetected("LOOP_DETECTED: force strategy switch")

    def _check_budgets(self) -> None:
        b = self.budget
        if b.steps_used > b.max_steps:
            raise BudgetExceeded(f"max_steps {b.max_steps}")
        if b.wall_seconds_used > b.max_wall_seconds:
            raise BudgetExceeded(f"max_wall_seconds {b.max_wall_seconds}")
        if b.tokens_used > b.max_tokens:
            raise BudgetExceeded(f"max_tokens {b.max_tokens}")
        if b.sap_round_trips > b.max_sap_round_trips:
            raise BudgetExceeded(f"max_sap_round_trips {b.max_sap_round_trips}")

    def evaluate_terminal(self, context: dict[str, Any]) -> TerminalOutcome:
        if self.hard_fail_fn and self.hard_fail_fn(context):
            return TerminalOutcome.HARD_FAIL
        if self.success_fn and self.success_fn(context):
            return TerminalOutcome.SUCCESS
        if self.escalate_fn and self.escalate_fn(context):
            return TerminalOutcome.ESCALATE
        return TerminalOutcome.RUNNING

    def budget_public(self) -> dict[str, Any]:
        b = self.budget
        return {
            "steps_remaining": b.remaining_steps(),
            "wall_seconds_used": round(b.wall_seconds_used, 1),
            "tokens_used": b.tokens_used,
            "sap_round_trips": b.sap_round_trips,
            "remediation_counts": dict(b.remediation_counts),
        }
