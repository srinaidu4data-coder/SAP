"""Declarative success / fail / escalate predicates."""

from __future__ import annotations

from typing import Any, Callable

from sapilot.know.tables import KnowledgeTables
from sapilot.schemas import TerminalOutcome


def f110_success(tables: KnowledgeTables, laufd: str, laufi: str) -> bool:
    """REGUV present, REGUP row count > 0. Exception emptiness checked by caller if available."""
    reguv = tables.reguv(laufd, laufi)
    if not reguv:
        return False
    regup = tables.regup(laufd, laufi)
    return len(regup) > 0


def evaluate_predicates(
    context: dict[str, Any],
    *,
    success: Callable[[dict[str, Any]], bool] | None = None,
    hard_fail: Callable[[dict[str, Any]], bool] | None = None,
    escalate: Callable[[dict[str, Any]], bool] | None = None,
) -> TerminalOutcome:
    if hard_fail and hard_fail(context):
        return TerminalOutcome.HARD_FAIL
    if success and success(context):
        return TerminalOutcome.SUCCESS
    if escalate and escalate(context):
        return TerminalOutcome.ESCALATE
    return TerminalOutcome.RUNNING
