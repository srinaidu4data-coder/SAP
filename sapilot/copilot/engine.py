"""
SAPILOT Co-pilot — login to SAP GUI Logon Pad, run scenarios / NL goals,
click like a consultant, extract table data (RFC first, GUI fallback).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sapilot.act.executor import GroundedExecutor
from sapilot.brain.governor import Governor
from sapilot.brain.loop import AgentLoop
from sapilot.brain.router import ModelRouter
from sapilot.connect.driver import GuiDriver, open_live_session
from sapilot.connect.gui import MockGuiSession
from sapilot.connect.logon import gui_logon_from_vault, load_connection, load_gui_logon_params
from sapilot.connect.rfc import MockRfcClient, RfcClient, RfcClientBase
from sapilot.copilot.knowledge import DataExtractor
from sapilot.copilot.scenarios import ScenarioContext, ScenarioRunner, list_scenarios, load_scenario
from sapilot.demo_data import seed_demo_tables
from sapilot.diagnose.engine import PaymentRunDiagnosticEngine
from sapilot.know.tables import KnowledgeTables
from sapilot.policy.tier import TierContext, derive_tier, load_policy
from sapilot.report.html import render_html_report
from sapilot.report.journal import RunJournal
from sapilot.schemas import (
    BudgetState,
    GuiElement,
    ScreenSnapshot,
    TerminalOutcome,
)
from sapilot.security.redaction import RedactionGate
from sapilot.security.vault import CredentialVault

log = logging.getLogger(__name__)


class Copilot:
    """
    Main Co-pilot façade.

    Primary mode (production intent):
      REAL SAP GUI via SAP Logon Pad — system description + client + user + password.

    Other modes:
      - attach: control an already-open SAP GUI session (no re-login)
      - mock: offline unit/demo only (explicit --mock; never the default for real work)
    """

    def __init__(
        self,
        *,
        mock: bool = False,
        attach: bool = False,
        connection: str | None = None,
        system: str | None = None,
        client: str | None = None,
        user: str | None = None,
        password: str | None = None,
        language: str = "EN",
        use_rfc: bool = True,
        mandt: str | None = None,
        cccategory: str | None = None,
        approval_token: str | None = None,
    ):
        # Real GUI is the default. Mock only when explicitly requested.
        self.mock = mock
        self.attach = attach and not mock
        self.connection = connection
        self.system = system or os.environ.get("SAPILOT_SYSTEM") or os.environ.get("SAPILOT_LOGON_SYSTEM")
        self.client = client or os.environ.get("SAPILOT_CLIENT")
        self.user = user or os.environ.get("SAPILOT_USER")
        self.password = password or os.environ.get("SAPILOT_PASSWORD")
        self.language = language or os.environ.get("SAPILOT_LANG", "EN")
        self.use_rfc = use_rfc
        self.mandt = mandt or self.client or os.environ.get("SAPILOT_CLIENT") or "100"
        self.cccategory = cccategory
        self.approval_token = approval_token or os.environ.get("SAPILOT_APPROVAL_TOKEN")

        self.journal = RunJournal()
        self.redaction = RedactionGate()
        self.driver: GuiDriver | None = None
        self.rfc: RfcClientBase | None = None
        self.extractor: DataExtractor | None = None
        self.tier_ctx: TierContext | None = None
        self._connected = False

    # ------------------------------------------------------------------ connect
    def connect(self) -> None:
        if self._connected:
            return
        pol = load_policy()

        if self.mock:
            self._connect_mock(pol)
        else:
            self._connect_live(pol)

        assert self.extractor is not None
        # Derive tier from T000 when RFC available
        # Live tier must come from T000 when possible — never honor operator cccategory
        # as a sandbox escalation path (RT-AUDIT F-01 / RT-SEC H1).
        cat = None
        if self.mock:
            cat = self.cccategory or "D"
        elif self.rfc:
            try:
                rows = KnowledgeTables(self.rfc).read_t000(self.mandt)
                if rows:
                    cat = rows[0].get("CCCATEGORY")
            except Exception as e:
                log.warning("T000 read failed: %s", e)
        if cat is None and not self.mock:
            # Unknown live client → most restrictive
            cat = "P"
            log.warning(
                "Live session without T000 CCCATEGORY — forcing production/observe mapping (T3)"
            )
        if cat is None:
            cat = "D"
        tier = derive_tier(str(self.mandt), str(cat), pol)
        self.tier_ctx = TierContext(tier=tier, mandt=str(self.mandt), cccategory=str(cat))
        self.journal.append(
            "connect",
            {
                "mock": self.mock,
                "attach": self.attach,
                "tier": tier.value,
                "mandt": self.mandt,
                "cccategory": cat,
            },
        )
        self._connected = True

    def _connect_mock(self, pol: dict[str, Any]) -> None:
        rfc = MockRfcClient()
        seed_demo_tables(rfc)
        self.rfc = rfc
        screens = _mock_screens()
        gui = MockGuiSession(screens=screens, initial="SESSION_MANAGER")
        self.driver = GuiDriver(gui, settle_seconds=0.0)
        self.extractor = DataExtractor(rfc=rfc, driver=self.driver)

    def _connect_live(self, pol: dict[str, Any]) -> None:
        """
        Always real SAP GUI.

        Priority:
          1. --attach → existing session
          2. --connection vault → Logon Pad (system + user + password)
          3. --system + --client + --user + --password → Logon Pad
          4. Otherwise fail with clear instructions (do NOT silently mock)
        """
        from sapilot.connect.logon import gui_logon

        if self.attach:
            log.info("Attaching to existing SAP GUI session")
            self.driver = open_live_session(attach=True)
        elif self.connection:
            params = load_gui_logon_params(self.connection)
            system = self.system or params["system_description"]
            client = self.client or params["client"]
            user = self.user or params["user"]
            password = self.password or params["password"]
            language = self.language or params["language"]
            if not password:
                raise RuntimeError(
                    f"Vault connection '{self.connection}' has no password. "
                    f"Re-run: sapilot vault set {self.connection} ..."
                )
            log.info(
                "Opening SAP Logon Pad connection '%s' as %s client %s",
                system,
                user,
                client,
            )
            gui = gui_logon(system, client, user, password, language)
            self.driver = GuiDriver(gui)
            self.mandt = client or self.mandt
            self.client, self.user, self.password = client, user, password
            self.system = system
        elif self.system and self.client and self.user and self.password:
            log.info(
                "Opening SAP Logon Pad '%s' as %s client %s",
                self.system,
                self.user,
                self.client,
            )
            gui = gui_logon(
                self.system, self.client, self.user, self.password, self.language
            )
            self.driver = GuiDriver(gui)
            self.mandt = self.client
        else:
            raise RuntimeError(
                "Real SAP GUI login required (mock is OFF).\n"
                "Provide credentials one of these ways:\n"
                "  1) Logon Pad login:\n"
                "       --system \"Your SID description in SAP Logon\" "
                "--client 100 --user MYUSER --password ...\n"
                "  2) Saved vault:\n"
                "       sapilot vault set myecc --system \"...\" --client 100 --user ...\n"
                "       sapilot copilot ... --connection myecc\n"
                "  3) Already logged on:\n"
                "       --attach\n"
                "  4) Offline only:\n"
                "       --mock\n"
                "Env aliases: SAPILOT_SYSTEM, SAPILOT_CLIENT, SAPILOT_USER, SAPILOT_PASSWORD"
            )

        # RFC knowledge channel (optional; GUI works without it)
        if self.use_rfc and self.connection:
            try:
                params = load_connection(self.connection)
                rfc = RfcClient(params)
                rfc.connect()
                self.rfc = rfc
                log.info("RFC knowledge channel connected")
            except Exception as e:
                log.warning("RFC not available — GUI-only mode: %s", e)
                self.rfc = None
        elif self.use_rfc and self.client and self.user and self.password:
            ashost = os.environ.get("SAPILOT_ASHOST", "")
            if ashost:
                try:
                    rfc = RfcClient(
                        {
                            "ashost": ashost,
                            "sysnr": os.environ.get("SAPILOT_SYSNR", "00"),
                            "client": self.client,
                            "user": self.user,
                            "passwd": self.password,
                            "lang": self.language,
                        }
                    )
                    rfc.connect()
                    self.rfc = rfc
                    log.info("RFC knowledge channel connected via SAPILOT_ASHOST")
                except Exception as e:
                    log.warning("RFC connect failed — GUI-only mode: %s", e)

        self.extractor = DataExtractor(rfc=self.rfc, driver=self.driver)
        self.journal.append(
            "gui_session",
            {
                "mode": "attach" if self.attach else "logon_pad",
                "system": self.system,
                "client": self.client,
                "user": self.user,
                "rfc": self.rfc is not None,
            },
        )

    def disconnect(self) -> None:
        if self.rfc and hasattr(self.rfc, "close"):
            try:
                self.rfc.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        self._connected = False

    # ------------------------------------------------------------------ ops
    def list_scenarios(self) -> list[dict[str, str]]:
        return list_scenarios()

    def run_scenario(self, scenario_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.connect()
        assert self.extractor and self.tier_ctx
        scenario = load_scenario(scenario_id)
        # Tier gate: write-heavy scenarios
        if scenario.get("requires_tier") == "T1_SANDBOX":
            from sapilot.schemas import Tier

            if self.tier_ctx.tier != Tier.T1_SANDBOX:
                raise RuntimeError(
                    f"Scenario {scenario_id} requires T1_SANDBOX; current {self.tier_ctx.tier.value}"
                )
        ctx = ScenarioContext(
            driver=self.driver,
            extractor=self.extractor,
            journal=self.journal,
            params=params or {},
        )
        runner = ScenarioRunner(ctx)
        result = runner.run(scenario)
        self._write_report(scenario_id, result, ctx)
        return result

    def extract_table(
        self,
        table: str,
        *,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 100,
    ) -> dict[str, Any]:
        self.connect()
        assert self.extractor
        data = self.extractor.read_table(table, fields=fields, options=options, rowcount=rowcount)
        self.journal.append("extract_table", self.redaction.redact_payload(data))
        return data

    def diagnose_payments(
        self, bukrs: str, method: str, vendors: list[str] | None = None
    ) -> Any:
        self.connect()
        assert self.rfc and self.extractor
        engine = PaymentRunDiagnosticEngine(KnowledgeTables(self.rfc))
        report = engine.diagnose(bukrs, method, vendors=vendors)
        self.journal.append(
            "diagnosis", self.redaction.redact_payload(report.model_dump(mode="json"))
        )
        path = self.journal.dir / "diagnosis.html"
        render_html_report(path, run_id=self.journal.run_id, diagnosis=report)
        return report

    def click(self, target: str) -> dict[str, Any]:
        self.connect()
        assert self.driver and self.tier_ctx
        # policy: GUI write capability
        self.tier_ctx.require("gui_write", action=f"press:{target}")
        self.driver.press(target)
        return {
            "pressed": target,
            "status": self.driver.status_bar(),
            "screen": self.extractor.screen_summary() if self.extractor else {},
        }

    def type_field(self, target: str, value: str) -> dict[str, Any]:
        self.connect()
        assert self.driver and self.tier_ctx
        self.tier_ctx.require("gui_write", action=f"setText:{target}")
        self.driver.set_text(target, value)
        return {"target": target, "status": self.driver.status_bar()}

    def goto(self, tcode: str) -> dict[str, Any]:
        self.connect()
        assert self.driver
        snap = self.driver.start_transaction(tcode)
        return {"tcode": snap.tcode, "title": snap.title, "status": self.driver.status_bar()}

    def screen(self) -> dict[str, Any]:
        self.connect()
        assert self.extractor
        return self.extractor.screen_summary()

    def run_goal(self, goal: str, *, max_steps: int = 30) -> TerminalOutcome:
        """
        NL Co-pilot loop: observe screen → plan (LLM) → grounded click/read → journal.
        Without XAI_API_KEY, escalates safely.
        """
        self.connect()
        assert self.driver and self.tier_ctx and self.extractor

        # Seed knowledge for planner
        knowledge: dict[str, Any] = {
            "screen": self.extractor.screen_summary(),
            "scenarios": [s["id"] for s in list_scenarios()],
            "goal_hint": goal,
        }
        # If payment-related, pre-read config when RFC present
        if self.rfc and any(k in goal.lower() for k in ("payment", "f110", "ach", "fbzp")):
            try:
                knowledge["fbzp"] = KnowledgeTables(self.rfc).fbzp_chain_snapshot("1000", "A")
            except Exception:
                pass

        gov = Governor(BudgetState(max_steps=max_steps))
        executor = GroundedExecutor(
            self.tier_ctx,
            gui=self.driver.session,
            rfc=self.rfc,
            approval_token=self.approval_token,
        )
        # Keep driver + executor session in sync: executor uses raw session
        loop = AgentLoop(
            self.tier_ctx,
            executor,
            gov,
            self.journal,
            router=ModelRouter(self.redaction),
            redaction=self.redaction,
            knowledge=self.redaction.redact_payload(knowledge),
        )
        outcome = loop.run(goal, max_steps=max_steps)
        self.journal.append("goal_end", {"goal": goal, "outcome": outcome.value})
        return outcome

    def _write_report(
        self, scenario_id: str, result: dict[str, Any], ctx: ScenarioContext
    ) -> Path:
        # lightweight HTML
        from sapilot.schemas import DiagnosisReport

        findings_note = DiagnosisReport(
            company_code=str(ctx.params.get("bukrs", "")),
            payment_method=str(ctx.params.get("method", "")),
            summary=(
                f"Scenario {scenario_id}: {'OK' if result.get('ok') else 'FAILED'} — "
                f"{result.get('steps_run', 0)} steps"
            ),
            findings=[],
            config_snapshot={
                k: v
                for k, v in ctx.vars.items()
                if k in {"fbzp", "vendor", "payment_run", "T042E", "grid"}
            },
        )
        path = self.journal.dir / f"scenario_{scenario_id}.html"
        render_html_report(
            path,
            run_id=self.journal.run_id,
            diagnosis=findings_note,
            journal_events=self.journal.read_all(),
        )
        result["report"] = str(path)
        result["journal"] = str(self.journal.path)
        return path


def _mock_screens() -> dict[str, ScreenSnapshot]:
    def win(tcode: str, title: str, children: list[GuiElement]) -> ScreenSnapshot:
        return ScreenSnapshot(
            tcode=tcode,
            title=title,
            elements=GuiElement(
                id="wnd[0]",
                type="GuiMainWindow",
                text=title,
                children=[
                    GuiElement(
                        id="wnd[0]/tbar[0]/okcd",
                        type="GuiOkCodeField",
                        name="okcd",
                        changeable=True,
                    ),
                    *children,
                ],
            ),
        )

    return {
        "SESSION_MANAGER": win(
            "SESSION_MANAGER",
            "SAP Easy Access",
            [GuiElement(id="wnd[0]/usr/cntlIMAGE_CONTAINER", type="GuiShell", name="IMAGE")],
        ),
        "F110": win(
            "F110",
            "Automatic Payment Transactions",
            [
                GuiElement(
                    id="wnd[0]/usr/txtF110V-LAUFD",
                    type="GuiTextField",
                    name="F110V-LAUFD",
                    changeable=True,
                ),
                GuiElement(
                    id="wnd[0]/usr/txtF110V-LAUFI",
                    type="GuiTextField",
                    name="F110V-LAUFI",
                    changeable=True,
                ),
                GuiElement(
                    id="wnd[0]/usr/btnPROPOSAL",
                    type="GuiButton",
                    name="PROPOSAL",
                    text="Proposal",
                ),
                GuiElement(
                    id="wnd[0]/usr/btnSTART",
                    type="GuiButton",
                    name="START",
                    text="Start Immediately",
                ),
                GuiElement(
                    id="wnd[0]/usr/tabsTABSTRIP",
                    type="GuiTabStrip",
                    name="TABSTRIP",
                    children=[
                        GuiElement(id="wnd[0]/usr/tabsTABSTRIP/tabpPARAM", type="GuiTab", text="Parameter"),
                        GuiElement(id="wnd[0]/usr/tabsTABSTRIP/tabpLOG", type="GuiTab", text="Additional Log"),
                    ],
                ),
            ],
        ),
        "SE16N": win(
            "SE16N",
            "General Table Display",
            [
                GuiElement(
                    id="wnd[0]/usr/ctxtGD-TAB",
                    type="GuiCTextField",
                    name="GD-TAB",
                    changeable=True,
                ),
                GuiElement(
                    id="wnd[0]/usr/tblSAPLSE16NGRID",
                    type="GuiTableControl",
                    name="GRID",
                    children=[
                        GuiElement(id="cell[0,0]", type="GuiTextField", name="BUKRS", text="1000"),
                        GuiElement(id="cell[0,1]", type="GuiTextField", name="ZLSCH", text="A"),
                    ],
                ),
            ],
        ),
        "XK03": win(
            "XK03",
            "Display Vendor",
            [
                GuiElement(
                    id="wnd[0]/usr/ctxtRF02K-LIFNR",
                    type="GuiCTextField",
                    name="RF02K-LIFNR",
                    changeable=True,
                ),
                GuiElement(
                    id="wnd[0]/usr/ctxtRF02K-BUKRS",
                    type="GuiCTextField",
                    name="RF02K-BUKRS",
                    changeable=True,
                ),
            ],
        ),
        "FBL1N": win(
            "FBL1N",
            "Vendor Line Item Display",
            [
                GuiElement(
                    id="wnd[0]/usr/ctxtKD_LIFNR-LOW",
                    type="GuiCTextField",
                    name="KD_LIFNR-LOW",
                    changeable=True,
                ),
                GuiElement(
                    id="wnd[0]/usr/ctxtKD_BUKRS-LOW",
                    type="GuiCTextField",
                    name="KD_BUKRS-LOW",
                    changeable=True,
                ),
            ],
        ),
    }
