"""Optional direct HANA SQL — knowledge ladder rung 3. Only when DB user sanctioned."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class HanaClient:
    def __init__(self, address: str, port: int, user: str, password: str, schema: str | None = None):
        self.params = {
            "address": address,
            "port": port,
            "user": user,
            "password": password,
        }
        self.schema = schema
        self._conn = None

    def connect(self) -> None:
        try:
            from hdbcli import dbapi  # type: ignore
        except ImportError as e:
            raise RuntimeError("hdbcli not installed (optional extra: hana)") from e
        self._conn = dbapi.connect(**self.params)

    def query(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or ())
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
