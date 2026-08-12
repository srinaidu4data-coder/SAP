"""
Run all PTP Co-pilot scenarios one-by-one and print expected/actual results.

Uses mock SAP tables that mirror a complete P2P chain (PR→PO→GR→IR→AP→F110).
Live RFC is used automatically if a working RfcClient is available.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_DATA", str(ROOT / "data"))
os.environ.setdefault("SAPILOT_VAULT_PASSPHRASE", os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local"))

from sapilot.connect.gui import MockGuiSession
from sapilot.connect.rfc import MockRfcClient, RfcClient
from sapilot.copilot.knowledge import DataExtractor
from sapilot.copilot.scenarios import ScenarioContext, ScenarioRunner, list_scenarios, load_scenario
from sapilot.demo_data_ptp import seed_ptp_tables
from sapilot.diagnose.engine import PaymentRunDiagnosticEngine
from sapilot.know.tables import KnowledgeTables
from sapilot.report.journal import RunJournal
from sapilot.connect.driver import GuiDriver
from sapilot.copilot.engine import _mock_screens

# Demo keys for the seeded PTP landscape
PARAMS = {
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
    "table": "EKKO",
}


def try_live_rfc() -> RfcClient | MockRfcClient:
    try:
        from sapilot.security.vault import CredentialVault
        from sapilot.connect.logon import load_connection

        params = load_connection("vista", CredentialVault(passphrase=os.environ["SAPILOT_VAULT_PASSPHRASE"]))
        if not params.get("ashost"):
            raise RuntimeError("no ashost")
        rfc = RfcClient(params)
        rfc.connect()
        print("LIVE RFC connected to", params.get("ashost"))
        return rfc
    except Exception as e:
        print(f"LIVE RFC unavailable ({e}); using mock PTP database snapshot")
        rfc = MockRfcClient()
        seed_ptp_tables(rfc)
        return rfc


def summarize_vars(vars_: dict) -> list[str]:
    lines = []
    for k, v in vars_.items():
        if k in {"screen", "vendor_screen", "pr_screen", "po_screen", "f110_screen", "open_item_grid"}:
            if isinstance(v, dict):
                lines.append(f"  {k}: tcode={v.get('tcode')} title={v.get('title')}")
            else:
                lines.append(f"  {k}: {type(v).__name__}")
            continue
        if isinstance(v, dict) and "rows" in v:
            rows = v.get("rows") or []
            lines.append(f"  {k}: {v.get('channel')} count={v.get('count')} sample={rows[:1]}")
        elif isinstance(v, dict) and any(isinstance(x, list) for x in v.values()):
            parts = []
            for tk, tv in v.items():
                if isinstance(tv, list):
                    parts.append(f"{tk}={len(tv)}")
            lines.append(f"  {k}: " + ", ".join(parts))
        elif isinstance(v, dict):
            lines.append(f"  {k}: keys={list(v.keys())[:8]}")
        else:
            lines.append(f"  {k}: {str(v)[:120]}")
    return lines


def expected_for(sid: str) -> str:
    return {
        "ptp_01_vendor_master": (
            "Vendor 100001 exists (LFA1). Company code 1000 data present (LFB1) but "
            "ZWELS may lack ACH 'A', ZAHLS block may be set, LFBK may be empty → payment risks."
        ),
        "ptp_02_material_purchasing": (
            "Material 100000 ROH at plant 1000 with standard price; purchasing-ready."
        ),
        "ptp_03_info_record": "Info record 5300000001 net price 12.50 USD for org 1000.",
        "ptp_04_source_list": "Fixed source vendor 100001 for plant 1000 / material 100000.",
        "ptp_05_purchase_requisition": "PR 10000001/10 qty 100 EA, fixed vendor 100001, open status.",
        "ptp_06_purchase_order": "PO 4500000001 vendor 100001, item 10 qty 100 @ 12.50 = 1250 USD.",
        "ptp_07_goods_receipt": "EKBE VGABE=1 GR 5000000001 mvt 101 for full qty 100.",
        "ptp_08_invoice_verification": "Invoice 5105600001 posted RE, amount 1250, ref INV-9001.",
        "ptp_09_vendor_open_items": (
            "BSIK shows open AP items (blocked demo item + clean INV-9001 1250 for payment)."
        ),
        "ptp_10_payment_readiness": (
            "FBZP gaps (T042E/T042I/T042Y) + vendor bank/method/block issues → F110 not ready "
            "until remediated; open items exist."
        ),
        "f110_diagnose": "Same payment blockers as AP diagnostic engine findings.",
        "vendor_display": "XK03 GUI + LFA1/LFB1/LFBK pack.",
        "vendor_line_items": "FBL1N GUI + BSIK extract.",
        "f110_parameters": "F110 opened; parameters fields set (demo-safe, no post).",
        "read_table": "Generic table extract.",
        "se16_browse": "SE16N GUI browse (demo).",
    }.get(sid, "See table extracts in journal.")


def main() -> int:
    rfc = try_live_rfc()
    live = not isinstance(rfc, MockRfcClient)
    mode = "LIVE" if live else "MOCK-PTP-DB"

    ptp_ids = [s["id"] for s in list_scenarios() if s["id"].startswith("ptp_")]
    # also run classic AP scenarios that close PTP
    extra = ["vendor_display", "vendor_line_items", "f110_diagnose", "f110_parameters"]
    ordered = ptp_ids + [x for x in extra if x not in ptp_ids]

    report = {
        "mode": mode,
        "params": PARAMS,
        "scenarios": [],
    }

    print("=" * 72)
    print(f"SAPILOT PTP SCENARIO RUN — mode={mode}")
    print("=" * 72)
    print("Demo keys:", json.dumps(PARAMS, indent=2))
    print()

    tables = KnowledgeTables(rfc)
    # Pre-flight diagnosis for payment end of PTP
    diag = PaymentRunDiagnosticEngine(tables).diagnose(
        PARAMS["bukrs"], PARAMS["method"], vendors=[PARAMS["lifnr"]], land1=PARAMS["land1"]
    )
    print("--- End-to-end payment diagnosis (after IR) ---")
    print(diag.summary)
    for f in diag.findings[:12]:
        print(f"  [{f.severity}] {f.cause_table}.{f.cause_field}: {f.symptom}")
    print()

    for sid in ordered:
        print("-" * 72)
        print(f"SCENARIO: {sid}")
        print(f"EXPECTED: {expected_for(sid)}")
        try:
            scenario = load_scenario(sid)
        except Exception as e:
            print(f"RESULT: SKIP load error {e}")
            report["scenarios"].append({"id": sid, "ok": False, "error": str(e)})
            continue

        journal = RunJournal()
        gui = MockGuiSession(screens=_mock_screens(), initial="SESSION_MANAGER")
        # add ME53N / ME23N shells
        from sapilot.schemas import GuiElement, ScreenSnapshot

        def win(tcode: str, title: str) -> ScreenSnapshot:
            return ScreenSnapshot(
                tcode=tcode,
                title=title,
                elements=GuiElement(
                    id="wnd[0]",
                    type="GuiMainWindow",
                    text=title,
                    children=[
                        GuiElement(id="wnd[0]/tbar[0]/okcd", type="GuiOkCodeField", name="okcd", changeable=True),
                        GuiElement(id="wnd[0]/usr/ctxtRF02K-LIFNR", type="GuiCTextField", name="RF02K-LIFNR", changeable=True),
                        GuiElement(id="wnd[0]/usr/ctxtRF02K-BUKRS", type="GuiCTextField", name="RF02K-BUKRS", changeable=True),
                        GuiElement(id="wnd[0]/usr/ctxtKD_LIFNR-LOW", type="GuiCTextField", name="KD_LIFNR-LOW", changeable=True),
                        GuiElement(id="wnd[0]/usr/ctxtKD_BUKRS-LOW", type="GuiCTextField", name="KD_BUKRS-LOW", changeable=True),
                        GuiElement(id="wnd[0]/usr/txtF110V-LAUFD", type="GuiTextField", name="F110V-LAUFD", changeable=True),
                        GuiElement(id="wnd[0]/usr/txtF110V-LAUFI", type="GuiTextField", name="F110V-LAUFI", changeable=True),
                    ],
                ),
            )

        for tc, title in [
            ("ME53N", "Display Purchase Requisition"),
            ("ME23N", "Display Purchase Order"),
            ("ME21N", "Create Purchase Order"),
            ("MIGO", "Goods Movement"),
            ("MIRO", "Enter Incoming Invoice"),
        ]:
            gui.load_screen(tc, win(tc, title))

        driver = GuiDriver(gui, settle_seconds=0.0)
        extractor = DataExtractor(rfc=rfc, driver=driver)
        ctx = ScenarioContext(driver=driver, extractor=extractor, journal=journal, params=dict(PARAMS))
        runner = ScenarioRunner(ctx)
        try:
            result = runner.run(scenario)
            ok = result.get("ok")
            print(f"RESULT: {'OK' if ok else 'FAILED'} steps={result.get('steps_run')}")
            for line in summarize_vars(result.get("vars") or {}):
                print(line)
            print(f"  journal: {journal.path}")
            report["scenarios"].append(
                {
                    "id": sid,
                    "ok": ok,
                    "steps": result.get("steps_run"),
                    "vars": {
                        k: (
                            {"count": v.get("count"), "channel": v.get("channel")}
                            if isinstance(v, dict) and "count" in v
                            else (list(v.keys()) if isinstance(v, dict) else str(type(v)))
                        )
                        for k, v in (result.get("vars") or {}).items()
                    },
                    "journal": str(journal.path),
                    "expected": expected_for(sid),
                }
            )
        except Exception as e:
            print(f"RESULT: ERROR {e}")
            report["scenarios"].append({"id": sid, "ok": False, "error": str(e)})

    out_path = ROOT / "data" / "runs" / "PTP_SCENARIO_RESULTS.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print()
    print("=" * 72)
    print(f"Wrote {out_path}")
    ok_n = sum(1 for s in report["scenarios"] if s.get("ok"))
    print(f"Summary: {ok_n}/{len(report['scenarios'])} scenarios OK ({mode})")
    if not live:
        print(
            "NOTE: Live table read needs SAP NW RFC SDK + pyrfc (not available on this Python). "
            "Results above are from a seeded PTP database mirroring Vista client 1000 landscape."
        )
    return 0 if ok_n == len(report["scenarios"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
