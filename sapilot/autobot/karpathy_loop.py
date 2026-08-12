"""
Karpathy-style auto-improvement loop — 100 iterations, MEGA reminders.

Exhaustive fleet bar (must all pass before perfected):
  • 10 PTP scenarios
  • 10 OTC scenarios
  • 2 ABAP debugging scenarios (ST22 + SE38 safe inspect)
  = 22 total

NO STOP until fleet exhausted OR iteration == 100.
Each tick writes a MEGA reminder for Grok (agent mode) to keep coding.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
MAX_ITERS = 100
STATE_DIR = Path(os.environ.get("SAPILOT_DATA", _ROOT / "data")) / "runs" / "karpathy_loop"
STATE_PATH = STATE_DIR / "state.json"
LOG_PATH = STATE_DIR / "loop.jsonl"
PROMPT_PATH = STATE_DIR / "NEXT_AGENT_PROMPT.md"
MEGA_PROMPT_PATH = STATE_DIR / "MEGA_REMINDER.md"
BOARD_PATH = _ROOT / "KARPATHY_LOOP.md"
REMINDERS_DIR = STATE_DIR / "mega_reminders"

FLEET = {"ptp": 10, "otc": 10, "abap": 2, "total": 22}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REMINDERS_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_PATH.exists():
        st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        # Upgrade prior 10-iter states to 100
        if int(st.get("max_iterations") or 0) < MAX_ITERS:
            st["max_iterations"] = MAX_ITERS
            st["goal"] = (
                "EXHAUST fleet: 10 PTP + 10 OTC + 2 ABAP debug = 22 SUCCESS; "
                "true_online when scripting available"
            )
            st["no_stop_until"] = "fleet_exhausted OR iteration==100"
        return st
    return {
        "iteration": 0,
        "max_iterations": MAX_ITERS,
        "interval_minutes": 15,
        "goal": (
            "EXHAUST fleet: 10 PTP + 10 OTC + 2 ABAP debug = 22 SUCCESS; "
            "true_online when scripting available"
        ),
        "no_stop_until": "fleet_exhausted OR iteration==100",
        "perfected": False,
        "fleet_exhausted": False,
        "history": [],
        "created_at": utc_iso(),
    }


def _save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _append_log(rec: dict[str, Any]) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def _run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    env = {
        **os.environ,
        "SAPILOT_LAB": "1",
        "SAPILOT_ALLOW_UNSIGNED_POLICY": "1",
        "SAPILOT_DATA": str(Path(os.environ.get("SAPILOT_DATA", _ROOT / "data"))),
        "PYTHONPATH": str(_ROOT),
        "SAPILOT_LIVE_GUI": os.environ.get("SAPILOT_LIVE_GUI", "0"),
        "SAPILOT_SHOW_MOUSE": os.environ.get("SAPILOT_SHOW_MOUSE", "0"),
    }
    try:
        p = subprocess.run(
            cmd,
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or ""))[-5000:]
    except subprocess.TimeoutExpired as e:
        return 1, f"TIMEOUT: {e}"
    except Exception as e:
        return 1, str(e)


def measure() -> dict[str, Any]:
    from sapilot.autobot.online_health import probe_online_health
    from sapilot.autobot.online_runner import OnlineScenarioRunner
    from sapilot.autobot.super_bot import SuperSuccessBot
    from sapilot.mission.critical_runner import CriticalMissionRunner

    health = probe_online_health(com_timeout_s=4.0)

    # Super fleet 22 in-process (faster + consistent)
    try:
        # Product mode online; CI measure uses offline only if SAPILOT_OFFLINE=1
        super_summary = SuperSuccessBot().run_all()
    except Exception as e:
        super_summary = {
            "all_success": False,
            "success_count": 0,
            "total": 22,
            "error": str(e),
            "ptp_ok_count": 0,
            "otc_ok_count": 0,
            "abap_ok_count": 0,
            "fleet_exhausted": False,
        }

    try:
        # Prefer online for mission-critical GUI steps when available
        live = os.environ.get("SAPILOT_OFFLINE", "").strip().lower() not in {"1", "true", "yes"}
        mc = CriticalMissionRunner(use_live_gui=live, show_mouse=live).run_all()
    except Exception as e:
        mc = {"all_pass": False, "ok_count": 0, "total": 22, "error": str(e)}

    code_t, out_t = _run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
        150,
    )

    try:
        # Product online runner — no offline success
        online = OnlineScenarioRunner(allow_offline_fallback=False).run_all()
    except Exception as e:
        online = {
            "all_ok": False,
            "true_online": False,
            "ok_count": 0,
            "total": 22,
            "error": str(e),
            "blockers": [str(e)],
        }

    ptp_n = int(super_summary.get("ptp_ok_count") or 0)
    otc_n = int(super_summary.get("otc_ok_count") or 0)
    abap_n = int(super_summary.get("abap_ok_count") or 0)
    true_online = bool(
        super_summary.get("true_online")
        or (online.get("true_online") if isinstance(online, dict) else False)
    )
    # PRODUCT: fleet exhausted only when ONLINE GUI succeeded for full fleet
    fleet_exhausted = (
        ptp_n >= FLEET["ptp"]
        and otc_n >= FLEET["otc"]
        and abap_n >= FLEET["abap"]
        and bool(super_summary.get("all_success"))
        and true_online
        and code_t == 0
    )

    return {
        "ts": utc_iso(),
        "health": health.to_dict(),
        "health_score": health.score,
        "super_bot": bool(super_summary.get("all_success")),
        "super_summary": {
            "success_count": super_summary.get("success_count"),
            "total": super_summary.get("total"),
            "ptp": ptp_n,
            "otc": otc_n,
            "abap": abap_n,
            "fleet_exhausted": super_summary.get("fleet_exhausted"),
        },
        "mission_critical": bool(mc.get("all_pass")),
        "mission_ok": f"{mc.get('ok_count')}/{mc.get('total')}",
        "unit_tests": code_t == 0,
        "unit_tail": out_t[-200:],
        "online": {
            "all_ok": online.get("all_ok"),
            "true_online": online.get("true_online"),
            "ok_count": online.get("ok_count"),
            "total": online.get("total"),
            "session_bound": online.get("session_bound"),
            "mode": online.get("mode"),
            "blockers": online.get("blockers") or health.blockers,
            "report": online.get("report"),
        },
        "fleet": {
            "ptp": ptp_n,
            "otc": otc_n,
            "abap": abap_n,
            "required": FLEET,
            "exhausted": fleet_exhausted,
        },
    }


def diagnose_gaps(m: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    fleet = m.get("fleet") or {}
    o = m.get("online") or {}
    h = m.get("health") or {}

    if not m.get("unit_tests"):
        gaps.append({"id": "unit_tests", "severity": "critical", "fix": "Fix pytest until green"})
    if not m.get("super_bot"):
        gaps.append(
            {
                "id": "super_fleet",
                "severity": "critical",
                "fix": "Super Bot must SUCCESS 22/22 (10 PTP + 10 OTC + 2 ABAP)",
            }
        )
    if not m.get("mission_critical"):
        gaps.append(
            {
                "id": "mission_critical",
                "severity": "critical",
                "fix": "Mission-critical fingerprints 22/22",
            }
        )
    if int(fleet.get("ptp") or 0) < 10:
        gaps.append(
            {
                "id": "ptp_10",
                "severity": "blocker",
                "fix": f"Only {fleet.get('ptp')}/10 PTP — fix packs/remediations/fingerprints",
            }
        )
    if int(fleet.get("otc") or 0) < 10:
        gaps.append(
            {
                "id": "otc_10",
                "severity": "blocker",
                "fix": f"Only {fleet.get('otc')}/10 OTC — fix OTC packs/chain",
            }
        )
    if int(fleet.get("abap") or 0) < 2:
        gaps.append(
            {
                "id": "abap_2",
                "severity": "blocker",
                "fix": (
                    f"Only {fleet.get('abap')}/2 ABAP debug — seed SNAP/TRDIR, "
                    "packs abap_01/abap_02, nav ST22/SE38, never field-replace"
                ),
            }
        )
    if not h.get("scripting_engine"):
        gaps.append(
            {
                "id": "scripting",
                "severity": "blocker_online",
                "fix": "Enable sapgui/user_scripting=TRUE + Logon scripting; COM timeout-safe bind",
            }
        )
    if not o.get("true_online"):
        gaps.append(
            {
                "id": "true_online",
                "severity": "goal",
                "fix": "Bind live session + run all 22 with GUI nav + data verify",
            }
        )
    if not gaps:
        gaps.append({"id": "polish", "severity": "low", "fix": "Polish mega UI + docs; re-harden"})
    return gaps


def apply_auto_fixes(gaps: list[dict[str, str]], iteration: int) -> list[str]:
    actions: list[str] = []
    # Always re-seed ABAP on early ticks
    try:
        from sapilot.autobot.digital_twin import DigitalTwin

        t = DigitalTwin()
        fixes = t.ensure_abap_debug_ready()
        actions.append("abap_ready: " + "; ".join(fixes))
    except Exception as e:
        actions.append(f"abap_seed_fail: {e}")

    bat = _ROOT / "start_fleet_22.bat"
    bat.write_text(
        "\n".join(
            [
                "@echo off",
                "cd /d %~dp0",
                "set SAPILOT_LAB=1",
                "set SAPILOT_ALLOW_UNSIGNED_POLICY=1",
                "set SAPILOT_DATA=%~dp0data",
                "set PYTHONPATH=%~dp0",
                "echo === FLEET 22: 10 PTP + 10 OTC + 2 ABAP ===",
                "python -m sapilot super-bot",
                "python -m sapilot mission-critical --no-gui",
                "python -m sapilot karpathy-tick",
                "pause",
                "",
            ]
        ),
        encoding="utf-8",
    )
    actions.append("wrote start_fleet_22.bat")

    checklist = _ROOT / "ONLINE_BASIS_CHECKLIST.md"
    checklist.write_text(
        "\n".join(
            [
                "# Online + Fleet Exhaust Checklist",
                "",
                "## Fleet (must be 22/22 before stop)",
                "- 10 PTP (S1–S10)",
                "- 10 OTC (O1–O10)",
                "- 2 ABAP debug (A1 ST22, A2 SE38) — **read-only**, never debugger field replace",
                "",
                "## Live online",
                "1. SAP Logon → Enable Scripting",
                "2. RZ11 `sapgui/user_scripting=TRUE`",
                "3. Login Vista client 100",
                "4. `set SAPILOT_LIVE_GUI=1` && `python -m sapilot online-20`",
                "",
                f"Tick template: {iteration}/100",
                "",
            ]
        ),
        encoding="utf-8",
    )
    actions.append("refreshed ONLINE_BASIS_CHECKLIST.md")

    trail = STATE_DIR / f"tick_{iteration:03d}_actions.json"
    trail.write_text(
        json.dumps({"iteration": iteration, "gaps": gaps, "actions": actions, "ts": utc_iso()}, indent=2),
        encoding="utf-8",
    )
    actions.append(f"wrote {trail.name}")
    return actions


def write_mega_reminder(
    state: dict[str, Any], measure_result: dict[str, Any], gaps: list[dict]
) -> str:
    """MEGA reminder — aggressive no-stop coding mandate for Grok agent mode."""
    n = state["iteration"]
    max_n = state["max_iterations"]
    fleet = measure_result.get("fleet") or {}
    o = measure_result.get("online") or {}
    body = f"""# 🚨 MEGA REMINDER — KARPATHY LOOP {n}/{max_n}

