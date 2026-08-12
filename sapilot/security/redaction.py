"""Redaction gate — fail closed. No payload leaves the process unredacted."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sapilot.exceptions import RedactionError

# Field IDs / names that always redact (SAP technical names)
SENSITIVE_FIELD_IDS = frozenset(
    {
        "BANKN",
        "BANKL",
        "BKREF",
        "IBAN",
        "KOINH",  # account holder
        "STCD1",
        "STCD2",
        "STCD3",
        "STCD4",
        "TAXNUM",
        "TAXNUMXL",
        "SSN",
        "PERNR",
        "PASSWORD",
        "PASSWD",
        "PWD",
        "ROUTING",
        "ABA",
        "ACCOUNT",
        "ACCNO",
        "CREDIT_CARD",
    }
)

# Technical IDs that look numeric but must NOT be free-text redacted
SAFE_FIELD_IDS = frozenset(
    {
        "LIFNR",
        "KUNNR",
        "BUKRS",
        "BELNR",
        "GJAHR",
        "BUZEI",
        "MANDT",
        "LAUFD",
        "LAUFI",
        "ZLSCH",
        "ZBUKR",
        "HBKID",
        "HKTID",
        "WAERS",
        "LAND1",
        "ZTERM",
        "MSGNR",
        "ARBGB",
        "TABNAME",
        "FIELDNAME",
        "VBLNR",
        "GJAHR",
        "AUGBL",
        "HKONT",
    }
)

# Regex patterns for free text
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")),
    # Account-like digit runs — exclude SAP dates YYYYMMDD (20xxxx)
    ("BANKN", re.compile(r"\b(?!20\d{6}\b)\d{10,17}\b")),
    ("ROUTING", re.compile(r"\b(?!20\d{6}\b)\d{9}\b")),  # US ABA (not dates)
    ("TAX_ID", re.compile(r"\b\d{2}-\d{7}\b")),  # EIN
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]


class RedactionGate:
    """
    Masks sensitive values with stable tokens «KIND_hash» so relational reasoning survives.
    Same raw value → same token within a gate instance (and across if salt fixed).
    """

    def __init__(self, salt: str = "sapilot", fail_closed: bool = True):
        self.salt = salt
        self.fail_closed = fail_closed
        self._token_map: dict[str, str] = {}  # token → original (local only, never exported)
        self._value_map: dict[str, str] = {}  # original → token

    def _token_for(self, kind: str, value: str) -> str:
        if value in self._value_map:
            return self._value_map[value]
        digest = hashlib.sha256(f"{self.salt}:{kind}:{value}".encode()).hexdigest()[:4]
        token = f"«{kind}_{digest}»"
        self._value_map[value] = token
        self._token_map[token] = value
        return token

    def redact_text(self, text: str | None) -> str:
        if text is None:
            return ""
        out = str(text)
        for kind, pat in _PATTERNS:
            def repl(m: re.Match[str], _k: str = kind) -> str:
                return self._token_for(_k, m.group(0))

            out = pat.sub(repl, out)
        return out

    def redact_field(self, field_name: str, value: Any) -> Any:
        if value is None:
            return None
        key = field_name.upper().split("-")[-1].split("/")[-1]
        if key in SENSITIVE_FIELD_IDS or any(
            s == key or key.endswith(s) for s in SENSITIVE_FIELD_IDS
        ):
            return self._token_for(key[:8], str(value))
        # SAP technical keys: pass through (digit regex would false-positive on LIFNR etc.)
        if key in SAFE_FIELD_IDS:
            return value
        if isinstance(value, str):
            return self.redact_text(value)
        return value

    def redact_dict(self, data: dict[str, Any], path: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                result[k] = self.redact_dict(v, f"{path}.{k}")
            elif isinstance(v, list):
                result[k] = [
                    self.redact_dict(i, path) if isinstance(i, dict) else self.redact_field(k, i)
                    for i in v
                ]
            else:
                result[k] = self.redact_field(str(k), v)
        return result

    def redact_payload(self, payload: Any) -> Any:
        """Public egress gate. Fail closed on unexpected types when configured."""
        try:
            if payload is None:
                return None
            if isinstance(payload, str):
                return self.redact_text(payload)
            if isinstance(payload, dict):
                return self.redact_dict(payload)
            if isinstance(payload, list):
                return [self.redact_payload(x) for x in payload]
            if isinstance(payload, (int, float, bool)):
                return payload
            # pydantic models
            if hasattr(payload, "model_dump"):
                return self.redact_dict(payload.model_dump(mode="json"))
            if self.fail_closed:
                raise RedactionError(f"Unredactable payload type: {type(payload)}")
            return self.redact_text(str(payload))
        except RedactionError:
            raise
        except Exception as e:
            if self.fail_closed:
                raise RedactionError(f"Redaction failed closed: {e}") from e
            return {}

    def reveal_local(self, token: str) -> str | None:
        """Local-only reverse lookup. Never call on egress path."""
        return self._token_map.get(token)
