"""Entry: mission-critical 20 scenarios with hash chain + exact verify."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")
os.environ.setdefault("SAPILOT_DATA", str(ROOT / "data"))

from sapilot.mission.critical_runner import main

if __name__ == "__main__":
    raise SystemExit(main())
