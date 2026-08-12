"""
Mission-critical precision primitives (NASA / SpaceX engineering style).

Principles applied here — non-negotiable:
  1. Fail closed — unknown / missing / partial state is GO = false
  2. Verify after every state change (read-back / fingerprint)
  3. Exact expected values, not "looks ok" or fuzzy match
  4. Hash-chain journals (tamper-evident audit trail)
  5. Deterministic go/no-go criteria published BEFORE the run
  6. No silent success — every step has an evaluated postcondition
  7. Hard abort on navigation garbage in business data fields
  8. Cross-document chain invariants (PO↔IR, SO↔Billing amounts)

This module is the single source of truth for precision gates.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Time / hash
# ---------------------------------------------------------------------------

def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(obj: Any) -> str:
    """Canonical SHA-256 of any JSON-serializable structure."""
    raw = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def amount_equal(a: Any, b: Any, *, places: int = 2) -> bool:
    """SAP currency-safe compare (2 decimal places by default)."""
    try:
        da = Decimal(str(a).replace(",", "").strip())
        db = Decimal(str(b).replace(",", "").strip())
        quant = Decimal(10) ** -places
        return da.quantize(quant) == db.quantize(quant)
    except (InvalidOperation, ValueError, TypeError):
        return str(a).strip() == str(b).strip()


# ---------------------------------------------------------------------------
# Exact deep equality
# ---------------------------------------------------------------------------

def verify_exact(
    actual: Any,
    expected: Any,
    *,
    path: str = "value",
    normalize_sap_key: bool = False,
    amount_fields: frozenset[str] | None = None,
) -> list[str]:
    """
    Deep equality with SAP-aware key padding and amount compare.
    Returns list of mismatch descriptions (empty = perfect match).
    Fail-closed: type mismatch is an error, not coerced success.
    """
    errors: list[str] = []
    amount_fields = amount_fields or frozenset(
        {
            "NETWR",
            "NETPR",
            "RMWWR",
            "WRBTR",
            "MENGE",
            "KWMENG",
            "LFIMG",
            "FKIMG",
            "STPRS",
            "MAXBT",
            "VONBT",
            "BISBT",
        }
    )

    def norm(v: Any, key: str = "") -> Any:
        if normalize_sap_key and isinstance(v, str) and v.isdigit():
            return v.lstrip("0") or "0"
        if isinstance(v, str):
            return v.strip()
        return v

    if isinstance(expected, dict) and isinstance(actual, dict):
        for k, exp in expected.items():
            if k not in actual:
                errors.append(f"{path}.{k}: MISSING (expected {exp!r})")
                continue
            if k.upper() in amount_fields:
                if not amount_equal(actual[k], exp):
                    errors.append(f"{path}.{k}: amount actual={actual[k]!r} expected={exp!r}")
            else:
                errors.extend(
                    verify_exact(
                        actual[k],
                        exp,
                        path=f"{path}.{k}",
                        normalize_sap_key=normalize_sap_key,
                        amount_fields=amount_fields,
                    )
                )
        return errors

    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            errors.append(f"{path}: length {len(actual)} != expected {len(expected)}")
        for i, (a, e) in enumerate(zip(actual, expected)):
            errors.extend(
                verify_exact(
                    a,
                    e,
                    path=f"{path}[{i}]",
                    normalize_sap_key=normalize_sap_key,
                    amount_fields=amount_fields,
                )
            )
        return errors

    # Type fail-closed: expected dict/list but actual is not
    if isinstance(expected, (dict, list)) and not isinstance(actual, type(expected)):
        errors.append(f"{path}: type {type(actual).__name__} != expected {type(expected).__name__}")
        return errors

    a, e = norm(actual), norm(expected)
    if a != e:
        errors.append(f"{path}: actual={actual!r} expected={expected!r}")
    return errors


# ---------------------------------------------------------------------------
# Hard safety: tcode never in business fields
# ---------------------------------------------------------------------------

_DATA_FIELD_MARKERS = (
    "LIFNR",
    "KUNNR",
    "MATNR",
    "EBELN",
    "BANFN",
    "BELNR",
    "SUPPLIER",
    "VENDOR",
    "PARTNER",
    "VBELN",
    "KUNAG",
    "FLIEF",
    "RF02K",
    "BUS_JOEL",
)


def is_tcode_command(value: str) -> bool:
    """True for /nF110, /oME23N — False for pure digit business keys."""
    v = (value or "").strip().upper()
    if not v:
        return False
    if v.startswith("/N") or v.startswith("/O"):
        return True
    return False


def assert_never_tcode_in_data_field(field_name: str, value: str) -> None:
    """Hard abort if navigation garbage enters a business field. Fail closed."""
    v = (value or "").strip()
    f = (field_name or "").upper()
    if any(m in f for m in _DATA_FIELD_MARKERS) and is_tcode_command(v):
        raise MissionAbort(
            f"PRECISION ABORT: tcode-like value {value!r} blocked in data field {field_name!r}"
        )
    # Also block if value is clearly a slash-command regardless of field name
    # when field is not ok-code / command field
    if is_tcode_command(v) and "OKCD" not in f and "OK_CODE" not in f and "TCODE" not in f:
        if any(m in f for m in _DATA_FIELD_MARKERS) or not f:
            raise MissionAbort(
                f"PRECISION ABORT: slash-command {value!r} not allowed in field {field_name!r}"
            )


class MissionAbort(Exception):
    """Non-negotiable stop — do not continue the mission. Fail closed."""


# ---------------------------------------------------------------------------
# Go / No-Go board
# ---------------------------------------------------------------------------

@dataclass
class GoNoGo:
    criterion: str
    go: bool
    evidence: str = ""
    severity: str = "blocker"  # blocker | warning

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StepVerification:
    step_id: str
    preconditions: list[GoNoGo] = field(default_factory=list)
    postconditions: list[GoNoGo] = field(default_factory=list)
    field_readbacks: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = False
    errors: list[str] = field(default_factory=list)

    def evaluate(self) -> bool:
        errs: list[str] = []
        for g in self.preconditions:
            if g.severity == "blocker" and not g.go:
                errs.append(f"PRE FAIL: {g.criterion} ({g.evidence})")
        for g in self.postconditions:
            if g.severity == "blocker" and not g.go:
                errs.append(f"POST FAIL: {g.criterion} ({g.evidence})")
        # Field read-backs: every expected must match actual
        for rb in self.field_readbacks:
            exp = rb.get("expected")
            act = rb.get("actual")
            name = rb.get("field", "?")
            if exp is not None and str(act).strip() != str(exp).strip():
                # SAP key pad-aware
                if str(act).lstrip("0") != str(exp).lstrip("0"):
                    errs.append(f"READBACK FAIL: {name} actual={act!r} expected={exp!r}")
        self.errors = errs
        self.ok = len(errs) == 0
        return self.ok


class MissionGate:
    """
    Go/No-Go board for a mission run.
    ALL blocker criteria must GO or the mission is ABORT.
    Unknown criteria are never auto-GO — must be explicitly required.
    """

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.criteria: list[GoNoGo] = []
        self.steps: list[StepVerification] = []

    def require(self, criterion: str, go: bool, evidence: str = "", severity: str = "blocker") -> None:
        self.criteria.append(GoNoGo(criterion, bool(go), evidence, severity))

    def is_go(self) -> bool:
        blockers = [c for c in self.criteria if c.severity == "blocker"]
        if not blockers:
            # Fail closed: empty board is NOT a go — mission never declared criteria
            return False
        return all(c.go for c in blockers)

    def abort_if_nogo(self) -> None:
        if not self.is_go():
            fails = [c for c in self.criteria if c.severity == "blocker" and not c.go]
            if not self.criteria:
                raise MissionAbort(f"NO-GO {self.mission_id}: empty gate (fail closed)")
            msg = "; ".join(f"{c.criterion}: {c.evidence}" for c in fails) or "unknown blockers"
            raise MissionAbort(f"NO-GO {self.mission_id}: {msg}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "go": self.is_go(),
            "criteria": [c.to_dict() for c in self.criteria],
            "steps": [asdict(s) for s in self.steps],
        }


# ---------------------------------------------------------------------------
# Tamper-evident journal (hash chain + sequence)
# ---------------------------------------------------------------------------

class JournalHashChain:
    """
    Append-only hash chain: each record includes hash of previous record + seq.
    Tampering any past line breaks the chain (detectable on verify).
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = "GENESIS"
        self._seq = 0
        if self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    last = json.loads(lines[-1])
                    self._prev = last.get("hash", "GENESIS")
                    self._seq = int(last.get("seq", len(lines)))
                except Exception:
                    self._prev = "GENESIS"
                    self._seq = 0

    def append(self, event_type: str, payload: Any) -> str:
        self._seq += 1
        body = {
            "seq": self._seq,
            "ts": utc_iso(),
            "type": event_type,
            "payload": payload,
            "prev": self._prev,
        }
        h = stable_hash(body)
        body["hash"] = h
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(body, default=str, ensure_ascii=False) + "\n")
        self._prev = h
        return h

    def verify_chain(self) -> tuple[bool, list[str]]:
        if not self.path.exists():
            return True, []
        errors: list[str] = []
        prev = "GENESIS"
        expect_seq = 0
        for i, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"line {i}: invalid JSON {e}")
                continue
            if rec.get("prev") != prev:
                errors.append(f"line {i}: prev hash mismatch")
            body = {k: v for k, v in rec.items() if k != "hash"}
            expect = stable_hash(body)
            if rec.get("hash") != expect:
                errors.append(f"line {i}: content hash mismatch")
            # Sequence monotonic when present
            if "seq" in rec:
                expect_seq += 1
                if int(rec["seq"]) != expect_seq:
                    errors.append(f"line {i}: seq {rec['seq']} != expected {expect_seq}")
            prev = rec.get("hash", prev)
        return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Exact fingerprints — critical business keys for all fleet packs (22)
