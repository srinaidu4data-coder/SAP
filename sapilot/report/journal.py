"""Immutable per-run JSONL journal with optional SHA-256 hash chain (SOX evidence)."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _runs_dir() -> Path:
    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    p = root / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RunJournal:
    def __init__(self, run_id: str | None = None, base: Path | None = None, *, chain: bool = True):
        self.run_id = (
            run_id
            or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        )
        self.dir = (base or _runs_dir()) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "journal.jsonl"
        self.chain = chain
        self._prev = "GENESIS"
        self._seq = 0
        if not self.path.exists():
            self.path.touch()
        else:
            # rebuild chain tip
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    self._prev = rec.get("hash") or self._prev
                    self._seq = int(rec.get("seq") or self._seq)
                except Exception:
                    pass

    def append(self, event_type: str, payload: Any) -> None:
        self._seq += 1
        rec: dict[str, Any] = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "type": event_type,
            "payload": payload,
        }
        if self.chain:
            rec["prev"] = self._prev
            body = {k: v for k, v in rec.items() if k != "hash"}
            h = _stable_hash(body)
            rec["hash"] = h
            self._prev = h
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        rows = []
        if not self.path.exists():
            return rows
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify hash chain integrity for SOX-grade evidence."""
        if not self.chain:
            return True, []
        errors: list[str] = []
        prev = "GENESIS"
        expect_seq = 0
        for i, rec in enumerate(self.read_all(), 1):
            expect_seq += 1
            if rec.get("prev") != prev:
                errors.append(f"line {i}: prev hash mismatch")
            body = {k: v for k, v in rec.items() if k != "hash"}
            if rec.get("hash") != _stable_hash(body):
                errors.append(f"line {i}: content hash mismatch")
            if int(rec.get("seq") or 0) != expect_seq:
                errors.append(f"line {i}: seq mismatch")
            prev = rec.get("hash", prev)
        return len(errors) == 0, errors
