"""
Functional-consultant brain: observe → decide → remediate → verify.

Runs 10 PTP scenarios autonomously like an SAP MM/FI consultant would.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from sapilot.autobot.digital_twin import DigitalTwin
from sapilot.autobot.human_operator import HumanOperator, human_pause
from sapilot.know.gather import ScenarioDataGatherer
from sapilot.report.journal import RunJournal

log = logging.getLogger(__name__)

# 10 PTP + 10 OTC autonomous scenarios
TEN_MISSIONS = [
    {
        "id": "S1_VENDOR",
        "title": "Check vendor master readiness",
        "pack": "ptp_01_vendor_master",
        "tcode": "XK03",
        "remediate": "payment_vendor",
    },
    {
        "id": "S2_MATERIAL",
        "title": "Verify material purchasing views",
        "pack": "ptp_02_material_purchasing",
        "tcode": "MM03",
        "remediate": None,
    },
    {
        "id": "S3_INFO",
        "title": "Validate purchasing info record",
        "pack": "ptp_03_info_record",
        "tcode": "ME13",
        "remediate": None,
    },
    {
        "id": "S4_SOURCE",
        "title": "Check source list",
        "pack": "ptp_04_source_list",
        "tcode": "ME03",
        "remediate": None,
    },
    {
        "id": "S5_PR",
        "title": "Display purchase requisition",
        "pack": "ptp_05_purchase_requisition",
        "tcode": "ME53N",
        "remediate": "ensure_chain",
    },
    {
        "id": "S6_PO",
        "title": "Display / ensure purchase order",
        "pack": "ptp_06_purchase_order",
        "tcode": "ME23N",
        "remediate": "ensure_chain",
    },
    {
        "id": "S7_GR",
        "title": "Verify goods receipt history",
        "pack": "ptp_07_goods_receipt",
        "tcode": "MIGO",
        "remediate": "ensure_chain",
    },
    {
        "id": "S8_IR",
        "title": "Verify invoice document",
        "pack": "ptp_08_invoice_verification",
        "tcode": "MIR4",
        "remediate": "ensure_chain",
    },
    {
        "id": "S9_OPEN_ITEMS",
        "title": "Vendor open items for payment",
        "pack": "ptp_09_vendor_open_items",
        "tcode": "FBL1N",
        "remediate": "payment_vendor",
    },
    {
        "id": "S10_PAYMENT",
        "title": "Payment program readiness (create missing config)",
        "pack": "ptp_10_payment_readiness",
        "tcode": "F110",
        "remediate": "payment_full",
    },
]

# 10 Order-to-Cash missions
OTC_MISSIONS = [
    {
        "id": "O1_CUSTOMER",
        "title": "Check customer master readiness",
        "pack": "otc_01_customer_master",
        "tcode": "XD03",
        "remediate": "ensure_otc",
    },
    {
        "id": "O2_MAT_SALES",
        "title": "Verify material sales views",
        "pack": "otc_02_material_sales",
        "tcode": "MM03",
        "remediate": "ensure_otc",
    },
    {
        "id": "O3_CUST_MAT",
        "title": "Customer-material info",
        "pack": "otc_03_customer_material",
        "tcode": "VD53",
        "remediate": "ensure_otc",
    },
    {
        "id": "O4_SALES_ORG",
        "title": "Sales area configuration",
        "pack": "otc_04_sales_org",
        "tcode": "OVX5",
        "remediate": "ensure_otc",
    },
    {
        "id": "O5_SO",
        "title": "Sales order",
        "pack": "otc_05_sales_order",
        "tcode": "VA03",
        "remediate": "ensure_otc",
    },
    {
        "id": "O6_DN",
        "title": "Outbound delivery",
        "pack": "otc_06_delivery",
        "tcode": "VL03N",
        "remediate": "ensure_otc",
    },
    {
        "id": "O7_GI",
        "title": "Goods issue / document flow",
        "pack": "otc_07_goods_issue",
        "tcode": "VL03N",
        "remediate": "ensure_otc",
    },
    {
        "id": "O8_BILL",
        "title": "Billing document",
        "pack": "otc_08_billing",
        "tcode": "VF03",
        "remediate": "ensure_otc",
    },
    {
        "id": "O9_AR",
        "title": "Customer open items AR",
        "pack": "otc_09_customer_open_items",
        "tcode": "FBL5N",
        "remediate": "otc_payment",
    },
    {
        "id": "O10_INCOMING",
        "title": "Incoming payment readiness",
        "pack": "otc_10_incoming_payment",
        "tcode": "F-28",
        "remediate": "otc_payment",
    },
]

# 2 ABAP debugging missions (read-only inspect — never field-value replace)
ABAP_MISSIONS = [
    {
        "id": "A1_ST22_DUMP",
        "title": "Analyze runtime dump (ST22)",
        "pack": "abap_01_runtime_dump",
        "tcode": "ST22",
        "remediate": "ensure_abap",
    },
    {
        "id": "A2_SE38_SOURCE",
        "title": "Inspect ABAP source + safe debug recipe (SE38)",
        "pack": "abap_02_source_inspect",
        "tcode": "SE38",
        "remediate": "ensure_abap",
    },
]

# Full fleet: 10 PTP + 10 OTC + 2 ABAP debug = 22
ALL_MISSIONS = TEN_MISSIONS + OTC_MISSIONS + ABAP_MISSIONS
FLEET_MISSIONS = ALL_MISSIONS



@dataclass
class MissionResult:
    id: str
    title: str
    ok: bool
    ready_before: bool
    ready_after: bool
    fixes: list[str] = field(default_factory=list)
    table_counts: dict[str, int] = field(default_factory=dict)
    gui_action: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConsultantBot:
    """
    Autonomous SAP AI bot.

    Mode:
      - twin: digital twin tables + optional live mouse on SAP window
      - live: attempt real GUI + extract (falls back twin for missing data)
    """

    def __init__(
        self,
        *,
        use_live_gui: bool = True,
        show_mouse: bool = True,
        auto_remediate: bool = True,
    ):
        self.twin = DigitalTwin()
        self.operator = HumanOperator(show_mouse=show_mouse)
        self.journal = RunJournal()
        self.use_live_gui = use_live_gui
        self.auto_remediate = auto_remediate
        self.results: list[MissionResult] = []
        self.message_log: list[str] = []
        self.stealth = False

    def say(self, msg: str) -> None:
        self.message_log.append(msg)
        self.journal.append("bot_say", {"msg": msg})
        log.info("BOT: %s", msg)
        print(f"[BOT] {msg}")

    def run_all_ten(self, user_message: str = "") -> dict[str, Any]:
        """Backward compatible: PTP only."""
        return self.run_missions(TEN_MISSIONS, user_message, process="PTP", outfile="AUTOBOT_10_PTP_RESULTS.json")

    def run_all_otc(self, user_message: str = "") -> dict[str, Any]:
        return self.run_missions(OTC_MISSIONS, user_message, process="OTC", outfile="AUTOBOT_10_OTC_RESULTS.json")

    def run_all_twenty(self, user_message: str = "") -> dict[str, Any]:
        """Full 10 PTP + 10 OTC autonomous run (legacy name; still PTP+OTC only)."""
        return self.run_missions(
            TEN_MISSIONS + OTC_MISSIONS,
            user_message or "Run full PTP and OTC as functional consultant. Get data alone. Create missing.",
            process="PTP+OTC",
            outfile="AUTOBOT_20_PTP_OTC_RESULTS.json",
        )

    def run_all_fleet(self, user_message: str = "") -> dict[str, Any]:
        """Full fleet: 10 PTP + 10 OTC + 2 ABAP debug."""
        return self.run_missions(
            ALL_MISSIONS,
            user_message
            or "Run PTP, OTC, and ABAP debug. Get data alone. Create missing. Never field-replace in debugger.",
            process="PTP+OTC+ABAP",
            outfile="AUTOBOT_22_FLEET_RESULTS.json",
        )

    def run_missions(
        self,
        missions: list[dict[str, Any]],
        user_message: str = "",
        *,
        process: str = "PTP",
        outfile: str = "AUTOBOT_RESULTS.json",
    ) -> dict[str, Any]:
        # Policy choke-point for any GUI writes this bot makes
        try:
            from sapilot.policy.guard import bind_write_context, is_lab_mode
            from sapilot.policy.tier import TierContext
            from sapilot.schemas import Tier

            tier = Tier.T1_SANDBOX if is_lab_mode() else Tier.T3_OBSERVE
            bind_write_context(
                TierContext(tier, os.environ.get("SAPILOT_CLIENT", "100"), "D" if is_lab_mode() else "P"),
                approval_token=os.environ.get("SAPILOT_APPROVAL_TOKEN"),
                source="consultant_bot",
            )
        except Exception as e:
            self.say(f"Policy bind note: {e}")

        if user_message:
            self.say(f"Received instruction: {user_message}")
        self.say(f"Starting {len(missions)}-scenario autonomous {process} walk.")
        self.twin.ensure_po_chain()
        self.twin.ensure_otc_chain()
        self.results = []

        if self.use_live_gui:
            self.say("Focusing SAP GUI (safe COM navigation — never types tcode into data fields)…")
            try:
                bound = self.operator.try_bind_open_session()
            except Exception as e:
                bound = False
                self.say(f"GUI bind failed fast: {e}")
            hwnd = None
            if bound:
                try:
                    hwnd = self.operator.focus_sap()
                except Exception as e:
                    self.say(f"Focus skipped: {e}")
                self.say("Scriptable SAP session bound — StartTransaction / ok-code only.")
            else:
                self.say(
                    "No scriptable session — twin data only "
                    "(will NOT type /nTCODE into form fields)."
                )
                # Disable further GUI attempts this run to avoid hang
                self.use_live_gui = False

        for mission in missions:
            self.results.append(self._run_mission(mission))

        summary = self._summarize()
        out = Path(os.environ.get("SAPILOT_DATA", "data")) / "runs" / outfile
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "process": process,
            "summary": summary,
            "missions": [r.to_dict() for r in self.results],
            "twin_created": self.twin.created,
            "twin_audit": self.twin.audit,
            "messages": self.message_log,
            "journal": str(self.journal.path),
        }
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self.say(f"Wrote {out}")
        self.say(summary)
        return payload

    def _run_mission(self, mission: dict[str, Any]) -> MissionResult:
        mid = mission["id"]
        self.say(f"—— {mid}: {mission['title']} ——")
        gatherer = ScenarioDataGatherer(self.twin.rfc)
        pack = gatherer.gather(mission["pack"])
        ready_before = pack.ready
        self.say(f"Tables: " + ", ".join(f"{k}={v.count}" for k, v in pack.tables.items()))
        self.say(pack.summary)

        fixes: list[str] = []
        if self.auto_remediate and mission.get("remediate"):
            fixes = self._remediate(mission["remediate"])
            if fixes:
                self.say("Created/fixed missing data: " + "; ".join(fixes[:8]))
                pack = gatherer.gather(mission["pack"])

        # Human GUI navigation — catalog-driven (research: okcd / StartTransaction only)
        gui_note = ""
        if self.use_live_gui:
            try:
                gui_note = self._navigate_mission(mission)
                self.say(gui_note)
            except Exception as e:
                gui_note = f"GUI nav skipped: {e}"
                self.say(gui_note)

        ready_after = pack.ready
        ok = ready_after or (ready_before is False and bool(fixes) and pack.ready)
        # Success criteria: no blockers after remediate OR expected info state
        ok = pack.ready if mission["id"] != "S10_PAYMENT" else pack.ready
        if mission["id"] == "S10_PAYMENT" and not pack.ready:
            # force full payment fix and re-check
            fixes.extend(self.twin.ensure_vendor_payment_ready())
            pack = gatherer.gather(mission["pack"])
            ok = pack.ready
            self.say("S10 re-check after payment config create: " + pack.summary)

        counts = {k: v.count for k, v in pack.tables.items()}
        result = MissionResult(
            id=mid,
            title=mission["title"],
            ok=ok,
            ready_before=ready_before,
            ready_after=pack.ready,
            fixes=fixes,
            table_counts=counts,
            gui_action=gui_note,
            notes=pack.summary,
        )
        self.journal.append("mission", result.to_dict())
        self.say(f"RESULT {mid}: {'OK' if ok else 'NEEDS_ATTENTION'}")
        # Keep autonomous runs snappy offline
        if self.use_live_gui:
            human_pause(0.15, 0.35)
        return result

    def _navigate_mission(self, mission: dict[str, Any]) -> str:
        """
        Use SafeNavigator + nav_catalog (Script Recording best practices).
        Never types /nTCODE into Supplier/Material/PO fields.
        """
        if self.operator._session is None:
            self.operator.try_bind_open_session()
        sess = self.operator._session
        if sess is None:
            return (
                f"No scriptable session — skipped GUI for {mission['tcode']} "
                f"(enable sapgui/user_scripting). Table extract still ran."
            )

        from sapilot.autobot.navigator import SafeNavigator

        nav = SafeNavigator(sess, show_mouse=self.operator.show_mouse)
        result = nav.run_mission_gui(mission["id"])
        if result.get("ok"):
            filled = result.get("filled") or {}
            parts = [f"{k}={v.get('value')}" for k, v in filled.items() if v.get("ok")]
            return (
                f"COM nav {result.get('tcode')}: filled [{', '.join(parts) or 'n/a'}] "
                f"status={result.get('status')!r}"
            )
        return (
            f"COM nav incomplete for {mission['tcode']}: {result.get('error')} "
            f"— check field catalog / screen variant"
        )

    def _remediate(self, kind: str) -> list[str]:
        if kind == "payment_vendor":
            return self.twin.ensure_vendor_payment_ready()
        if kind == "payment_full":
            return self.twin.ensure_vendor_payment_ready()
        if kind == "ensure_chain":
            self.twin.ensure_po_chain()
            return ["PTP chain verified/seeded"]
        if kind == "ensure_otc":
            self.twin.ensure_otc_chain()
            return ["OTC chain verified/seeded"]
        if kind == "otc_payment":
            return self.twin.ensure_customer_payment_ready()
        if kind == "ensure_abap":
            return self.twin.ensure_abap_debug_ready()
        return []

    def _summarize(self) -> str:
        ok_n = sum(1 for r in self.results if r.ok)
        ptp = sum(1 for r in self.results if r.id.startswith("S") and r.ok)
        otc = sum(1 for r in self.results if r.id.startswith("O") and r.ok)
        return (
            f"Autonomous run complete: {ok_n}/{len(self.results)} scenarios OK "
            f"(PTP={ptp}, OTC={otc}). Fixes applied: {len(self.twin.created)} creation batches."
        )
