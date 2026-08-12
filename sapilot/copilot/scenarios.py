"""
Scenario engine — YAML playbooks executed as deterministic Co-pilot scripts,
with optional LLM assist for recovery.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import yaml

from sapilot.connect.driver import GuiDriver
from sapilot.copilot.knowledge import DataExtractor
from sapilot.report.journal import RunJournal

log = logging.getLogger(__name__)

StepHandler = Callable[[dict[str, Any], "ScenarioContext"], Any]


class ScenarioContext:
    def __init__(
        self,
        driver: GuiDriver | None,
        extractor: DataExtractor,
        journal: RunJournal,
        params: dict[str, Any],
    ):
        self.driver = driver
        self.extractor = extractor
        self.journal = journal
        self.params = params
        self.vars: dict[str, Any] = dict(params)
        self.results: list[dict[str, Any]] = []


def _scenarios_dir() -> Path:
    return Path(__file__).resolve().parent / "scenarios"


def list_scenarios() -> list[dict[str, str]]:
    out = []
    for p in sorted(_scenarios_dir().glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out.append(
            {
                "id": data.get("id") or p.stem,
                "title": data.get("title") or p.stem,
                "description": data.get("description") or "",
                "path": str(p),
            }
        )
    return out


def load_scenario(scenario_id: str) -> dict[str, Any]:
    import re

    if not re.fullmatch(r"[A-Za-z0-9_-]+", scenario_id or ""):
        raise FileNotFoundError(f"Invalid scenario id: {scenario_id!r}")
    root = _scenarios_dir().resolve()
    path = (root / f"{scenario_id}.yaml").resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise FileNotFoundError(f"Scenario not found: {scenario_id}") from e
    if path.exists() and path.is_file():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for p in root.glob("*.yaml"):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if data.get("id") == scenario_id or p.stem == scenario_id:
            return data
    raise FileNotFoundError(f"Scenario not found: {scenario_id}")


class ScenarioRunner:
    def __init__(self, ctx: ScenarioContext):
        self.ctx = ctx
        self._handlers: dict[str, StepHandler] = {
            "tcode": self._tcode,
            "set": self._set,
            "press": self._press,
            "select": self._select,
            "enter": self._enter,
            "f8": self._f8,
            "f3": self._f3,
            "wait": self._wait,
            "wait_element": self._wait_element,
            "read_table": self._read_table,
            "read_config": self._read_config,
            "extract_grid": self._extract_grid,
            "snapshot": self._snapshot,
            "status": self._status,
            "assert_status_not_error": self._assert_status_not_error,
            "note": self._note,
            "set_var": self._set_var,
        }

    def run(self, scenario: dict[str, Any]) -> dict[str, Any]:
        from sapilot.exceptions import PolicyViolation

        sid = scenario.get("id", "unknown")
        self.ctx.journal.append("scenario_start", {"id": sid, "params": self.ctx.params})
        steps = scenario.get("steps") or []
        for i, step in enumerate(steps):
            action = step.get("action") or step.get("do")
            if not action:
                continue
            # skip GUI-only steps when no driver (knowledge-only mode)
            if self.ctx.driver is None and action in {
                "tcode",
                "set",
                "press",
                "select",
                "enter",
                "f8",
                "f3",
                "wait",
                "wait_element",
                "extract_grid",
                "snapshot",
                "status",
                "assert_status_not_error",
            }:
                self.ctx.journal.append(
                    "step_skip",
                    {"i": i, "action": action, "reason": "no_gui_session"},
                )
                continue
            handler = self._handlers.get(action)
            if not handler:
                raise ValueError(f"Unknown scenario action: {action}")
            try:
                result = handler(step, self.ctx)
                rec = {"i": i, "action": action, "ok": True, "result": _safe(result)}
                self.ctx.results.append(rec)
                self.ctx.journal.append("step", rec)
            except PolicyViolation as e:
                # HARD FAIL — policy never continues
                rec = {
                    "i": i,
                    "action": action,
                    "ok": False,
                    "error": str(e),
                    "policy": True,
                    "step": step,
                }
                self.ctx.results.append(rec)
                self.ctx.journal.append("policy_hard_fail", rec)
                raise
            except Exception as e:
                rec = {"i": i, "action": action, "ok": False, "error": str(e), "step": step}
                self.ctx.results.append(rec)
                self.ctx.journal.append("step_error", rec)
                if step.get("continue_on_error"):
                    log.warning("Step %s failed (continue): %s", i, e)
                    continue
                raise
        summary = {
            "id": sid,
            "ok": all(r.get("ok") for r in self.ctx.results),
            "steps_run": len(self.ctx.results),
            "vars": self.ctx.vars,
            "results": self.ctx.results,
        }
        self.ctx.journal.append("scenario_end", {"id": sid, "ok": summary["ok"]})
        return summary

    # --- handlers ---
    def _tcode(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        tcode = self._fmt(step.get("tcode") or step.get("value"), ctx)
        return {"screen": _screen_brief(ctx.driver.start_transaction(tcode))}

    def _set(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        target = self._fmt(step.get("target") or step.get("field"), ctx)
        value = self._fmt(step.get("value"), ctx)
        ctx.driver.set_text(target, value)
        return {"target": target, "value": value}

    def _press(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        target = self._fmt(step.get("target"), ctx)
        ctx.driver.press(target)
        return {"pressed": target}

    def _select(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        target = self._fmt(step.get("target"), ctx)
        ctx.driver.select(target)
        return {"selected": target}

    def _enter(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        ctx.driver.send_enter()
        return {"status": ctx.driver.status_bar()}

    def _f8(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        ctx.driver.send_f8()
        return {"status": ctx.driver.status_bar()}

    def _f3(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        ctx.driver.send_f3()
        return {"status": ctx.driver.status_bar()}

    def _wait(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        import time

        seconds = float(step.get("seconds") or step.get("value") or 1)
        time.sleep(seconds)
        return {"waited": seconds}

    def _wait_element(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        target = self._fmt(step.get("target"), ctx)
        timeout = float(step.get("timeout") or 15)
        eid = ctx.driver.wait_for_element(target, timeout=timeout)
        return {"id": eid}

    def _read_table(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        table = self._fmt(step.get("table") or step.get("target"), ctx)
        fields = step.get("fields")
        options = [self._fmt(o, ctx) for o in (step.get("options") or [])]
        rowcount = int(step.get("rowcount") or 100)
        data = ctx.extractor.read_table(table, fields=fields, options=options, rowcount=rowcount)
        key = step.get("as") or table
        ctx.vars[key] = data
        return data

    def _read_config(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        kind = step.get("kind") or "fbzp"
        if kind == "fbzp":
            data = ctx.extractor.fbzp_snapshot(
                self._fmt(step.get("bukrs") or ctx.params.get("bukrs", "1000"), ctx),
                self._fmt(step.get("method") or ctx.params.get("method", "A"), ctx),
                self._fmt(step.get("land1") or ctx.params.get("land1", "US"), ctx),
            )
        elif kind == "vendor":
            data = ctx.extractor.vendor_pack(
                self._fmt(step.get("lifnr") or ctx.params.get("lifnr", ""), ctx),
                self._fmt(step.get("bukrs") or ctx.params.get("bukrs", "1000"), ctx),
            )
        elif kind == "payment_run":
            data = ctx.extractor.payment_run_status(
                self._fmt(step.get("laufd") or ctx.params.get("laufd", ""), ctx),
                self._fmt(step.get("laufi") or ctx.params.get("laufi", ""), ctx),
            )
        else:
            raise ValueError(f"Unknown read_config kind: {kind}")
        key = step.get("as") or kind
        ctx.vars[key] = data
        return {"keys": list(data.keys()) if isinstance(data, dict) else type(data).__name__}

    def _extract_grid(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        data = ctx.extractor.extract_visible_grid(step.get("table_id"))
        key = step.get("as") or "grid"
        ctx.vars[key] = data
        return {"count": data.get("count", 0)}

    def _snapshot(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        data = ctx.extractor.screen_summary()
        key = step.get("as") or "screen"
        ctx.vars[key] = data
        return {"title": data.get("title"), "tcode": data.get("tcode")}

    def _status(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        data = ctx.extractor.resolve_status_bar()
        ctx.vars["last_message"] = data
        return data

    def _assert_status_not_error(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        assert ctx.driver
        msg = ctx.extractor.resolve_status_bar()
        if (msg.get("msgty") or "").upper() in {"E", "A", "X"}:
            raise RuntimeError(f"SAP error status: {msg}")
        return msg

    def _note(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        text = self._fmt(step.get("text") or step.get("value") or "", ctx)
        return {"note": text}

    def _set_var(self, step: dict[str, Any], ctx: ScenarioContext) -> Any:
        name = step.get("name")
        value = self._fmt(step.get("value"), ctx)
        ctx.vars[str(name)] = value
        return {name: value}

    def _fmt(self, template: Any, ctx: ScenarioContext) -> str:
        if template is None:
            return ""
        s = str(template)
        # {param} substitution from ctx.vars / params
        for k, v in {**ctx.params, **ctx.vars}.items():
            if isinstance(v, (str, int, float)):
                s = s.replace("{" + str(k) + "}", str(v))
        return s


def _screen_brief(snap: Any) -> dict[str, str]:
    return {
        "tcode": getattr(snap, "tcode", ""),
        "title": getattr(snap, "title", ""),
        "status": getattr(snap, "status_bar", ""),
    }


def _safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in list(obj.items())[:50]}
    if isinstance(obj, list):
        return [_safe(x) for x in obj[:30]]
    return str(obj)[:500]
