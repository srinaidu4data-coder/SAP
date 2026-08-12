"""Load project .env into process environment (no extra dependency)."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> Path | None:
    """
    Parse KEY=VALUE lines from .env into os.environ (does not override existing).
    Returns path loaded, or None if missing.
    """
    candidates = []
    if path is not None:
        candidates.append(path)
    else:
        # Project root: cwd, then parent of package
        candidates.append(Path.cwd() / ".env")
        candidates.append(Path(__file__).resolve().parent.parent / ".env")
        home = os.environ.get("SAPILOT_HOME")
        if home:
            candidates.append(Path(home) / ".env")

    for p in candidates:
        if p.is_file():
            _apply(p)
            return p
    return None


def _apply(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        # Do not override explicit environment
        if key not in os.environ or os.environ.get(key, "") == "":
            os.environ[key] = val
