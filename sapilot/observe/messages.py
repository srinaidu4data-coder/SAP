"""Status bar capture + T100 resolution + long text."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sapilot.schemas import SapMessage

if TYPE_CHECKING:
    from sapilot.connect.rfc import RfcClientBase


# Common status bar patterns: "E: No valid payment method" or "Message FZ 123"
_MSG_RE = re.compile(
    r"(?:^|\s)(?P<ty>[EWIASX])[:\s]+(?:(?P<id>[A-Z0-9_/]{2,20})\s*(?P<no>\d{3})[:\s]*)?(?P<text>.*)$",
    re.IGNORECASE,
)
_MSG_RE2 = re.compile(
    r"Message\s+(?P<id>[A-Z0-9_/]+)\s+(?P<no>\d{3})",
    re.IGNORECASE,
)


def parse_status_bar(text: str) -> SapMessage:
    raw = (text or "").strip()
    msg = SapMessage(raw_status_bar=raw, short_text=raw)
    if not raw:
        return msg

    m2 = _MSG_RE2.search(raw)
    if m2:
        msg.msgid = m2.group("id").upper()
        msg.msgno = m2.group("no").zfill(3)

    m = _MSG_RE.match(raw)
    if m:
        msg.msgty = m.group("ty").upper()
        if m.group("id"):
            msg.msgid = m.group("id").upper()
        if m.group("no"):
            msg.msgno = m.group("no").zfill(3)
        if m.group("text"):
            msg.short_text = m.group("text").strip() or raw
    elif raw:
        # Infer type from first char conventions
        if raw[0].upper() in "EWIASX" and len(raw) > 2 and raw[1] in ": ":
            msg.msgty = raw[0].upper()
            msg.short_text = raw[2:].strip()
    return msg


class MessageResolver:
    """Resolve message short/long text from T100 / DOKHL via RFC."""

    def __init__(self, rfc: RfcClientBase, spras: str = "E"):
        self.rfc = rfc
        self.spras = spras
        self._cache: dict[str, SapMessage] = {}

    def resolve(
        self,
        msgid: str,
        msgno: str,
        msgty: str = "",
        msgv1: str = "",
        msgv2: str = "",
        msgv3: str = "",
        msgv4: str = "",
        raw_status_bar: str = "",
    ) -> SapMessage:
        key = f"{msgid}/{msgno}/{self.spras}"
        base = self._cache.get(key)
        if base is None:
            base = self._read_t100(msgid, msgno)
            self._cache[key] = base

        short = base.short_text
        # Apply & placeholders
        for i, v in enumerate([msgv1, msgv2, msgv3, msgv4], start=1):
            short = short.replace(f"&{i}", v).replace("&", v, 1) if v else short.replace(f"&{i}", "")

        long_text = base.long_text or self._read_long_text(msgid, msgno)
        return SapMessage(
            msgty=msgty or base.msgty,
            msgid=msgid,
            msgno=msgno.zfill(3),
            msgv1=msgv1,
            msgv2=msgv2,
            msgv3=msgv3,
            msgv4=msgv4,
            short_text=short,
            long_text=long_text,
            raw_status_bar=raw_status_bar,
        )

    def resolve_status_bar(self, text: str) -> SapMessage:
        parsed = parse_status_bar(text)
        if parsed.msgid and parsed.msgno:
            return self.resolve(
                parsed.msgid,
                parsed.msgno,
                msgty=parsed.msgty,
                raw_status_bar=text,
            )
        return parsed

    def _read_t100(self, msgid: str, msgno: str) -> SapMessage:
        rows = self.rfc.read_table(
            "T100",
            fields=["SPRSL", "ARBGB", "MSGNR", "TEXT"],
            options=[f"ARBGB = '{msgid.upper()}'", f"AND MSGNR = '{msgno.zfill(3)}'"],
            rowcount=5,
        )
        # Prefer language
        chosen = None
        for r in rows:
            if r.get("SPRSL", r.get("SPRAS", "")) == self.spras:
                chosen = r
                break
        if not chosen and rows:
            chosen = rows[0]
        text = (chosen or {}).get("TEXT", "")
        return SapMessage(msgid=msgid.upper(), msgno=msgno.zfill(3), short_text=text)

    def _read_long_text(self, msgid: str, msgno: str) -> str:
        # Best-effort: some systems expose DOKTL / via function module
        try:
            result = self.rfc.call(
                "BAPI_MESSAGE_GETDETAIL",
                ID=msgid.upper(),
                NUMBER=msgno.zfill(3),
                LANGUAGE=self.spras,
                TEXTFORMAT="ASC",
            )
            texts = result.get("TEXT") or result.get("MESSAGE") or ""
            if isinstance(texts, list):
                return "\n".join(str(t) for t in texts)
            return str(texts)
        except Exception:
            return ""
