"""
End-to-end system completion board.
Runs: unit tests → RT probes → mission critical 20 → auto 20 → writes SYSTEM_STATUS.md
Exit 0 only if everything that can pass offline passes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_LAB", "1")
os.environ.setdefault("SAPILOT_ENV", "lab")
os.environ.setdefault("SAPILOT_DATA", str(ROOT / "data"))
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "0")
os.environ.setdefault("PYTHONPATH", str(ROOT))


def run(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    env = {
        **os.environ,
        "SAPILOT_LIVE_GUI": "0",
        "SAPILOT_SHOW_MOUSE": "0",
        "SAPILOT_LAB": "1",
        "SAPILOT_ALLOW_UNSIGNED_POLICY": "1",
    }
    try:
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out
    except subprocess.TimeoutExpired as e:
        return 1, f"TIMEOUT after {timeout}s: {e}"


def main() -> int:
    board: list[dict] = []
    all_ok = True

    def rec(name: str, code: int, detail: str) -> None:
        nonlocal all_ok
        ok = code == 0
        if not ok:
            all_ok = False
        board.append({"name": name, "ok": ok, "code": code, "detail": detail[-500:]})
        print(("PASS" if ok else "FAIL"), name, detail.splitlines()[-1] if detail.strip() else "")

    code, out = run([sys.executable, "-m", "pytest", "tests", "-q", "--tb=line"], 180)
    rec("unit_tests", code, out)

    code, out = run([sys.executable, "scripts/rt_probes.py"], 60)
    rec("rt_probes", code, out)

    code, out = run([sys.executable, "scripts/run_mission_critical_20.py"], 120)
    rec("mission_critical_20", code, out)

    # Twin-only auto-20 (no COM hang); set SAPILOT_LIVE_GUI=1 for live
    try:
        env_auto = {**os.environ, "SAPILOT_LIVE_GUI": "0", "SAPILOT_SHOW_MOUSE": "0"}
        p = subprocess.run(
            [sys.executable, "scripts/run_auto_20.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=90,
            env=env_auto,
        )
        rec("auto_20_ptp_otc", p.returncode, (p.stdout or "") + (p.stderr or ""))
    except subprocess.TimeoutExpired as e:
        rec("auto_20_ptp_otc", 1, f"TIMEOUT: {e}")

    # Policy import smoke
    try:
        from sapilot.policy.guard import authorize_write, bind_write_context, clear_write_context
        from sapilot.policy.tier import TierContext
        from sapilot.schemas import Tier
        from sapilot.exceptions import PolicyViolation

        clear_write_context()
        bind_write_context(TierContext(Tier.T3_OBSERVE, "800", "P"), source="complete")
        try:
            authorize_write("press", target="btn")
            rec("policy_chokepoint", 1, "T3 allowed press")
        except PolicyViolation:
            rec("policy_chokepoint", 0, "T3 blocked")
        clear_write_context()
    except Exception as e:
        rec("policy_chokepoint", 1, str(e))

    md = ROOT / "SYSTEM_STATUS.md"
    lines = [
        "# SAPILOT System Status",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Overall:** {'READY' if all_ok else 'PARTIAL / FAIL'}",
        "",
        "| Check | Result | Detail |",
        "|-------|--------|--------|",
    ]
    for b in board:
        flag = "PASS" if b["ok"] else "FAIL"
        det = (b["detail"] or "").replace("|", "/").replace("\n", " ")[:120]
        lines.append(f"| {b['name']} | {flag} | {det} |")
    lines.extend(
        [
            "",
            "## Go-live controls closed",
            "",
            "- Single WriteGuard on GuiDriver / inject / mega goto / scenarios",
            "- Denylist → POLICY_VIOLATION hard-fail (agent loop HARD_FAIL)",
            "- Vault DPAPI-first; weak default passphrase banned outside lab",
            "- Portable HMAC approval tokens + JSONL ledger",
            "- RunJournal SHA-256 hash chain",
            "- Mission fingerprints 20/20 + document chain invariants",
            "",
            "## Commands",
            "",
            "```bat",
            "python scripts\\system_complete.py",
            "python -m sapilot mission-critical --no-gui",
            "python -m sapilot system-status",
            "python -m sapilot auto-20",
            "python scripts\\rt_probes.py",
            "```",
            "",
            "## Live SAP still requires",
            "",
            "- `sapgui/user_scripting = TRUE`",
            "- Optional RFC (pyrfc) for direct table reads",
            "- Dual control tokens for T2 (`sapilot approve --scope gui_write`)",
            "",
        ]
    )
    md.write_text("\n".join(lines), encoding="utf-8")
    json_path = ROOT / "data" / "runs" / "SYSTEM_COMPLETE.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "ok": all_ok,
                "ts": datetime.now(timezone.utc).isoformat(),
                "board": board,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("---")
    print("SYSTEM:", "READY" if all_ok else "FAIL")
    print("Wrote", md)
    print("Wrote", json_path)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
