"""Autonomous bot: 10 PTP + 10 OTC — gets data alone, creates missing, executes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")
os.environ.setdefault("SAPILOT_DATA", str(ROOT / "data"))

from sapilot.autobot.consultant import ConsultantBot


def main() -> int:
    # Live GUI only when explicitly requested — COM bind can hang without scripting
    live = os.environ.get("SAPILOT_LIVE_GUI", "0").strip() in {"1", "true", "yes"}
    show = os.environ.get("SAPILOT_SHOW_MOUSE", "0").strip() in {"1", "true", "yes"}
    bot = ConsultantBot(use_live_gui=live, show_mouse=show and live, auto_remediate=True)
    result = bot.run_all_twenty()
    ok = sum(1 for m in result["missions"] if m["ok"])
    total = len(result["missions"])
    print()
    print("=" * 64)
    print("PTP")
    for m in result["missions"]:
        if m["id"].startswith("S"):
            print(f"  {'OK' if m['ok'] else 'FAIL'}  {m['id']}: {m['title']}")
    print("OTC")
    for m in result["missions"]:
        if m["id"].startswith("O"):
            print(f"  {'OK' if m['ok'] else 'FAIL'}  {m['id']}: {m['title']}")
    print("=" * 64)
    print(result["summary"])
    print("Report:", ROOT / "data" / "runs" / "AUTOBOT_20_PTP_OTC_RESULTS.json")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