## YOU ARE GROK IN FULL AGENT MODE. DO NOT STOP CODING.

**Permissions:** full read/write/execute on `C:\\Projects\\SAP`.  
**Rule:** No idle. No “looks good offline”. **Code until the fleet is exhausted.**

---

### FLEET EXHAUST BAR (non-negotiable)

| Track | Required | Current |
|-------|----------|---------|
| PTP | **10** | **{fleet.get('ptp', 0)}** |
| OTC | **10** | **{fleet.get('otc', 0)}** |
| ABAP debug | **2** | **{fleet.get('abap', 0)}** |
| **TOTAL** | **22** | **{(fleet.get('ptp') or 0)+(fleet.get('otc') or 0)+(fleet.get('abap') or 0)}** |

- Super Bot all_success: **{measure_result.get('super_bot')}**
- Mission critical: **{measure_result.get('mission_critical')}** ({measure_result.get('mission_ok')})
- Unit tests: **{measure_result.get('unit_tests')}**
- Fleet exhausted: **{fleet.get('exhausted')}**
- true_online: **{o.get('true_online')}** (ok {o.get('ok_count')}/{o.get('total')})
- Perfected: **{state.get('perfected')}**

---

### MANDATE THIS TICK

1. `cd C:\\Projects\\SAP`
2. Read `data/runs/karpathy_loop/state.json` + this file
3. Run: `python -m sapilot karpathy-tick`
4. **If any of PTP<10, OTC<10, ABAP<2:** implement code now:
   - packs / fingerprints / twin seed / nav_catalog / super_bot / critical_runner
   - ABAP: ST22 dump + SE38 source inspect only — **NEVER debugger field-value replace**
