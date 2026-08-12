"""CLI entry for one Karpathy loop tick."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_LAB", "1")
os.environ.setdefault("SAPILOT_DATA", str(ROOT / "data"))

from sapilot.autobot.karpathy_loop import main

if __name__ == "__main__":
    raise SystemExit(main())
