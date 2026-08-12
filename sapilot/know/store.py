"""SQLite episodic + semantic memory for remediations."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _default_db() -> Path:
    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    p = root / "kb"
    p.mkdir(parents=True, exist_ok=True)
    return p / "sapilot.db"


class KnowledgeStore:
    def __init__(self, path: Path | None = None):
        self.path = path or _default_db()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path))
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_signature TEXT NOT NULL,
                    symptom TEXT,
                    remediation_json TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_ep_sig ON episodes(message_signature);

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def record_remediation(
        self,
        message_signature: str,
        symptom: str,
        remediation: dict[str, Any],
        success: bool,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO episodes(message_signature, symptom, remediation_json, success) "
                "VALUES (?,?,?,?)",
                (message_signature, symptom, json.dumps(remediation), 1 if success else 0),
            )

    def lookup_remediation(self, message_signature: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT remediation_json FROM episodes "
                "WHERE message_signature=? AND success=1 ORDER BY id DESC LIMIT 1",
                (message_signature,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["remediation_json"])

    def set_fact(self, key: str, value: Any) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO facts(key, value_json) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, "
                "updated_at=CURRENT_TIMESTAMP",
                (key, json.dumps(value)),
            )

    def get_fact(self, key: str) -> Any | None:
        with self._conn() as c:
            row = c.execute("SELECT value_json FROM facts WHERE key=?", (key,)).fetchone()
            return json.loads(row["value_json"]) if row else None