5. Re-run until green: `python -m sapilot super-bot` · mission-critical · pytest · online-20
6. **Do not declare done** until `fleet.exhausted == true` AND tests green
7. Online scripting blocked? Still finish offline 22/22; then harden COM/login for true_online
8. Never type `/nTCODE` into LIFNR/Supplier/PROGRAM data fields — StartTransaction/okcd only

---

### GAPS (fix in this order)

"""
    for g in gaps:
        body += f"- **[{g['severity']}] {g['id']}**: {g['fix']}\n"
    body += "\n### Blockers\n\n"
    for b in o.get("blockers") or []:
        body += f"- {b}\n"
    body += f"""

### Commands

```bat
python -m sapilot karpathy-tick
python -m sapilot super-bot
python -m sapilot mission-critical --no-gui
python -m sapilot online-health
python -m sapilot online-20
python -m pytest tests -q
start_fleet_22.bat
```

### Definition of PERFECTED (only then stop)

1. 10/10 PTP SUCCESS  
2. 10/10 OTC SUCCESS  
3. 2/2 ABAP debug SUCCESS  
4. Super Bot `all_success` + mission-critical `all_pass`  
5. pytest green  
6. Prefer true_online when Basis allows scripting  

**NO CODING STOPS UNTIL FLEET EXHAUSTED OR ITERATION 100.**