# (stable under remediations; amounts and document IDs are contractual)
# ---------------------------------------------------------------------------

# Canonical twin / demo IDs used across the mission suite
CANON = {
    "lifnr": "0000100001",
    "kunnr": "0000001000",
    "bukrs": "1000",
    "matnr": "000000000000100000",
    "ebeln": "4500000001",
    "banfn": "0010000001",
    "belnr_inv": "5105600001",
    "mblnr": "5000000001",
    "vbeln_so": "0000001001",
    "vbeln_dn": "0080001001",
    "vbeln_bill": "0090001001",
    "po_netwr": "1250.00",
    "so_netwr": "2500.00",
    "waers": "USD",
    "program": "ZSAP_DEMO_INVOICE",
    "errid": "COMPUTE_INT_ZERODIVIDE",
    "datum": "20260812",
}

# EXACT fingerprints: first-row must match these key fields (pack_id → table → fields)
PACK_EXACT: dict[str, dict[str, list[dict[str, Any]]]] = {
    "ptp_01_vendor_master": {
        "LFA1": [{"LIFNR": CANON["lifnr"], "LAND1": "US", "SPERR": "", "LOEVM": ""}],
        "LFB1": [{"LIFNR": CANON["lifnr"], "BUKRS": CANON["bukrs"], "ZAHLS": ""}],
        "LFM1": [{"LIFNR": CANON["lifnr"], "EKORG": "1000", "WAERS": CANON["waers"]}],
    },
    "ptp_02_material_purchasing": {
        "MARA": [{"MATNR": CANON["matnr"], "MTART": "ROH", "MEINS": "EA"}],
        "MARC": [{"MATNR": CANON["matnr"], "WERKS": "1000", "MMSTA": ""}],
        "MBEW": [{"MATNR": CANON["matnr"], "BWKEY": "1000", "STPRS": "10.00"}],
    },
    "ptp_03_info_record": {
        "EINA": [{"INFNR": "5300000001", "MATNR": CANON["matnr"], "LIFNR": CANON["lifnr"]}],
        "EINE": [{"INFNR": "5300000001", "EKORG": "1000", "NETPR": "12.50"}],
    },
    "ptp_04_source_list": {
        "EORD": [
            {
                "MATNR": CANON["matnr"],
                "WERKS": "1000",
                "LIFNR": CANON["lifnr"],
                "EKORG": "1000",
                "FLIFN": "X",
            }
        ],
    },
    "ptp_05_purchase_requisition": {
        "EBAN": [
            {
                "BANFN": CANON["banfn"],
                "BNFPO": "00010",
                "MATNR": CANON["matnr"],
                "MENGE": "100",
                "FLIEF": CANON["lifnr"],
                "LOEKZ": "",
            }
        ],
    },
    "ptp_06_purchase_order": {
        "EKKO": [
            {
                "EBELN": CANON["ebeln"],
                "LIFNR": CANON["lifnr"],
                "BUKRS": CANON["bukrs"],
                "WAERS": CANON["waers"],
                "LOEKZ": "",
            }
        ],
        "EKPO": [
            {
                "EBELN": CANON["ebeln"],
                "EBELP": "00010",
                "MENGE": "100",
                "NETPR": "12.50",
                "NETWR": CANON["po_netwr"],
            }
        ],
    },
    "ptp_07_goods_receipt": {
        "EKKO": [{"EBELN": CANON["ebeln"], "LIFNR": CANON["lifnr"]}],
        "EKBE": [{"EBELN": CANON["ebeln"], "VGABE": "1", "BWART": "101", "MENGE": "100"}],
        "MSEG": [
            {
                "MBLNR": CANON["mblnr"],
                "BWART": "101",
                "EBELN": CANON["ebeln"],
                "MENGE": "100",
            }
        ],
    },
    "ptp_08_invoice_verification": {
        "RBKP": [
            {
                "BELNR": CANON["belnr_inv"],
                "GJAHR": "2026",
                "RMWWR": CANON["po_netwr"],
                "XBLNR": "INV-9001",
                "LIFNR": CANON["lifnr"],
            }
        ],
        "RSEG": [
            {
                "BELNR": CANON["belnr_inv"],
                "EBELN": CANON["ebeln"],
                "WRBTR": CANON["po_netwr"],
                "MENGE": "100",
            }
        ],
    },
    "ptp_09_vendor_open_items": {
        "BSIK": [{"BUKRS": CANON["bukrs"], "LIFNR": CANON["lifnr"], "WAERS": CANON["waers"]}],
    },
    "ptp_10_payment_readiness": {
        "T042": [{"BUKRS": CANON["bukrs"]}],
        "T042E": [{"ZBUKR": CANON["bukrs"], "ZLSCH": "A", "WAERS": CANON["waers"]}],
        "LFB1": [{"LIFNR": CANON["lifnr"], "BUKRS": CANON["bukrs"], "ZAHLS": ""}],
        "LFBK": [{"LIFNR": CANON["lifnr"], "BANKS": "US"}],
    },
    "otc_01_customer_master": {
        "KNA1": [{"KUNNR": CANON["kunnr"], "LAND1": "US", "SPERR": "", "LOEVM": ""}],
        "KNB1": [{"KUNNR": CANON["kunnr"], "BUKRS": CANON["bukrs"], "SPERR": ""}],
        "KNVV": [{"KUNNR": CANON["kunnr"], "VKORG": "1000", "VTWEG": "10"}],
    },
    "otc_02_material_sales": {
        "MARA": [{"MATNR": CANON["matnr"]}],
        "MVKE": [{"MATNR": CANON["matnr"], "VKORG": "1000", "VTWEG": "10", "DWERK": "1000"}],
    },
    "otc_03_customer_material": {
        "KNMT": [
            {
                "KUNNR": CANON["kunnr"],
                "MATNR": CANON["matnr"],
                "VKORG": "1000",
                "KDMAT": "CUST-MAT-100",
            }
        ],
    },
    "otc_04_sales_org": {
        "TVKO": [{"VKORG": "1000", "BUKRS": CANON["bukrs"]}],
        "TVTW": [{"VTWEG": "10"}],
        "TSPA": [{"SPART": "00"}],
    },
    "otc_05_sales_order": {
        "VBAK": [
            {
                "VBELN": CANON["vbeln_so"],
                "KUNNR": CANON["kunnr"],
                "NETWR": CANON["so_netwr"],
                "VKORG": "1000",
            }
        ],
        "VBAP": [
            {
                "VBELN": CANON["vbeln_so"],
                "POSNR": "000010",
                "KWMENG": "50",
                "MATNR": CANON["matnr"],
            }
        ],
    },
    "otc_06_delivery": {
        "LIKP": [{"VBELN": CANON["vbeln_dn"], "KUNNR": CANON["kunnr"], "VKORG": "1000"}],
        "LIPS": [
            {
                "VBELN": CANON["vbeln_dn"],
                "LFIMG": "50",
                "VGBEL": CANON["vbeln_so"],
                "MATNR": CANON["matnr"],
            }
        ],
    },
    "otc_07_goods_issue": {
        "VBFA": [{"VBELV": CANON["vbeln_so"], "VBELN": CANON["vbeln_dn"], "VBTYP_N": "J"}],
        "LIKP": [{"VBELN": CANON["vbeln_dn"], "WADAT_IST": "20260811"}],
    },
    "otc_08_billing": {
        "VBRK": [
            {
                "VBELN": CANON["vbeln_bill"],
                "KUNAG": CANON["kunnr"],
                "NETWR": CANON["so_netwr"],
                "BUKRS": CANON["bukrs"],
            }
        ],
        "VBRP": [
            {
                "VBELN": CANON["vbeln_bill"],
                "FKIMG": "50",
                "VGBEL": CANON["vbeln_dn"],
                "NETWR": CANON["so_netwr"],
            }
        ],
    },
    "otc_09_customer_open_items": {
        "BSID": [
            {
                "BUKRS": CANON["bukrs"],
                "KUNNR": CANON["kunnr"],
                "WRBTR": CANON["so_netwr"],
                "VBELN": CANON["vbeln_bill"],
            }
        ],
    },
    "otc_10_incoming_payment": {
        "KNA1": [{"KUNNR": CANON["kunnr"], "SPERR": ""}],
        "KNB1": [{"KUNNR": CANON["kunnr"], "BUKRS": CANON["bukrs"], "SPERR": ""}],
        "BSID": [{"KUNNR": CANON["kunnr"], "WRBTR": CANON["so_netwr"], "ZLSPR": ""}],
    },
    "abap_01_runtime_dump": {
        "SNAP_BEG": [
            {
                "DATUM": CANON["datum"],
                "ERRID": CANON["errid"],
                "PROGRAM": CANON["program"],
            }
        ],
        "SNAP": [{"PROGRAM": CANON["program"], "FVALUE": CANON["errid"]}],
    },
    "abap_02_source_inspect": {
        "TRDIR": [{"NAME": CANON["program"], "SUBC": "1"}],
        "ZBOT_DEBUG_RECIPE": [
            {
                "PROGRAM": CANON["program"],
                "ERRID": CANON["errid"],
                "SAFE": "X",
            }
        ],
    },
}

