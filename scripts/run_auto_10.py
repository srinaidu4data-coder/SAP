"""Headless: run 10 autonomous consultant scenarios (creates missing data)."""
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
    bot = ConsultantBot(use_live_gui=True, show_mouse=True, auto_remediate=True)
    # Default now: full 10 PTP + 10 OTC
    result = bot.run_all_twenty(
        "Run full PTP and OTC. Get table data alone. Create what is missing."
    )
    ok = sum(1 for m in result["missions"] if m["ok"])
    total = len(result["missions"])
    print()
    print("=" * 60)
    print("PTP (10)")
    for m in result["missions"]:
        if m["id"].startswith("S"):
            print(f"  {'OK' if m['ok'] else 'FAIL'}  {m['id']}: {m['title']}")
            if m["fixes"]:
                print(f"       fixes: {m['fixes'][:3]}")
    print("OTC (10)")
    for m in result["missions"]:
        if m["id"].startswith("O"):
            print(f"  {'OK' if m['ok'] else 'FAIL'}  {m['id']}: {m['title']}")
            if m["fixes"]:
                print(f"       fixes: {m['fixes'][:3]}")
    print("=" * 60)
    print(result["summary"])
    print("Report:", ROOT / "data" / "runs" / "AUTOBOT_20_PTP_OTC_RESULTS.json")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
