"""Screenshot capture — gated behind --allow-vision. Redact before any model egress."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class VisionCapture:
    def __init__(self, allow_vision: bool = False, out_dir: Path | None = None):
        self.allow_vision = allow_vision
        self.out_dir = out_dir

    def capture_window(self, session: Any, name: str = "screen") -> Path | None:
        if not self.allow_vision:
            log.info("Vision disabled; skip screenshot (text-tree first policy)")
            return None
        if self.out_dir is None:
            return None
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{name}.png"
        try:
            # SAP GUI HardCopy
            session.FindById("wnd[0]").HardCopy(str(path), 1)
            return path
        except Exception as e:
            log.warning("HardCopy failed: %s", e)
            return None

    def to_base64(self, path: Path) -> str | None:
        if not self.allow_vision:
            return None
        if not path.exists():
            return None
        return base64.b64encode(path.read_bytes()).decode("ascii")
