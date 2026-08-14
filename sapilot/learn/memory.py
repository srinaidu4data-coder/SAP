"""Persistent navigation memory. Wins are reused. Losses are not repeated."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any


def _db_path() -> Path:
    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    p = root / "kb"
    p.mkdir(parents=True, exist_ok=True)
    return p / "nav_learn.db"


_LOCK = threading.Lock()


class NavMemory:
    def __init__(self, path: Path | None = None):
        self.path = path or _db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path), timeout=15)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signature TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    reward INTEGER NOT NULL,
                    title TEXT,
                    status TEXT,
                    note TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_ep_sig ON episodes(signature, intent);

                CREATE TABLE IF NOT EXISTS skills (
                    signature TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (signature, intent, action_json)
                );

                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    recipe_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS beliefs (
                    key TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    thought TEXT,
                    source TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS thoughts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thought TEXT NOT NULL,
                    table_name TEXT,
                    action TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def record(
        self,
        signature: str,
        intent: str,
        action: dict[str, Any],
        reward: int,
        *,
        title: str = "",
        status: str = "",
        note: str = "",
    ) -> None:
        payload = json.dumps(action, sort_keys=True)
        with _LOCK, self._conn() as c:
            c.execute(
                "INSERT INTO episodes(signature, intent, action_json, reward, title, status, note) "
                "VALUES (?,?,?,?,?,?,?)",
                (signature, intent, payload, int(reward), title, status, note[:240]),
            )
            row = c.execute(
                "SELECT wins, losses FROM skills WHERE signature=? AND intent=? AND action_json=?",
                (signature, intent, payload),
            ).fetchone()
            if row is None:
                wins = 1 if reward > 0 else 0
                losses = 1 if reward < 0 else 0
                c.execute(
                    "INSERT INTO skills(signature, intent, action_json, wins, losses) VALUES (?,?,?,?,?)",
                    (signature, intent, payload, wins, losses),
                )
            else:
                if reward > 0:
                    c.execute(
                        "UPDATE skills SET wins=wins+1 WHERE signature=? AND intent=? AND action_json=?",
                        (signature, intent, payload),
                    )
                elif reward < 0:
                    c.execute(
                        "UPDATE skills SET losses=losses+1 WHERE signature=? AND intent=? AND action_json=?",
                        (signature, intent, payload),
                    )

    def best_action(self, signature: str, intent: str) -> dict[str, Any] | None:
        with _LOCK, self._conn() as c:
            row = c.execute(
                "SELECT action_json, wins, losses FROM skills "
                "WHERE signature=? AND intent=? AND wins > losses "
                "ORDER BY (wins - losses) DESC, wins DESC LIMIT 1",
                (signature, intent),
            ).fetchone()
            if not row:
                # same intent, any similar signature prefix (kind)
                kind = (signature or "").split("|")[0]
                row = c.execute(
                    "SELECT action_json, wins, losses FROM skills "
                    "WHERE intent=? AND signature LIKE ? AND wins > losses "
                    "ORDER BY (wins - losses) DESC LIMIT 1",
                    (intent, kind + "%"),
                ).fetchone()
            if not row:
                return None
            rec = json.loads(row["action_json"])
            rec["_wins"] = row["wins"]
            rec["_losses"] = row["losses"]
            return rec

    def add_knowledge(self, source: str, title: str, recipe: dict[str, Any], url: str = "") -> None:
        with _LOCK, self._conn() as c:
            exists = c.execute(
                "SELECT id FROM knowledge WHERE source=? AND title=?",
                (source, title),
            ).fetchone()
            if exists:
                return
            c.execute(
                "INSERT INTO knowledge(source, url, title, recipe_json) VALUES (?,?,?,?)",
                (source, url, title, json.dumps(recipe)),
            )

    def knowledge(self) -> list[dict[str, Any]]:
        with _LOCK, self._conn() as c:
            rows = c.execute(
                "SELECT source, url, title, recipe_json FROM knowledge ORDER BY id DESC"
            ).fetchall()
        out = []
        for r in rows:
            rec = {"source": r["source"], "url": r["url"], "title": r["title"]}
            rec.update(json.loads(r["recipe_json"]))
            out.append(rec)
        return out

    def set_belief(
        self,
        key: str,
        kind: str,
        payload: dict[str, Any],
        *,
        thought: str = "",
        source: str = "glass",
    ) -> None:
        name = (key or "").strip().upper()
        if not name:
            return
        with _LOCK, self._conn() as c:
            c.execute(
                "INSERT INTO beliefs(key, kind, payload_json, thought, source, updated_at) "
                "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET kind=excluded.kind, "
                "payload_json=excluded.payload_json, thought=excluded.thought, "
                "source=excluded.source, updated_at=CURRENT_TIMESTAMP",
                (name, kind, json.dumps(payload), (thought or "")[:400], source),
            )

    def get_belief(self, key: str) -> dict[str, Any] | None:
        name = (key or "").strip().upper()
        with _LOCK, self._conn() as c:
            row = c.execute(
                "SELECT key, kind, payload_json, thought, source, updated_at FROM beliefs WHERE key=?",
                (name,),
            ).fetchone()
        if not row:
            return None
        rec = json.loads(row["payload_json"] or "{}")
        rec.update(
            {
                "key": row["key"],
                "kind": row["kind"],
                "thought": row["thought"] or "",
                "source": row["source"] or "",
                "updated_at": row["updated_at"],
            }
        )
        return rec

    def all_beliefs(self) -> list[dict[str, Any]]:
        with _LOCK, self._conn() as c:
            rows = c.execute(
                "SELECT key, kind, payload_json, thought, source, updated_at "
                "FROM beliefs ORDER BY updated_at DESC"
            ).fetchall()
        out = []
        for row in rows:
            rec = json.loads(row["payload_json"] or "{}")
            rec.update(
                {
                    "key": row["key"],
                    "kind": row["kind"],
                    "thought": row["thought"] or "",
                    "source": row["source"] or "",
                    "updated_at": row["updated_at"],
                }
            )
            out.append(rec)
        return out

    def add_thought(self, thought: str, table: str = "", action: str = "") -> None:
        text = (thought or "").strip()
        if not text:
            return
        with _LOCK, self._conn() as c:
            c.execute(
                "INSERT INTO thoughts(thought, table_name, action) VALUES (?,?,?)",
                (text[:400], (table or "")[:40], (action or "")[:40]),
            )
            c.execute(
                "DELETE FROM thoughts WHERE id NOT IN (SELECT id FROM thoughts ORDER BY id DESC LIMIT 80)"
            )

    def recent_thoughts(self, n: int = 12) -> list[dict[str, Any]]:
        with _LOCK, self._conn() as c:
            rows = c.execute(
                "SELECT thought, table_name, action, created_at FROM thoughts "
                "ORDER BY id DESC LIMIT ?",
                (max(1, min(int(n), 40)),),
            ).fetchall()
        return [
            {
                "thought": r["thought"],
                "table": r["table_name"],
                "action": r["action"],
                "at": r["created_at"],
            }
            for r in rows
        ]

    def stats(self) -> dict[str, Any]:
        with _LOCK, self._conn() as c:
            ep = c.execute("SELECT COUNT(*) n FROM episodes").fetchone()["n"]
            sk = c.execute("SELECT COUNT(*) n FROM skills WHERE wins > losses").fetchone()["n"]
            kn = c.execute("SELECT COUNT(*) n FROM knowledge").fetchone()["n"]
            wins = c.execute("SELECT COALESCE(SUM(wins),0) n FROM skills").fetchone()["n"]
            losses = c.execute("SELECT COALESCE(SUM(losses),0) n FROM skills").fetchone()["n"]
            try:
                beliefs = c.execute("SELECT COUNT(*) n FROM beliefs").fetchone()["n"]
            except Exception:
                beliefs = 0
        return {
            "episodes": ep,
            "skills": sk,
            "knowledge": kn,
            "wins": wins,
            "losses": losses,
            "beliefs": beliefs,
        }


def default_memory() -> NavMemory:
    return NavMemory()