Generated: {utc_iso()}
"""
    MEGA_PROMPT_PATH.write_text(body, encoding="utf-8")
    # Per-iteration archive
    arch = REMINDERS_DIR / f"MEGA_{n:03d}.md"
    arch.write_text(body, encoding="utf-8")
    PROMPT_PATH.write_text(body, encoding="utf-8")
    return body


def write_board(state: dict[str, Any]) -> None:
    lines = [
        "# Karpathy Auto-Loop Board (100 × MEGA)",
        "",
        f"**Goal:** {state.get('goal')}",
        f"**No-stop until:** {state.get('no_stop_until')}",
        f"**Iteration:** {state.get('iteration')}/{state.get('max_iterations')}",
        f"**Fleet exhausted:** {state.get('fleet_exhausted')}",
        f"**Perfected:** {state.get('perfected')}",
        "",
        "Fleet bar: **10 PTP + 10 OTC + 2 ABAP debug = 22**",
        "",
        "| Iter | ts | PTP | OTC | ABAP | super | mission | tests | true_online | exhausted |",
        "|------|----|-----|-----|------|-------|---------|-------|-------------|-----------|",
    ]
    for h in (state.get("history") or [])[-40:]:
        f = h.get("fleet") or {}
        o = h.get("online") or {}
        lines.append(
            f"| {h.get('iteration')} | {(h.get('ts') or '')[:19]} | "
            f"{f.get('ptp')}/10 | {f.get('otc')}/10 | {f.get('abap')}/2 | "
            f"{'Y' if h.get('super_bot') else 'N'} | {'Y' if h.get('mission_critical') else 'N'} | "
            f"{'Y' if h.get('unit_tests') else 'N'} | {o.get('true_online')} | {f.get('exhausted')} |"
        )
    lines.extend(
        [
            "",
            "## MEGA reminder (current)",
            "",
            f"`{MEGA_PROMPT_PATH}`",
            "",
            f"Archive: `{REMINDERS_DIR}`",
            "",
            "## Scheduler",
            "",
            "100 fires · mega coding mandate · stops only when fleet exhausted or iter=100",
            "",
        ]
    )
    BOARD_PATH.write_text("\n".join(lines), encoding="utf-8")


def tick() -> dict[str, Any]:
    state = _load_state()
    state["max_iterations"] = MAX_ITERS

    if state.get("perfected") and state.get("fleet_exhausted"):
        write_mega_reminder(state, state.get("last_measure") or {}, [])
        return {
            "ok": True,
            "perfected": True,
            "fleet_exhausted": True,
            "iteration": state["iteration"],
            "msg": "FLEET EXHAUSTED — perfected",
        }

    if state["iteration"] >= state["max_iterations"]:
        return {
            "ok": False,
            "perfected": False,
            "fleet_exhausted": state.get("fleet_exhausted"),
            "iteration": state["iteration"],
            "msg": "HIT 100 — stop scheduler; review remaining gaps",
        }

    state["iteration"] += 1
    n = state["iteration"]
    print(f"[KARPATHY] === MEGA TICK {n}/{MAX_ITERS} ===")

    try:
        m = measure()
    except Exception as e:
        m = {
            "error": str(e),
            "trace": traceback.format_exc(),
            "online": {},
            "fleet": {"ptp": 0, "otc": 0, "abap": 0, "exhausted": False},
            "health_score": 0,
        }
        print("[KARPATHY] measure error:", e)

    gaps = diagnose_gaps(m) if "error" not in m else [
        {"id": "measure_crash", "severity": "critical", "fix": str(m.get("error"))}
    ]
    actions = apply_auto_fixes(gaps, n)
    write_mega_reminder(state, m, gaps)

    fleet_exhausted = bool((m.get("fleet") or {}).get("exhausted"))
    state["fleet_exhausted"] = fleet_exhausted
    # Perfected = fleet exhausted (22/22 + tests). true_online is bonus when Basis allows.
    if fleet_exhausted:
        state["perfected"] = True

    hist = {
        "iteration": n,
        "ts": utc_iso(),
        "health_score": m.get("health_score"),
        "super_bot": m.get("super_bot"),
        "mission_critical": m.get("mission_critical"),
        "unit_tests": m.get("unit_tests"),
        "online": m.get("online"),
        "fleet": m.get("fleet"),
        "gaps": gaps,
        "auto_actions": actions,
        "perfected": state["perfected"],
    }
    state.setdefault("history", []).append(hist)
    state["last_measure"] = {
        "health_score": m.get("health_score"),
        "online": m.get("online"),
        "fleet": m.get("fleet"),
        "gaps": gaps,
        "super_bot": m.get("super_bot"),
        "mission_critical": m.get("mission_critical"),
        "unit_tests": m.get("unit_tests"),
        "mission_ok": m.get("mission_ok"),
    }
    state["updated_at"] = utc_iso()
    _save_state(state)
    _append_log(hist)
    write_board(state)

    print(
        f"[KARPATHY] fleet PTP={ (m.get('fleet') or {}).get('ptp') } "
        f"OTC={(m.get('fleet') or {}).get('otc')} "
        f"ABAP={(m.get('fleet') or {}).get('abap')} "
        f"exhausted={fleet_exhausted} perfected={state['perfected']}"
    )
    print(f"[KARPATHY] MEGA → {MEGA_PROMPT_PATH}")

    return {
        "ok": True,
        "iteration": n,
        "max_iterations": MAX_ITERS,
        "perfected": state["perfected"],
        "fleet_exhausted": fleet_exhausted,
        "fleet": m.get("fleet"),
        "gaps": gaps,
        "auto_actions": actions,
        "mega_reminder": str(MEGA_PROMPT_PATH),
        "state_path": str(STATE_PATH),
        "board": str(BOARD_PATH),
        "online": m.get("online"),
        "should_stop_scheduler": state["perfected"] or n >= MAX_ITERS,
    }


def main() -> int:
    os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
    os.environ.setdefault("SAPILOT_LAB", "1")
    os.environ.setdefault("SAPILOT_DATA", str(_ROOT / "data"))
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    result = tick()
    print(json.dumps({k: v for k, v in result.items() if k != "gaps"}, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
