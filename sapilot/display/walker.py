"""Drive a display cycle on live SAP GUI. Never save, post, or open create t-codes."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sapilot.display.catalog import DisplayCycle, DisplayStep, get_cycle
from sapilot.display.policy import (
    DisplayPolicyError,
    assert_display_tcode,
    is_create_screen,
    is_display_screen,
)
from sapilot.autobot.vision_operator import Op, find_popup


@dataclass
class StepResult:
    id: str
    tcode: str
    phase: str
    purpose: str
    ok: bool
    title: str = ""
    status: str = ""
    shot: str = ""
    detail: str = ""
    skipped_fill: bool = False
    create_aborted: bool = False


@dataclass
class WalkResult:
    cycle: str
    ok: bool
    started: str
    finished: str
    shot_dir: str
    keys: dict[str, str]
    steps: list[StepResult] = field(default_factory=list)
    abort_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "ok": self.ok,
            "started": self.started,
            "finished": self.finished,
            "shot_dir": self.shot_dir,
            "keys": self.keys,
            "abort_reason": self.abort_reason,
            "steps": [asdict(s) for s in self.steps],
        }


def plan(cycle_name: str) -> DisplayCycle:
    """Catalog only — no SAP."""
    cycle = get_cycle(cycle_name)
    for step in cycle.steps:
        assert_display_tcode(step.tcode)
    return cycle


def _status_text(view) -> str:
    if view is None or view.status is None:
        return ""
    return view.status.text or ""


def _dismiss_nonbusiness_dialogs(hh) -> None:
    """SAP GUI shortcut wizard is not a business create. Cancel it. Never Finish."""
    op = hh._op()
    for title in ("Shortcut", "Create New", "SAP Shortcut", "Personal Settings"):
        pop = find_popup(title, exclude=op.hwnd)
        if not pop:
            continue
        popop = Op(hwnd=pop, shot_dir=hh.shot_dir)
        # bottom-right cluster is Next/Finish; Cancel is left of that
        popop.click(0.55, 0.92, settle=0.3)


def _leave_write_screen(hh) -> None:
    """F12 / Back if we landed on a create screen. Never Save."""
    try:
        hh.key("F12", settle=0.8)
    except Exception:
        pass
    try:
        hh.key("F3", settle=0.6)
    except Exception:
        pass


def _title_matches(step: DisplayStep, title: str) -> bool:
    t = (title or "").strip()
    if not t or t.upper() == "SAP":
        return False
    if is_create_screen(t):
        return False
    expect = step.expect_in_title or ("Display",)
    low = t.lower()
    return any(tok.lower() in low for tok in expect)


def _goto_display(hh, code: str):
    """Navigate; if we land on a blank shell, start Easy Access and retry once."""
    r = hh.goto(code)
    title = hh._title()
    if hh._title_kind(title) == "shell":
        hh._leave_blank_shell()
        r = hh.goto(code)
        title = hh._title()
    return r, title


def _fill_step(hh, step: DisplayStep, keys: dict[str, str]) -> tuple[bool, str]:
    """Fill known keys. Empty key → skip that field. Never invent values."""
    filled = 0
    notes: list[str] = []
    for aliases, key_name in step.fields:
        val = (keys.get(key_name) or "").strip()
        if not val:
            notes.append(f"skip {key_name} (empty)")
            continue
        r = hh.fill_label(list(aliases), val, enter=False, side="right")
        if r.ok:
            filled += 1
            notes.append(f"fill {key_name}={val}")
        else:
            notes.append(f"miss {key_name} ({r.detail})")
    if filled and step.enter_after:
        hh.key("ENTER", settle=1.2)
    if step.execute and filled:
        hh.key("F8", settle=1.6)
    return filled > 0, "; ".join(notes)


def walk(
    cycle_name: str,
    *,
    keys: dict[str, str] | None = None,
    shot_dir: str | None = None,
    hh: Any = None,
) -> WalkResult:
    """Open every display t-code in the cycle. Abort if a write screen appears."""
    cycle = plan(cycle_name)
    merged = dict(cycle.default_keys)
    if keys:
        merged.update({k: v for k, v in keys.items() if v is not None})

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(shot_dir or f"data/runs/display_{cycle.name}_{ts}")
    root.mkdir(parents=True, exist_ok=True)

    if hh is None:
        from sapilot.autobot.operator import HumanEyesHands

        hh = HumanEyesHands(shot_dir=str(root))

    started = datetime.now(timezone.utc).isoformat()
    results: list[StepResult] = []
    abort = ""
    prev_title = ""

    for step in cycle.steps:
        try:
            code = assert_display_tcode(step.tcode)
        except DisplayPolicyError as e:
            abort = str(e)
            break

        _dismiss_nonbusiness_dialogs(hh)
        nav, title = _goto_display(hh, code)
        if not _title_matches(step, title) and hh._title_kind(title) != "shell":
            # leftover previous t-code — reset to menu and retry once
            try:
                hh.goto("SESSION_MANAGER")
            except Exception:
                pass
            nav, title = _goto_display(hh, code)

        view = hh.see(f"{step.id}_open")
        status = _status_text(view)

        if is_create_screen(title, status):
            _leave_write_screen(hh)
            rec = StepResult(
                id=step.id,
                tcode=code,
                phase=step.phase,
                purpose=step.purpose,
                ok=False,
                title=title,
                status=status,
                shot=str(view.path) if view else "",
                detail=f"WRITE SCREEN — left immediately: {title}",
                create_aborted=True,
            )
            results.append(rec)
            abort = rec.detail
            break

        filled, fill_note = _fill_step(hh, step, merged)
        title2 = hh._title()
        view2 = hh.see(f"{step.id}_after")
        status2 = _status_text(view2)

        if is_create_screen(title2, status2):
            _leave_write_screen(hh)
            rec = StepResult(
                id=step.id,
                tcode=code,
                phase=step.phase,
                purpose=step.purpose,
                ok=False,
                title=title2,
                status=status2,
                shot=str(view2.path) if view2 else "",
                detail=f"WRITE SCREEN after fill — left: {title2}",
                create_aborted=True,
            )
            results.append(rec)
            abort = rec.detail
            break

        if step.drill_label and _title_matches(step, title2 or title):
            try:
                hh.click_label([step.drill_label], side="on")
                hh.see(f"{step.id}_drill")
            except Exception:
                pass

        landed = _title_matches(step, title2) or _title_matches(step, title)
        final_title = title2 or title
        if prev_title and final_title.strip() == prev_title.strip():
            landed = False
            fill_note = (fill_note + "; ").lstrip("; ") + "title unchanged from previous step"
        rec = StepResult(
            id=step.id,
            tcode=code,
            phase=step.phase,
            purpose=step.purpose,
            ok=landed and not is_create_screen(title2),
            title=title2 or title,
            status=status2,
            shot=str(view2.path) if view2 else "",
            detail=fill_note or nav.detail,
            skipped_fill=not filled,
        )
        results.append(rec)
        prev_title = rec.title
        time.sleep(0.2)

    finished = datetime.now(timezone.utc).isoformat()
    ok = bool(results) and all(s.ok for s in results) and not abort
    out = WalkResult(
        cycle=cycle.name,
        ok=ok,
        started=started,
        finished=finished,
        shot_dir=str(root),
        keys={k: v for k, v in merged.items() if v},
        steps=results,
        abort_reason=abort,
    )
    (root / "walk.json").write_text(json.dumps(out.as_dict(), indent=2), encoding="utf-8")
    (root / "WALK.md").write_text(_markdown(cycle, out), encoding="utf-8")
    return out


def _markdown(cycle: DisplayCycle, out: WalkResult) -> str:
    lines = [
        f"# Display walk — {cycle.title}",
        "",
        f"**Cycle:** `{cycle.name}`  ",
        f"**Spine:** {cycle.spine}  ",
        f"**Mode:** display t-codes only. No create, no change, no post.  ",
        f"**Started:** {out.started}  ",
        f"**Finished:** {out.finished}  ",
        f"**OK:** {out.ok}  ",
    ]
    if out.abort_reason:
        lines.append(f"**Abort:** {out.abort_reason}  ")
    lines += ["", "## Steps", ""]
    lines.append("| # | Phase | T-code | Title | Result |")
    lines.append("|---|---|---|---|---|")
    for i, s in enumerate(out.steps, 1):
        mark = "LIVE display" if s.ok else ("ABORTED write" if s.create_aborted else "fail")
        title = (s.title or "").replace("|", "/")
        lines.append(f"| {i} | {s.phase} | {s.tcode} | {title} | {mark} |")
    lines += ["", "## Purpose (what we looked at, not what we created)", ""]
    for s in out.steps:
        lines.append(f"- **{s.tcode}** ({s.phase}): {s.purpose}")
        if s.detail:
            lines.append(f"  - {s.detail}")
        if s.shot:
            lines.append(f"  - shot: `{s.shot}`")
    lines += [
        "",
        "## Rule",
        "",
        "Existing documents were **looked at**. Nothing in this walk is CREATED.",
        "A Display title is evidence the glass is in display mode. It is not a create proof.",
        "",
    ]
    return "\n".join(lines)
