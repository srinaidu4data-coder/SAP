"""Consultant operator: scoring, planning, dry-run knowledge path."""

from __future__ import annotations

from pathlib import Path

from sapilot.autobot.consult import (
    ConsultLoop,
    PlannedStep,
    parse_plan,
    seed_plan,
)
from sapilot.connect.hwnd_input import (
    ChildInfo,
    Rect,
    pick_okcd,
    score_okcd_candidate,
)
from sapilot.connect.rfc import MockRfcClient
from sapilot.report.journal import RunJournal


def _child(
    *,
    hwnd: int = 1,
    cls: str = "Edit",
    title: str = "",
    box: tuple[int, int, int, int] = (20, 10, 180, 32),
    acc: str = "",
) -> ChildInfo:
    return ChildInfo(
        hwnd=hwnd,
        class_name=cls,
        title=title,
        rect=Rect(*box),
        acc_name=acc,
    )


def test_okcd_name_match_wins():
    parent = Rect(0, 0, 1000, 800)
    child = _child(acc="Command Field")
    assert score_okcd_candidate(child, parent) >= 50
    assert pick_okcd([child], parent) is child


def test_okcd_toolbar_edit_without_name():
    parent = Rect(0, 0, 1000, 800)
    child = _child()
    picked = pick_okcd([child], parent)
    assert picked is child


def test_okcd_center_edit_fail_closed():
    parent = Rect(0, 0, 1000, 800)
    child = _child(box=(300, 400, 500, 424))
    assert pick_okcd([child], parent) is None


def test_okcd_empty_children_fail_closed():
    assert pick_okcd([], Rect(0, 0, 100, 100)) is None


def test_seed_plan_treasury_reads_tables_not_clicks():
    plan = seed_plan("run end-to-end Treasury flow")
    assert plan.seed
    kinds = {s.kind for s in plan.steps}
    assert "read_table" in kinds
    assert any(s.table == "T012" for s in plan.steps)
    assert not any(s.kind in {"save", "post"} for s in plan.steps)


def test_parse_plan_drops_unknown_kinds():
    plan = parse_plan(
        {
            "process": "X",
            "assessment": "a",
            "steps": [
                {"id": "1", "kind": "goto", "tcode": "se16n"},
                {"id": "2", "kind": "rm -rf", "tcode": "SM35"},
            ],
        }
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].tcode == "SE16N"


def test_consult_dry_run_mock_rfc(tmp_path: Path):
    rfc = MockRfcClient()
    rfc.seed("T012", [{"BUKRS": "1000", "HBKID": "CITI"}])
    rfc.seed("T001", [{"BUKRS": "1000", "BUTXT": "Demo"}])
    rfc.seed("T012K", [{"BUKRS": "1000", "HBKID": "CITI", "HKTID": "01"}])
    rfc.seed("TZPA", [{"GSART": "51A"}])
    rfc.seed("VTBFHA", [])
    class _Stub:
        def complete(self, *args, **kwargs):
            raise RuntimeError("unit test — no live model")

    loop = ConsultLoop(
        rfc=rfc,
        journal=RunJournal(base=tmp_path),
        router=_Stub(),  # type: ignore[arg-type]
        dry_run=True,
        max_steps=20,
        shot_dir=str(tmp_path / "shots"),
    )
    result = loop.run("run end-to-end Treasury")
    assert result.outcome == "DONE"
    assert result.plan.seed
    assert "T012" in result.knowledge
    assert result.knowledge["T012"][0]["HBKID"] == "CITI"
    assert not any(s.kind == "save" and s.ok and "dry-run" not in s.detail for s in result.steps)


def test_parse_write_flag_on_post():
    plan = parse_plan(
        {
            "process": "p",
            "steps": [{"id": "1", "kind": "post", "tcode": "TBB1", "why": "post flows"}],
        }
    )
    assert plan.steps[0].write is True


def test_planned_step_roundtrip():
    s = PlannedStep(id="1", kind="goto", tcode="me51n", why="pr")
    d = s.to_dict()
    assert d["tcode"] == "me51n"
    assert d["kind"] == "goto"
