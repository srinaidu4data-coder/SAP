"""
Multi-table data gatherer + scenario debugger for Co-pilot.

1. Load scenario pack definition (which tables + keys)
2. Read all tables via knowledge channel (RFC/mock)
3. Run readiness / field checks
4. Optional payment diagnose engine
5. Produce DataPack used before scenario execution
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from sapilot.connect.rfc import RfcClientBase
from sapilot.diagnose.engine import PaymentRunDiagnosticEngine
from sapilot.know.tables import KnowledgeTables


def _packs_path() -> Path:
    return Path(__file__).with_name("scenario_packs.yaml")


def load_packs() -> dict[str, Any]:
    with open(_packs_path(), encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("packs") or {}


def list_packs() -> list[dict[str, str]]:
    packs = load_packs()
    out = []
    for pid, p in packs.items():
        out.append(
            {
                "id": pid,
                "title": p.get("title") or pid,
                "process": p.get("process") or "",
                "params": ",".join(p.get("params") or []),
                "tables": str(len(p.get("tables") or [])),
            }
        )
    return out


@dataclass
class Finding:
    severity: str  # blocker | warning | info
    table: str
    field: str
    message: str
    current: str | None = None
    key: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TableSlice:
    table: str
    options: list[str]
    channel: str
    count: int
    rows: list[dict[str, str]]
    required_rows: int = 0
    ok: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "options": self.options,
            "channel": self.channel,
            "count": self.count,
            "rows": self.rows[:50],  # cap for reports
            "row_total": self.count,
            "required_rows": self.required_rows,
            "ok": self.ok,
            "note": self.note,
        }


@dataclass
class DataPack:
    pack_id: str
    title: str
    params: dict[str, str]
    tables: dict[str, TableSlice] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    fbzp: dict[str, Any] = field(default_factory=dict)
    payment_diagnosis: dict[str, Any] = field(default_factory=dict)
    ready: bool = True
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "title": self.title,
            "params": self.params,
            "ready": self.ready,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "tables": {k: v.to_dict() for k, v in self.tables.items()},
            "fbzp_keys": {k: len(v) if isinstance(v, list) else 0 for k, v in self.fbzp.items()},
            "payment_diagnosis_summary": self.payment_diagnosis.get("summary", ""),
            "payment_findings": self.payment_diagnosis.get("findings", [])[:20],
        }


class ScenarioDataGatherer:
    """Access multiple tables and debug readiness for a scenario pack."""

    def __init__(self, rfc: RfcClientBase):
        self.rfc = rfc
        self.tables_api = KnowledgeTables(rfc)
        self.packs = load_packs()

    def gather(self, pack_id: str, params: dict[str, Any] | None = None) -> DataPack:
        if pack_id not in self.packs:
            # try alias: scenario id without prefix
            raise KeyError(
                f"Unknown data pack '{pack_id}'. Known: {', '.join(sorted(self.packs))}"
            )
        defn = self.packs[pack_id]
        raw_params = {str(k): str(v) if v is not None else "" for k, v in (params or {}).items()}
        # defaults for common PTP keys
        defaults = {
            "lifnr": "0000100001",
            "bukrs": "1000",
            "ekorg": "1000",
            "werks": "1000",
            "matnr": "000000000000100000",
            "banfn": "0010000001",
            "ebeln": "4500000001",
            "belnr_inv": "5105600001",
            "gjahr": "2026",
            "method": "A",
            "land1": "US",
            "laufd": "20260812",
            "laufi": "PTP001",
            # OTC
            "kunnr": "0000001000",
            "vkorg": "1000",
            "vtweg": "10",
            "spart": "00",
            "vbeln_so": "0000001001",
            "vbeln_dn": "0080001001",
            "vbeln_bill": "0090001001",
            # ABAP debug
            "datum": "20260812",
            "uname": "SV3_000349",
            "program": "ZSAP_DEMO_INVOICE",
            "abap_safe": "X",
        }
        p = {**defaults, **raw_params}
        # pad common SAP keys
        if p.get("lifnr") and p["lifnr"].isdigit():
            p["lifnr"] = p["lifnr"].zfill(10)
        if p.get("kunnr") and p["kunnr"].isdigit():
            p["kunnr"] = p["kunnr"].zfill(10)
        if p.get("matnr") and p["matnr"].isdigit():
            p["matnr"] = p["matnr"].zfill(18)
        for key in ("vbeln_so", "vbeln_dn", "vbeln_bill"):
            if p.get(key) and str(p[key]).isdigit():
                p[key] = str(p[key]).zfill(10)

        pack = DataPack(
            pack_id=pack_id,
            title=defn.get("title") or pack_id,
            params=p,
        )

        for tdef in defn.get("tables") or []:
            slice_ = self._read_table_def(tdef, p)
            pack.tables[tdef["table"]] = slice_
            if not slice_.ok:
                pack.findings.append(
                    Finding(
                        severity="blocker",
                        table=tdef["table"],
                        field="*",
                        message=slice_.note or f"{tdef['table']} required data missing",
                    )
                )
            elif tdef.get("warn_if_empty") and slice_.count == 0:
                pack.findings.append(
                    Finding(
                        severity="warning",
                        table=tdef["table"],
                        field="*",
                        message=tdef["warn_if_empty"],
                    )
                )

        for fdef in defn.get("field_checks") or []:
            pack.findings.extend(self._field_checks(fdef, pack.tables, p))

        for cdef in defn.get("custom_checks") or []:
            pack.findings.extend(self._custom_checks(cdef, pack.tables))

        if defn.get("use_fbzp"):
            pack.fbzp = self.tables_api.fbzp_chain_snapshot(
                p.get("bukrs", "1000"), p.get("method", "A"), p.get("land1", "US")
            )

        if defn.get("use_payment_diagnose"):
            report = PaymentRunDiagnosticEngine(self.tables_api).diagnose(
                company_code=p.get("bukrs", "1000"),
                payment_method=p.get("method", "A"),
                vendors=[p["lifnr"]] if p.get("lifnr") else None,
                land1=p.get("land1", "US"),
            )
            pack.payment_diagnosis = {
                "summary": report.summary,
                "findings": [f.model_dump(mode="json") for f in report.findings],
            }
            for f in report.findings:
                pack.findings.append(
                    Finding(
                        severity=f.severity,
                        table=f.cause_table,
                        field=f.cause_field,
                        message=f.symptom,
                        current=f.current_value,
                        key=f.cause_key,
                    )
                )

        blockers = [f for f in pack.findings if f.severity == "blocker"]
        warnings = [f for f in pack.findings if f.severity == "warning"]
        pack.ready = len(blockers) == 0
        pack.summary = (
            f"{pack.title}: {'READY' if pack.ready else 'NOT READY'} — "
            f"{len(pack.tables)} tables, {len(blockers)} blocker(s), {len(warnings)} warning(s)"
        )
        return pack

    def debug_message(
        self,
        symptom: str,
        params: dict[str, Any] | None = None,
    ) -> DataPack:
        """
        Debug helper: map free-text SAP symptom to ordered table checks (payment-oriented).
        """
        p = params or {}
        # Reuse payment pack + extra tables based on keywords
        pack_id = "ptp_10_payment_readiness"
        if re.search(r"purchase.?order|ekko|me2", symptom, re.I):
            pack_id = "ptp_06_purchase_order"
        elif re.search(r"goods.?receipt|migo|mseg", symptom, re.I):
            pack_id = "ptp_07_goods_receipt"
        elif re.search(r"invoice|miro|rbkp", symptom, re.I):
            pack_id = "ptp_08_invoice_verification"
        elif re.search(r"requisition|eban|me5", symptom, re.I):
            pack_id = "ptp_05_purchase_requisition"
        elif re.search(r"material|mara", symptom, re.I):
            pack_id = "ptp_02_material_purchasing"
        elif re.search(r"vendor|lifnr|xk0", symptom, re.I):
            pack_id = "ptp_01_vendor_master"
        elif re.search(r"dump|st22|zerodivide|runtime|short.?dump", symptom, re.I):
            pack_id = "abap_01_runtime_dump"
        elif re.search(r"se38|source|program|abap|breakpoint|debug", symptom, re.I):
            pack_id = "abap_02_source_inspect"

        pack = self.gather(pack_id, p)
        pack.findings.insert(
            0,
            Finding(
                severity="info",
                table="DEBUG",
                field="symptom",
                message=f"Debug routed symptom to pack '{pack_id}': {symptom[:200]}",
            ),
        )
        pack.summary = f"DEBUG → {pack.summary}"
        return pack

    def gather_many(self, pack_ids: list[str], params: dict[str, Any] | None = None) -> list[DataPack]:
        return [self.gather(pid, params) for pid in pack_ids]

    def _fmt(self, template: str, params: dict[str, str]) -> str:
        out = template
        for k, v in params.items():
            out = out.replace("{" + k + "}", v)
        return out

    def _read_table_def(self, tdef: dict[str, Any], params: dict[str, str]) -> TableSlice:
        table = tdef["table"]
        options = [self._fmt(o, params) for o in (tdef.get("options") or [])]
        rowcount = int(tdef.get("rowcount") or 200)
        rows = self.rfc.read_table(table, options=options or None, rowcount=rowcount)
        required = int(tdef.get("required_rows") or 0)
        ok = len(rows) >= required
        note = ""
        if not ok:
            note = tdef.get("missing_means") or f"Need >= {required} row(s), got {len(rows)}"
        return TableSlice(
            table=table,
            options=options,
            channel="rfc",
            count=len(rows),
            rows=rows,
            required_rows=required,
            ok=ok,
            note=note,
        )

    def _field_checks(
        self,
        fdef: dict[str, Any],
        slices: dict[str, TableSlice],
        params: dict[str, str],
    ) -> list[Finding]:
        findings: list[Finding] = []
        table = fdef.get("table", "")
        field = fdef.get("field", "")
        sl = slices.get(table)
        if not sl or not sl.rows:
            return findings
        severity = fdef.get("severity") or "warning"
        for row in sl.rows:
            val = str(row.get(field, "") or "").strip()
            if fdef.get("expect_empty") and val:
                findings.append(
                    Finding(
                        severity=severity,
                        table=table,
                        field=field,
                        message=fdef.get("message") or f"{field} should be empty",
                        current=val,
                        key={k: row.get(k, "") for k in list(row.keys())[:4]},
                    )
                )
            if fdef.get("contains_param"):
                needle = params.get(str(fdef["contains_param"]), "")
                if needle and needle.upper() not in val.upper() and val != "":
                    findings.append(
                        Finding(
                            severity=severity,
                            table=table,
                            field=field,
                            message=fdef.get("message") or f"{field} missing {needle}",
                            current=val,
                        )
                    )
                # empty ZWELS often means all methods allowed — only warn if non-empty and missing
        return findings

    def _custom_checks(self, cdef: dict[str, Any], slices: dict[str, TableSlice]) -> list[Finding]:
        findings: list[Finding] = []
        if cdef.get("type") == "ekbe_vgabe":
            sl = slices.get("EKBE")
            vgabe = str(cdef.get("vgabe", "1"))
            if not sl or not any(str(r.get("VGABE", "")) == vgabe for r in sl.rows):
                findings.append(
                    Finding(
                        severity=cdef.get("severity") or "warning",
                        table="EKBE",
                        field="VGABE",
                        message=cdef.get("fail_message") or "GR not found",
                    )
                )
            else:
                findings.append(
                    Finding(
                        severity="info",
                        table="EKBE",
                        field="VGABE",
                        message=cdef.get("message") or "GR found",
                        current=vgabe,
                    )
                )
        return findings