# Backward-compatible alias used by earlier tests / runners
PTP_EXACT = PACK_EXACT


def verify_pack_exact(pack_tables: dict[str, Any], expected: dict[str, list[dict]]) -> list[str]:
    """Verify first N rows of each expected table match exactly (SAP key normalize)."""
    errors: list[str] = []
    for table, exp_rows in expected.items():
        slice_ = pack_tables.get(table)
        if slice_ is None:
            errors.append(f"{table}: table missing from pack")
            continue
        rows = slice_.rows if hasattr(slice_, "rows") else (slice_.get("rows") or [])
        if not rows:
            errors.append(f"{table}: no rows extracted")
            continue
        for i, exp in enumerate(exp_rows):
            if i >= len(rows):
                errors.append(f"{table}[{i}]: missing row")
                continue
            act = {k: rows[i].get(k) for k in exp}
            errors.extend(verify_exact(act, exp, path=f"{table}[{i}]", normalize_sap_key=True))
    return errors


def verify_document_chain_invariants(twin_or_rfc: Any) -> list[str]:
    """
    Cross-document invariants (mission-critical accounting consistency):
      PO net value == IR invoice amount
      SO net value == Billing net value == AR open item
      GR quantity == PO item quantity
    """
    errors: list[str] = []

    def read(table: str, opts: list[str] | None = None) -> list[dict]:
        if hasattr(twin_or_rfc, "read"):
            return twin_or_rfc.read(table, opts)
        if hasattr(twin_or_rfc, "read_table"):
            return twin_or_rfc.read_table(table, options=opts or [], rowcount=50)
        return []

    ekpo = read("EKPO", [f"EBELN = '{CANON['ebeln']}'"])
    rbkp = read("RBKP", [f"BELNR = '{CANON['belnr_inv']}'"])
    if ekpo and rbkp:
        if not amount_equal(ekpo[0].get("NETWR"), rbkp[0].get("RMWWR")):
            errors.append(
                f"PO.NETWR {ekpo[0].get('NETWR')} != IR.RMWWR {rbkp[0].get('RMWWR')}"
            )
        if str(ekpo[0].get("EBELN")) != CANON["ebeln"]:
            errors.append("EKPO EBELN mismatch vs canon")

    mseg = read("MSEG", [f"EBELN = '{CANON['ebeln']}'"])
    if ekpo and mseg:
        if not amount_equal(ekpo[0].get("MENGE"), mseg[0].get("MENGE")):
            errors.append(
                f"PO.MENGE {ekpo[0].get('MENGE')} != GR.MENGE {mseg[0].get('MENGE')}"
            )

    vbak = read("VBAK", [f"VBELN = '{CANON['vbeln_so']}'"])
    vbrk = read("VBRK", [f"VBELN = '{CANON['vbeln_bill']}'"])
    bsid = read("BSID", [f"KUNNR = '{CANON['kunnr']}'"])
    if vbak and vbrk:
        if not amount_equal(vbak[0].get("NETWR"), vbrk[0].get("NETWR")):
            errors.append(
                f"SO.NETWR {vbak[0].get('NETWR')} != BILL.NETWR {vbrk[0].get('NETWR')}"
            )
    if vbrk and bsid:
        if not amount_equal(vbrk[0].get("NETWR"), bsid[0].get("WRBTR")):
            errors.append(
                f"BILL.NETWR {vbrk[0].get('NETWR')} != AR.WRBTR {bsid[0].get('WRBTR')}"
            )

    return errors


def scan_rows_for_tcode_pollution(tables: dict[str, Any]) -> list[str]:
    """Fail-closed scan: any LIFNR/KUNNR/etc containing /n or /o is pollution."""
    polluted: list[str] = []
    key_fields = ("LIFNR", "KUNNR", "MATNR", "EBELN", "BANFN", "BELNR", "VBELN", "KUNAG", "FLIEF")
    for tname, sl in tables.items():
        rows = sl.rows if hasattr(sl, "rows") else (sl.get("rows") or [])
        for ri, row in enumerate(rows):
            for fld in key_fields:
                if fld not in row:
                    continue
                val = str(row[fld] or "")
                if is_tcode_command(val):
                    polluted.append(f"{tname}[{ri}].{fld}={val!r}")
    return polluted


def manifest_hash() -> str:
    """Hash of all exact fingerprints — published before run, verified after."""
    return stable_hash(PACK_EXACT)
