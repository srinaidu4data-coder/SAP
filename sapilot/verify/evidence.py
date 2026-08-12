"""Collect proof: table state, screenshots, run IDs."""

from __future__ import annotations

from typing import Any

from sapilot.know.tables import KnowledgeTables
from sapilot.schemas import EvidencePack, TerminalOutcome, Tier


class EvidenceCollector:
    def __init__(self, tables: KnowledgeTables | None = None):
        self.tables = tables
        self.notes: list[str] = []
        self.diffs: list = []
        self.exceptions_before: list[dict[str, Any]] = []
        self.exceptions_after: list[dict[str, Any]] = []
        self.remediation_steps = 0

    def build(
        self,
        run_id: str,
        goal: str,
        tier: Tier,
        outcome: TerminalOutcome,
        *,
        laufd: str | None = None,
        laufi: str | None = None,
        elapsed_seconds: float = 0.0,
    ) -> EvidencePack:
        reguv_status = None
        regup_count = None
        fi_docs: list[str] = []
        table_evidence: dict[str, Any] = {}
        if self.tables and laufd and laufi:
            reguv = self.tables.reguv(laufd, laufi)
            regup = self.tables.regup(laufd, laufi)
            reguh = self.tables.reguh(laufd, laufi)
            table_evidence = {"REGUV": reguv, "REGUP": regup, "REGUH": reguh}
            if reguv:
                reguv_status = reguv[0].get("STATU") or reguv[0].get("XVORL") or str(reguv[0])
            regup_count = len(regup)
            fi_docs = [r.get("BELNR", "") for r in regup if r.get("BELNR")]
        return EvidencePack(
            run_id=run_id,
            goal=goal,
            tier=tier,
            outcome=outcome,
            reguv_status=reguv_status,
            regup_count=regup_count,
            fi_documents=fi_docs,
            config_diffs=self.diffs,
            exceptions_before=self.exceptions_before,
            exceptions_after=self.exceptions_after,
            remediation_steps=self.remediation_steps,
            elapsed_seconds=elapsed_seconds,
            notes=self.notes,
            table_evidence=table_evidence,
        )
