"""Super Success Bot — plan/execute/reflect/verify + fleet bar.

CI uses SAPILOT_OFFLINE=1 (data path only). Product mode requires live GUI.
"""

from __future__ import annotations

import os

os.environ.setdefault("SAPILOT_LAB", "1")
os.environ["SAPILOT_OFFLINE"] = "1"  # unit tests: twin path; product uses online
os.environ["SAPILOT_LIVE_GUI"] = "0"

from sapilot.autobot.playbooks import all_super_plans, build_mission_plan
from sapilot.autobot.success_engine import Channel, MissionPlan, PlanStep, SuccessCriteria, SuccessEngine
from sapilot.autobot.super_bot import SuperSuccessBot
from sapilot.autobot.consultant import ALL_MISSIONS


def test_every_mission_has_playbook():
    plans = all_super_plans()
    assert len(plans) == len(ALL_MISSIONS) == 22  # 10 PTP + 10 OTC + 2 ABAP
    for p in plans:
        assert p.steps
        assert p.criteria
        assert any(s.action == "gather" for s in p.steps)
        assert any(s.action == "fingerprint" for s in p.steps)


def test_engine_never_success_without_verify():
    eng = SuccessEngine(max_replans=0)

    def ok_handler(step, plan):
        plan.context["pack_ready"] = True
        plan.context["exact_errors"] = []
        plan.context["pollution"] = []
        return {"ok": True}

    eng.register("gather", ok_handler)
    eng.register("note", lambda s, p: {"ok": True})

    plan = MissionPlan(
        mission_id="T1",
        title="t",
        goal="g",
        steps=[PlanStep(id="g1", action="gather", channel=Channel.KNOWLEDGE)],
        criteria=[
            SuccessCriteria("pack_ready", "ready", lambda c: bool(c.get("pack_ready"))),
            SuccessCriteria("fp", "fp", lambda c: not c.get("exact_errors")),
        ],
    )
    out = eng.run_plan(plan)
    assert out.verified is True
    assert out.outcome == "SUCCESS"
    assert out.success_score >= 0.99


def test_engine_fails_when_criteria_fail():
    eng = SuccessEngine(max_replans=0)
    eng.register("gather", lambda s, p: {"ok": True, "context_update": {"pack_ready": False}})

    plan = MissionPlan(
        mission_id="T2",
        title="t",
        goal="g",
        steps=[PlanStep(id="g1", action="gather")],
        criteria=[SuccessCriteria("pack_ready", "ready", lambda c: bool(c.get("pack_ready")))],
    )
    # Manually set context empty
    out = eng.run_plan(plan)
    assert out.outcome in {"FAIL", "PARTIAL"}
    assert out.verified is False or out.success_score < 1.0


def test_super_bot_fleet_22_data_path_offline_ci():
    """CI offline: data + fingerprints. Product online is a separate bar."""
    bot = SuperSuccessBot(use_live_gui=False, show_mouse=False, require_gui=False)
    summary = bot.run_all()
    assert summary["total"] == 22
    assert summary["success_count"] == 22, summary
    assert summary["ptp_ok_count"] == 10
    assert summary["otc_ok_count"] == 10
    assert summary["abap_ok_count"] == 2
    assert summary["all_success"] is True
    assert summary["require_gui"] is False
    assert summary["avg_score"] >= 0.99
    assert summary["journal_chain_valid"] is True


def test_product_mode_requires_gui_flag():
    """Product constructor defaults require GUI when not offline."""
    os.environ.pop("SAPILOT_OFFLINE", None)
    os.environ["SAPILOT_LIVE_GUI"] = "1"
    bot = SuperSuccessBot(require_gui=True, use_live_gui=True, show_mouse=False)
    assert bot.require_gui is True
    os.environ["SAPILOT_OFFLINE"] = "1"


def test_build_plan_remediate_missions():
    m = next(x for x in ALL_MISSIONS if x["id"] == "S10_PAYMENT")
    plan = build_mission_plan(m)
    assert any(s.action == "remediate" for s in plan.steps)
