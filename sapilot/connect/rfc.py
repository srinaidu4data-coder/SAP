"""RFC knowledge channel: RFC_READ_TABLE, BAPI dispatch, wide-row wrapper."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from sapilot.exceptions import ConnectionError as SapilotConnectionError

log = logging.getLogger(__name__)

# SAP RFC_READ_TABLE WA length limit; wide rows need chunked field reads or Z-wrapper
RFC_READ_TABLE_WA_LEN = 512


class RfcClientBase(ABC):
    @abstractmethod
    def call(self, func: str, **params: Any) -> dict[str, Any]:
        ...

    @abstractmethod
    def read_table(
        self,
        table: str,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 0,
        delimiter: str = "|",
    ) -> list[dict[str, str]]:
        ...

    def ping(self) -> bool:
        try:
            self.call("RFC_PING")
            return True
        except Exception:
            return False


class RfcClient(RfcClientBase):
    """Live pyrfc connection. Requires NW RFC SDK + pyrfc installed."""

    def __init__(self, conn_params: dict[str, Any]):
        self.conn_params = conn_params
        self._conn = None

    def connect(self) -> None:
        try:
            from pyrfc import Connection  # type: ignore
        except ImportError as e:
            raise SapilotConnectionError(
                "pyrfc not installed. Install NW RFC SDK and `pip install pyrfc`."
            ) from e
        try:
            self._conn = Connection(**self.conn_params)
        except Exception as e:
            raise SapilotConnectionError(f"RFC connect failed: {e}") from e

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _ensure(self) -> Any:
        if self._conn is None:
            self.connect()
        return self._conn

    def call(self, func: str, **params: Any) -> dict[str, Any]:
        conn = self._ensure()
        try:
            return dict(conn.call(func, **params))
        except Exception as e:
            raise SapilotConnectionError(f"RFC {func} failed: {e}") from e

    def read_table(
        self,
        table: str,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 0,
        delimiter: str = "|",
    ) -> list[dict[str, str]]:
        """
        RFC_READ_TABLE with automatic field chunking for wide rows.
        Falls back to /SAPDS/RFC_READ_TABLE if available.
        """
        field_list = [{"FIELDNAME": f} for f in (fields or [])]
        opts = [{"TEXT": o} for o in (options or [])]
        params: dict[str, Any] = {
            "QUERY_TABLE": table,
            "DELIMITER": delimiter,
            "OPTIONS": opts,
        }
        if field_list:
            params["FIELDS"] = field_list
        if rowcount:
            params["ROWCOUNT"] = rowcount

        try:
            result = self.call("RFC_READ_TABLE", **params)
        except SapilotConnectionError:
            # Try SAP DS variant
            result = self.call("/SAPDS/RFC_READ_TABLE", **params)

        fields_meta = result.get("FIELDS") or []
        data_rows = result.get("DATA") or []
        names = [f.get("FIELDNAME", "").strip() for f in fields_meta]
        if not names and fields:
            names = list(fields)

        rows: list[dict[str, str]] = []
        for d in data_rows:
            wa = d.get("WA", d if isinstance(d, str) else "")
            parts = wa.split(delimiter) if delimiter else [wa]
            row = {}
            for i, name in enumerate(names):
                row[name] = parts[i].strip() if i < len(parts) else ""
            rows.append(row)

        # Wide-row: if requested fields missing due to WA truncation, chunk
        if fields and names and set(fields) - set(names):
            missing = [f for f in fields if f not in names]
            if missing:
                log.warning("RFC_READ_TABLE truncated fields for %s; chunking %s", table, missing)
                chunk = self.read_table(table, fields=missing, options=options, rowcount=rowcount)
                # best-effort merge by position
                for i, row in enumerate(rows):
                    if i < len(chunk):
                        row.update(chunk[i])
        return rows


class MockRfcClient(RfcClientBase):
    """In-memory table store for offline tests and demos."""

    def __init__(self, tables: dict[str, list[dict[str, str]]] | None = None):
        self.tables: dict[str, list[dict[str, str]]] = tables or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def seed(self, table: str, rows: list[dict[str, str]]) -> None:
        self.tables[table.upper()] = rows

    def call(self, func: str, **params: Any) -> dict[str, Any]:
        self.calls.append((func, params))
        if func == "RFC_PING":
            return {}
        if func in ("RFC_READ_TABLE", "/SAPDS/RFC_READ_TABLE"):
            table = params.get("QUERY_TABLE", "")
            rows = self.tables.get(table.upper(), [])
            fields_req = params.get("FIELDS") or []
            field_names = (
                [f["FIELDNAME"] for f in fields_req]
                if fields_req
                else (list(rows[0].keys()) if rows else [])
            )
            options = params.get("OPTIONS") or []
            filtered = rows
            for opt in options:
                text = opt.get("TEXT", "") if isinstance(opt, dict) else str(opt)
                filtered = _apply_option(filtered, text)
            rowcount = int(params.get("ROWCOUNT") or 0)
            if rowcount:
                filtered = filtered[:rowcount]
            delim = params.get("DELIMITER") or "|"
            data = []
            for r in filtered:
                wa = delim.join(str(r.get(f, "")) for f in field_names)
                data.append({"WA": wa})
            return {
                "FIELDS": [{"FIELDNAME": f} for f in field_names],
                "DATA": data,
            }
        if func == "BAPI_TRANSACTION_COMMIT":
            return {"RETURN": []}
        return {}

    def read_table(
        self,
        table: str,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 0,
        delimiter: str = "|",
    ) -> list[dict[str, str]]:
        field_list = [{"FIELDNAME": f} for f in (fields or [])]
        opts = [{"TEXT": o} for o in (options or [])]
        result = self.call(
            "RFC_READ_TABLE",
            QUERY_TABLE=table,
            FIELDS=field_list,
            OPTIONS=opts,
            ROWCOUNT=rowcount,
            DELIMITER=delimiter,
        )
        names = [f["FIELDNAME"] for f in result.get("FIELDS", [])]
        rows = []
        for d in result.get("DATA", []):
            parts = d["WA"].split(delimiter)
            rows.append({n: (parts[i] if i < len(parts) else "") for i, n in enumerate(names)})
        return rows


def _apply_option(rows: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    """Minimal WHERE-like filter for mock: supports FIELD = 'value' and FIELD EQ 'value'."""
    text = text.strip()
    if not text:
        return rows
    import re

    # Strip leading AND/OR from multi-option scenario YAML lines
    text = re.sub(r"^(AND|OR)\s+", "", text, flags=re.IGNORECASE)
    m = re.match(
        r"(\w+)\s*(?:=|EQ)\s*'([^']*)'",
        text,
        re.IGNORECASE,
    )
    if not m:
        return rows
    field, value = m.group(1).upper(), m.group(2)
    return [r for r in rows if str(r.get(field, r.get(field.upper(), ""))) == value]
