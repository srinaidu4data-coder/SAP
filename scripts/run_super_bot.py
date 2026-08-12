"""Entry: Super Success Bot — research cascade for 10 PTP + 10 OTC."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_LAB", "1")
os.environ.setdefault("SAPILOT_DATA", str(ROOT / "data"))
# PRODUCT: online GUI + mouse ON by default
os.environ.setdefault("SAPILOT_LIVE_GUI", "1")
os.environ.setdefault("SAPILOT_FORCE_COM_BIND", "1")
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")

from sapilot.autobot.super_bot import main

if __name__ == "__main__":
    raise SystemExit(main())
