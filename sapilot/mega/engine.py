"""
Mega SAP Co-pilot — online-first orchestrator.

Pipeline:
  1. Login to SAP GUI (Logon Pad) with real credentials
  2. Extract multi-table data ONLINE (RFC or SE16N GUI)
  3. Debug readiness from real tables
  4. Inject extracted values into live screens (mouse-visible)
  5. Execute scenario / transaction path
  6. Full journal
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sapilot.connect.driver import GuiDriver, open_live_session
from sapilot.connect.gui import GuiSession, MockGuiSession
from sapilot.connect.logon import gui_logon, gui_logon_from_vault, load_gui_logon_params
from sapilot.exceptions import CredentialsEnteredNoScripting
from sapilot.know.execute_with_data import ScenarioOrchestrator
from sapilot.know.gather import DataPack, list_packs
from sapilot.mega.extract import OnlineExtractor, connect_live_rfc
from sapilot.mega.inject import DataInjector
from sapilot.report.journal import RunJournal
from sapilot.security.vault import CredentialVault

log = logging.getLogger(__name__)


class MegaCopilot:
    """
    Massive online Co-pilot façade.

    Defaults: LIVE SAP only. Mock only if allow_mock=True for lab.
    """

    def __init__(
        self,
        *,
        system: str | None = None,
        client: str | None = None,
        user: str | None = None,
        password: str | None = None,
        connection: str = "vista",
        allow_mock: bool = False,
        show_mouse: bool = True,
    ):
        self.system = system or os.environ.get("SAPILOT_SYSTEM") or "Vista"
        self.client = client or os.environ.get("SAPILOT_CLIENT") or "100"
        self.user = user or os.environ.get("SAPILOT_USER")
        self.password = password or os.environ.get("SAPILOT_PASSWORD")
        self.connection = connection
        self.allow_mock = allow_mock
        self.show_mouse = show_mouse
        if show_mouse:
            os.environ["SAPILOT_SHOW_MOUSE"] = "1"

        self.journal = RunJournal()
        self.driver: GuiDriver | None = None
        self.extractor: OnlineExtractor | None = None
        self.injector: DataInjector | None = None
        self.last_pack: DataPack | None = None
        self.online = False
        self.status_msg = ""
        # Bind policy choke-point for all GUI writes in this process
        self._bind_policy()

    def _bind_policy(self) -> None:
        from sapilot.policy.guard import bind_write_context, is_lab_mode
        from sapilot.policy.tier import TierContext
        from sapilot.schemas import Tier

        if is_lab_mode() or self.allow_mock:
            tier = Tier.T1_SANDBOX
            cat = "D"
        else:
            tier = Tier.T3_OBSERVE
            cat = "P"
        bind_write_context(
            TierContext(tier, self.client or "100", cat),
            approval_token=os.environ.get("SAPILOT_APPROVAL_TOKEN"),
            source="mega",
        )

    # ------------------------------------------------------------------ login
    def login(self) -> dict[str, Any]:
        """Open Logon Pad system and enter Client / User / Password (visible mouse)."""
        # Prefer env passphrase; DPAPI if unset on Windows (no weak default outside lab)
        vault_pass = os.environ.get("SAPILOT_VAULT_PASSPHRASE")
        try:
            vault = CredentialVault(passphrase=vault_pass)
        except RuntimeError:
            vault = CredentialVault(passphrase=None)
        # Prefer vault for missing pieces
        try:
            p = load_gui_logon_params(self.connection, vault)
            self.system = self.system or p["system_description"]
            self.client = self.client or p["client"]
            self.user = self.user or p["user"]
            self.password = self.password or p["password"]
        except Exception:
            pass

        if not self.user or not self.password:
            raise RuntimeError("Username and password required for online Mega Co-pilot")

        # Persist for next run
        try:
            vault.set(
                self.connection,
                {
                    "system": self.system,
                    "description": self.system,
                    "client": self.client,
                    "user": self.user,
                    "passwd": self.password,
                    "lang": "EN",
                    "ashost": "apex.sapvista.com",
                    "sysnr": "00",
                },
            )
        except Exception as e:
            log.warning("vault save: %s", e)

        self.journal.append(
            "mega_login_start",
            {"system": self.system, "client": self.client, "user": self.user},
        )

        result: dict[str, Any] = {
            "system": self.system,
            "client": self.client,
            "user": self.user,
            "scriptable": False,
            "credentials_entered": False,
        }

        try:
            gui = gui_logon(self.system, self.client, self.user, self.password, "EN")
            self.driver = GuiDriver(gui, show_mouse=self.show_mouse)
            self.driver.maximize()
            result["scriptable"] = True
            result["credentials_entered"] = True
            result["title"] = self.driver.snapshot().title
            result["tcode"] = self.driver.snapshot().tcode
            self.online = True
            self.status_msg = "Online COM session"
        except CredentialsEnteredNoScripting as e:
            result["credentials_entered"] = True
            result["scriptable"] = False
            result["message"] = str(e)
            self.status_msg = "Credentials typed; scripting limited"
            # Try attach if a session appeared after login
            try:
                self.driver = open_live_session(attach=True)
                self.driver.show_mouse = self.show_mouse
                self.online = True
                result["scriptable"] = True
                result["attached_after_login"] = True
                result["title"] = self.driver.snapshot().title
            except Exception:
                pass
        except Exception as e:
            # Last resort: attach existing
            try:
                self.driver = open_live_session(attach=True)
                self.driver.show_mouse = self.show_mouse
                self.online = True
                result["scriptable"] = True
                result["attached"] = True
                result["title"] = self.driver.snapshot().title
                result["prior_error"] = str(e)
            except Exception as e2:
                result["error"] = f"{e}; attach failed: {e2}"
                self.journal.append("mega_login_fail", result)
                return result

        self._init_channels()
        self.journal.append("mega_login_ok", result)
        return result

    def attach(self) -> dict[str, Any]:
        self.driver = open_live_session(attach=True)
        self.driver.show_mouse = self.show_mouse
        self.online = True
        self._init_channels()
        snap = self.driver.snapshot()
        info = {"attached": True, "title": snap.title, "tcode": snap.tcode}
        self.journal.append("mega_attach", info)
        return info

    def _init_channels(self) -> None:
        rfc = connect_live_rfc(self.connection)
        try:
            self.extractor = OnlineExtractor(
                rfc=rfc, driver=self.driver, allow_mock=self.allow_mock
            )
        except Exception as e:
            if self.allow_mock:
                self.extractor = OnlineExtractor(allow_mock=True)
                log.warning("Online extract fallback mock: %s", e)
            else:
                # GUI-only extract if driver live
                if self.driver and not isinstance(self.driver.session, MockGuiSession):
                    self.extractor = OnlineExtractor(
                        rfc=None, driver=self.driver, allow_mock=False
                    )
                else:
                    raise
        if self.driver:
            self.injector = DataInjector(self.driver)

    # ------------------------------------------------------------------ extract
    def extract_tables(
        self, tables: list[str], options: dict[str, list[str]] | None = None, rowcount: int = 50
    ) -> dict[str, Any]:
        self._need_extractor()
        out = {}
        for t in tables:
            opts = (options or {}).get(t)
            out[t] = self.extractor.read_table(t, options=opts, rowcount=rowcount)
        self.journal.append("mega_extract_tables", {"tables": list(out.keys()), "mode": self.extractor.mode})
        return {"mode": self.extractor.mode, "data": out}

    def gather(self, pack_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need_extractor()
        pack = self.extractor.gather_pack(pack_id, params)
        self.last_pack = pack
        self.journal.append("mega_gather", pack.to_dict())
        return pack.to_dict()

    def debug(self, symptom: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need_extractor()
        from sapilot.know.gather import ScenarioDataGatherer

        assert self.extractor.rfc is not None
        pack = ScenarioDataGatherer(self.extractor.rfc).debug_message(symptom, params)
        self.last_pack = pack
        self.journal.append("mega_debug", pack.to_dict())
        return pack.to_dict()

    # ------------------------------------------------------------------ inject + run
    def inject(self, values: dict[str, str]) -> dict[str, Any]:
        if not self.injector or not self.driver:
            raise RuntimeError("No live GUI session for inject — login/attach first")
        res = self.injector.inject_map(values)
        self.journal.append("mega_inject", res)
        return res

    def inject_from_last_pack(self, table: str, fields: list[str] | None = None) -> dict[str, Any]:
        if not self.last_pack or not self.injector:
            raise RuntimeError("Gather a pack first, and login to GUI")
        res = self.injector.inject_from_pack(
            {k: v.to_dict() for k, v in self.last_pack.tables.items()},
            table,
            fields,
        )
        self.journal.append("mega_inject_pack", res)
        return res

    def goto(self, tcode: str) -> dict[str, Any]:
        if not self.driver:
            raise RuntimeError("Login/attach first")
        from sapilot.policy.guard import authorize_write

        authorize_write(
            "goto",
            tcode=str(tcode).upper(),
            target=str(tcode),
            logical="mega_goto",
        )
        snap = self.driver.start_transaction(tcode)
        info = {"tcode": snap.tcode, "title": snap.title, "status": self.driver.status_bar()}
        self.journal.append("mega_goto", info)
        return info

    def run_scenario(
        self,
        scenario_id: str,
        params: dict[str, Any] | None = None,
        *,
        require_ready: bool = False,
        inject_table: str | None = None,
        inject_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Full mega pipeline for one scenario:
          gather online data → optional inject first row into GUI → execute steps
        """
        params = params or {}
        pack_dict = None
        try:
            pack_dict = self.gather(scenario_id, params)
        except Exception as e:
            log.warning("gather for %s: %s", scenario_id, e)

        if require_ready and pack_dict and not pack_dict.get("ready"):
            return {
                "ok": False,
                "blocked": True,
                "pack": pack_dict,
                "journal": str(self.journal.path),
            }

        if inject_table and self.injector and pack_dict:
            try:
                self.inject_from_last_pack(inject_table, inject_fields)
            except Exception as e:
                log.warning("inject: %s", e)

        if not self.driver:
            return {
                "ok": False,
                "error": "No GUI session — login first",
                "pack": pack_dict,
                "journal": str(self.journal.path),
            }

        assert self.extractor and self.extractor.rfc is not None
        orch = ScenarioOrchestrator(
            self.extractor.rfc, driver=self.driver, journal=self.journal
        )
        result = orch.execute(
            scenario_id, params, require_ready=False, skip_gather=True
        )
        if pack_dict:
            result["data_pack"] = pack_dict
        result["extract_mode"] = self.extractor.mode if self.extractor else None
        result["online"] = self.online
        return result

    def screen(self) -> dict[str, Any]:
        if not self.driver:
            raise RuntimeError("No GUI")
        from sapilot.copilot.knowledge import DataExtractor

        return DataExtractor(driver=self.driver).screen_summary()

    def mouse_demo(self) -> None:
        from sapilot.connect.mouse import demo_wiggle

        demo_wiggle()

    def list_capabilities(self) -> dict[str, Any]:
        return {
            "packs": list_packs(),
            "sessions": GuiSession.list_open_sessions(),
            "online": self.online,
            "extract_mode": self.extractor.mode if self.extractor else None,
            "show_mouse": self.show_mouse,
            "journal": str(self.journal.path),
        }

    def _need_extractor(self) -> None:
        if self.extractor is None:
            if self.allow_mock:
                self.extractor = OnlineExtractor(allow_mock=True)
            else:
                raise RuntimeError("Call login() or attach() first for online extraction")
