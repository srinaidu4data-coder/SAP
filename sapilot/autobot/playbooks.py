"""
Deterministic skill playbooks for super-success.

Research basis:
  - SAP P2P: ME51N → ME21N → MIGO → MIRO → F110 (community + MM guides)
  - SAP OTC: VA01 → VL01N → VL02N(PGI) → VF01 → F-28
  - Prefer multi-table readiness checks before GUI
  - Prefer BAPI when available; twin invent when blocked
  - Explicit success criteria published before execution
"""

from __future__ import annotations

from typing import Any

from sapilot.autobot.consultant import ABAP_MISSIONS, ALL_MISSIONS, OTC_MISSIONS, TEN_MISSIONS
from sapilot.autobot.success_engine import (
    Channel,
    MissionPlan,
    PlanStep,
    SuccessCriteria,
)
from sapilot.mission.precision import PACK_EXACT, CANON


def _pack_ready(ctx: dict[str, Any]) -> bool:
    return bool(ctx.get("pack_ready"))


def _fingerprint_ok(ctx: dict[str, Any]) -> bool:
    errs = ctx.get("exact_errors") or []
    return len(errs) == 0


def _no_tcode_pollution(ctx: dict[str, Any]) -> bool:
    return not ctx.get("pollution")


def _table_count_at_least(table: str, n: int = 1):
    def _check(ctx: dict[str, Any]) -> bool:
        counts = ctx.get("table_counts") or {}
        return int(counts.get(table) or 0) >= n

    return _check


def build_mission_plan(mission: dict[str, Any]) -> MissionPlan:
    """
    Build a super-success plan for one consultant mission.

    Standard playbook (every mission):
      1. gather multi-table pack (knowledge)
      2. remediate / invent if not ready (twin)
      3. re-gather + exact fingerprint verify
      4. safe GUI navigate (optional channel)
      5. final verify criteria
    """
    mid = mission["id"]
    pack = mission["pack"]
    tcode = mission.get("tcode") or ""
    remediate = mission.get("remediate")

    steps: list[PlanStep] = [
        PlanStep(
            id=f"{mid}_gather1",
            action="gather",
            params={"pack": pack},
            channel=Channel.KNOWLEDGE,
            max_attempts=2,
        ),
    ]
    if remediate:
        steps.append(
            PlanStep(
                id=f"{mid}_remediate",
                action="remediate",
                params={"kind": remediate, "pack": pack},
                channel=Channel.TWIN,
                max_attempts=2,
            )
        )
        steps.append(
            PlanStep(
                id=f"{mid}_gather2",
                action="gather",
                params={"pack": pack},
                channel=Channel.KNOWLEDGE,
                max_attempts=2,
            )
        )
    else:
        # Still allow invent recovery path via engine if gather not ready
        steps.append(
            PlanStep(
                id=f"{mid}_ensure_ready",
                action="ensure_ready",
                params={"pack": pack, "process": "PTP" if mid.startswith("S") else "OTC"},
                channel=Channel.TWIN,
                max_attempts=2,
            )
        )
        steps.append(
            PlanStep(
                id=f"{mid}_gather2",
                action="gather",
                params={"pack": pack},
                channel=Channel.KNOWLEDGE,
                max_attempts=2,
            )
        )

    steps.append(
        PlanStep(
            id=f"{mid}_fingerprint",
            action="fingerprint",
            params={"pack": pack},
            channel=Channel.KNOWLEDGE,
            max_attempts=1,
        )
    )
    steps.append(
        PlanStep(
            id=f"{mid}_navigate",
            action="navigate",
            params={"mission_id": mid, "tcode": tcode},
            channel=Channel.GUI,
            max_attempts=2,
        )
    )
    steps.append(
        PlanStep(
            id=f"{mid}_final_verify",
            action="verify",
            params={"pack": pack},
            channel=Channel.KNOWLEDGE,
            max_attempts=1,
        )
    )

    criteria = [
        SuccessCriteria(
            id="pack_ready",
            description="Multi-table data pack has zero blockers",
            check=_pack_ready,
        ),
        SuccessCriteria(
            id="no_tcode_pollution",
            description="Business keys free of /n /o navigation garbage",
            check=_no_tcode_pollution,
        ),
        SuccessCriteria(
            id="exact_fingerprint",
            description="Critical fields match published PACK_EXACT",
            check=_fingerprint_ok,
        ),
    ]

    # Mission-specific table presence
    if pack in PACK_EXACT:
        for table in PACK_EXACT[pack]:
            criteria.append(
                SuccessCriteria(
                    id=f"table_{table}",
                    description=f"{table} has rows",
                    check=_table_count_at_least(table, 1),
                    severity="blocker",
                )
            )

    return MissionPlan(
        mission_id=mid,
        title=mission["title"],
        goal=f"Complete {mission['title']} with verified data readiness (pack={pack})",
        steps=steps,
        criteria=criteria,
        context={"pack_id": pack, "tcode": tcode, "canon": dict(CANON)},
    )


def all_super_plans() -> list[MissionPlan]:
    return [build_mission_plan(m) for m in ALL_MISSIONS]


def ptp_plans() -> list[MissionPlan]:
    return [build_mission_plan(m) for m in TEN_MISSIONS]


def otc_plans() -> list[MissionPlan]:
    return [build_mission_plan(m) for m in OTC_MISSIONS]


# High-level process playbooks (research chain integrity)
PROCESS_CHAINS: dict[str, list[str]] = {
    "PTP": [
        "S1_VENDOR",
        "S2_MATERIAL",
        "S3_INFO",
        "S4_SOURCE",
        "S5_PR",
        "S6_PO",
        "S7_GR",
        "S8_IR",
        "S9_OPEN_ITEMS",
        "S10_PAYMENT",
    ],
    "OTC": [
        "O1_CUSTOMER",
        "O2_MAT_SALES",
        "O3_CUST_MAT",
        "O4_SALES_ORG",
        "O5_SO",
        "O6_DN",
        "O7_GI",
        "O8_BILL",
        "O9_AR",
        "O10_INCOMING",
    ],
    "ABAP": [
        "A1_ST22_DUMP",
        "A2_SE38_SOURCE",
    ],
}

# Exhaustive fleet bar for Karpathy loops
FLEET_REQUIRED = {
    "ptp": 10,
    "otc": 10,
    "abap": 2,
    "total": 22,
}
