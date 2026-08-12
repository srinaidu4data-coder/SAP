"""
SuperSuccessBot — ONLINE GUI is the product path.

This tool exists to drive SAP **on screen** (mouse + StartTransaction + fields).
Digital twin / table logic prepares data and verifies fingerprints, but a mission
is NOT SUCCESS unless live GUI navigation ran (unless SAPILOT_OFFLINE=1 for CI only).

Hard rules:
  1. Default: require live scriptable SAP GUI + visible mouse
  2. Never treat "GUI skipped" as success
  3. Twin is support channel only — not a substitute for online success
  4. StartTransaction / okcd only — never /n into data fields
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sapilot.autobot.consultant import ALL_MISSIONS
from sapilot.autobot.digital_twin import DigitalTwin
from sapilot.autobot.human_operator import HumanOperator
from sapilot.autobot.navigator import SafeNavigator
from sapilot.autobot.online_health import run_with_timeout
from sapilot.autobot.playbooks import FLEET_REQUIRED, PROCESS_CHAINS, all_super_plans, build_mission_plan
from sapilot.autobot.success_engine import (
    Channel,
    MissionPlan,
    PlanStep,
    SuccessCriteria,
    SuccessEngine,
)
from sapilot.know.gather import ScenarioDataGatherer
from sapilot.mission.precision import (
    JournalHashChain,
    PACK_EXACT,
    scan_rows_for_tcode_pollution,
    utc_iso,
    verify_document_chain_invariants,
    verify_pack_exact,
)
from sapilot.report.journal import RunJournal

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]


def _offline_ci_mode() -> bool:
    """CI/unit tests only — never the product default."""
    return os.environ.get("SAPILOT_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


class SuperSuccessBot:
    """Online-first SAP bot: GUI is mandatory for SUCCESS (product mode)."""

    def __init__(
        self,
        *,
        use_live_gui: bool | None = None,
        show_mouse: bool | None = None,
        auto_remediate: bool = True,
        require_gui: bool | None = None,
    ):
        # Product default: ONLINE. Only SAPILOT_OFFLINE=1 opts out for CI.
        offline = _offline_ci_mode()
        if use_live_gui is None:
            if offline:
                self.use_live_gui = False
            else:
                # Default ON unless explicitly set to 0
                self.use_live_gui = os.environ.get("SAPILOT_LIVE_GUI", "1").strip().lower() not in {
                    "0",
                    "false",
                    "no",
                }
        else:
            self.use_live_gui = use_live_gui

        if show_mouse is None:
            self.show_mouse = self.use_live_gui and os.environ.get("SAPILOT_SHOW_MOUSE", "1").strip().lower() not in {
                "0",
                "false",
                "no",
            }
        else:
            self.show_mouse = bool(show_mouse) and self.use_live_gui

        # Product: GUI required for SUCCESS. CI offline: data-only SUCCESS allowed.
        if require_gui is None:
            self.require_gui = self.use_live_gui and not offline
        else:
            self.require_gui = require_gui

        self.auto_remediate = auto_remediate
        self.gui_session_bound = False
        self.gui_bind_error = ""

        # Force env so COM bind is not refused
        if self.use_live_gui:
            os.environ["SAPILOT_LIVE_GUI"] = "1"
            os.environ["SAPILOT_FORCE_COM_BIND"] = "1"
            if self.show_mouse:
                os.environ["SAPILOT_SHOW_MOUSE"] = "1"

        self.twin = DigitalTwin()
        self.operator = HumanOperator(show_mouse=self.show_mouse)
        self.journal = RunJournal()
        data = Path(os.environ.get("SAPILOT_DATA", _ROOT / "data"))
        chain_path = data / "runs" / "SUPER_BOT_CHAIN.jsonl"
        if chain_path.exists():
            try:
                chain_path.replace(data / "runs" / "SUPER_BOT_CHAIN_prev.jsonl")
            except Exception:
                chain_path.unlink(missing_ok=True)
        self.chain = JournalHashChain(chain_path)

        self.engine = SuccessEngine(
            max_replans=2,
            max_step_attempts=3,
            on_log=self.say,
        )
        self._register_handlers()
        self.plans: list[MissionPlan] = []
        self.message_log: list[str] = []

        # Policy
        try:
            from sapilot.policy.guard import bind_write_context, is_lab_mode
            from sapilot.policy.tier import TierContext
            from sapilot.schemas import Tier

            tier = Tier.T1_SANDBOX if is_lab_mode() else Tier.T3_OBSERVE
            bind_write_context(
                TierContext(tier, os.environ.get("SAPILOT_CLIENT", "100"), "D"),
                approval_token=os.environ.get("SAPILOT_APPROVAL_TOKEN"),
                source="super_bot",
            )
        except Exception as e:
            self.say(f"Policy bind: {e}")
    def say(self, msg: str) -> None:
        self.message_log.append(msg)
        self.journal.append("super_say", {"msg": msg})
        log.info("SUPER: %s", msg)
        print(f"[SUPER] {msg}")

    def log_chain(self, event: str, payload: Any) -> None:
        self.chain.append(event, payload)

    def _register_handlers(self) -> None:
        e = self.engine
        e.register("gather", self._h_gather)
        e.register("remediate", self._h_remediate)
        e.register("invent", self._h_invent)
        e.register("ensure_ready", self._h_ensure_ready)
        e.register("fingerprint", self._h_fingerprint)
        e.register("navigate", self._h_navigate)
        e.register("verify", self._h_verify)
        e.register("note", self._h_note)

    # ------------------------------------------------------------------ handlers
    def _h_gather(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        pack_id = step.params.get("pack") or plan.context.get("pack_id")
        g = ScenarioDataGatherer(self.twin.rfc)
        pack = g.gather(pack_id)
        pollution = scan_rows_for_tcode_pollution(pack.tables)
        counts = {k: v.count for k, v in pack.tables.items()}
        exact = []
        if pack_id in PACK_EXACT:
            exact = verify_pack_exact(pack.tables, PACK_EXACT[pack_id])
        ctx_update = {
            "pack_id": pack_id,
            "pack_ready": pack.ready,
            "pack_summary": pack.summary,
            "table_counts": counts,
            "pollution": pollution,
            "exact_errors": exact,
        }
        plan.context.update(ctx_update)
        ok = pack.ready or step.params.get("allow_not_ready")
        # gather succeeds if we got tables; readiness may need remediate
        return {
            "ok": len(pack.tables) > 0,
            "ready": pack.ready,
            "tables": counts,
            "pollution": pollution,
            "context_update": ctx_update,
        }

    def _h_remediate(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        kind = step.params.get("kind") or ""
        fixes = self._remediate(kind)
        return {"ok": True, "fixes": fixes, "context_update": {"last_fixes": fixes}}

    def _h_invent(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        """Twin invent = BAPI analog when live create blocked (research hybrid)."""
        pack = step.params.get("pack") or plan.context.get("pack_id") or ""
        fixes: list[str] = []
        if pack.startswith("ptp") or plan.mission_id.startswith("S"):
            self.twin.ensure_po_chain()
            fixes.extend(self.twin.ensure_vendor_payment_ready())
            fixes.append("PTP chain invented/sealed")
        if pack.startswith("otc") or plan.mission_id.startswith("O"):
            self.twin.ensure_otc_chain()
            fixes.extend(self.twin.ensure_customer_payment_ready())
            fixes.append("OTC chain invented/sealed")
        if not fixes:
            self.twin.ensure_po_chain()
            self.twin.ensure_otc_chain()
            fixes = ["full landscape sealed"]
        return {"ok": True, "fixes": fixes, "channel": Channel.TWIN.value}

    def _h_ensure_ready(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        if plan.context.get("pack_ready"):
            return {"ok": True, "skipped": True}
        # invent then rely on next gather
        return self._h_invent(step, plan)

    def _h_fingerprint(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        pack_id = step.params.get("pack") or plan.context.get("pack_id")
        g = ScenarioDataGatherer(self.twin.rfc)
        pack = g.gather(pack_id)
        if pack_id not in PACK_EXACT:
            return {"ok": False, "error": f"no fingerprint for {pack_id}"}
        errs = verify_pack_exact(pack.tables, PACK_EXACT[pack_id])
        plan.context["exact_errors"] = errs
        plan.context["pack_ready"] = pack.ready
        plan.context["table_counts"] = {k: v.count for k, v in pack.tables.items()}
        plan.context["pollution"] = scan_rows_for_tcode_pollution(pack.tables)
        return {
            "ok": len(errs) == 0 and not plan.context["pollution"],
            "exact_errors": errs,
            "error": "; ".join(errs[:5]) if errs else "",
        }

    def _h_navigate(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        """
        ONLINE path — product core.
        Skipping GUI is NEVER success when require_gui=True.
        """
        if not self.use_live_gui or not self.require_gui:
            # Explicit CI offline only
            plan.context["gui_ok"] = False
            plan.context["gui_skipped_offline_ci"] = True
            return {
                "ok": True,
                "skipped": True,
                "reason": "SAPILOT_OFFLINE=1 CI data path (not product success)",
                "context_update": {"gui_ok": False, "gui_skipped_offline_ci": True},
            }

        if self.operator._session is None:
            ok_b, bound, err = run_with_timeout(
                lambda: self.operator.try_bind_open_session(),
                timeout_s=6.0,
                default=False,
            )
            if not (ok_b and bound):
                plan.context["gui_ok"] = False
                msg = (
                    "ONLINE REQUIRED: no scriptable SAP GUI session. "
                    "Enable scripting (Logon Options + RZ11 sapgui/user_scripting=TRUE), "
                    "log into Vista, then re-run. "
                    f"bind_error={err or self.gui_bind_error or 'none'}"
                )
                return {"ok": False, "error": msg, "context_update": {"gui_ok": False}}

        try:
            nav = SafeNavigator(self.operator._session, show_mouse=self.show_mouse)
            mid = step.params.get("mission_id") or plan.mission_id
            result = nav.run_mission_gui(mid)
            for k, v in (result.get("filled") or {}).items():
                val = str(v.get("value") or "")
                if val.upper().startswith("/N") or val.upper().startswith("/O"):
                    plan.context["gui_ok"] = False
                    return {
                        "ok": False,
                        "error": f"tcode in field {k}={val}",
                        "context_update": {"gui_ok": False},
                    }
            gui_ok = bool(result.get("ok", True))
            plan.context["gui_ok"] = gui_ok
            plan.context["gui_result"] = {
                "tcode": result.get("tcode"),
                "status": result.get("status"),
                "filled": result.get("filled"),
            }
            return {
                "ok": gui_ok,
                "gui": result,
                "error": "" if gui_ok else (result.get("error") or "GUI nav failed"),
                "context_update": {"gui_ok": gui_ok},
            }
        except Exception as e:
            plan.context["gui_ok"] = False
            return {
                "ok": False,
                "error": f"GUI navigate exception: {e}",
                "context_update": {"gui_ok": False},
            }
    def _h_verify(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        pack_id = step.params.get("pack") or plan.context.get("pack_id")
        g = ScenarioDataGatherer(self.twin.rfc)
        pack = g.gather(pack_id)
        exact = (
            verify_pack_exact(pack.tables, PACK_EXACT[pack_id])
            if pack_id in PACK_EXACT
            else []
        )
        pollution = scan_rows_for_tcode_pollution(pack.tables)
        plan.context.update(
            {
                "pack_ready": pack.ready,
                "exact_errors": exact,
                "pollution": pollution,
                "table_counts": {k: v.count for k, v in pack.tables.items()},
                "pack_summary": pack.summary,
            }
        )
        ok = pack.ready and not exact and not pollution
        return {
            "ok": ok,
            "ready": pack.ready,
            "exact_errors": exact,
            "pollution": pollution,
            "error": "" if ok else pack.summary or str(exact or pollution),
        }

    def _h_note(self, step: PlanStep, plan: MissionPlan) -> dict[str, Any]:
        text = step.params.get("text") or ""
        plan.reflections.append(text)
        return {"ok": True, "note": text}

    def _remediate(self, kind: str) -> list[str]:
        if kind in ("payment_vendor", "payment_full"):
            return self.twin.ensure_vendor_payment_ready()
        if kind == "ensure_chain":
            self.twin.ensure_po_chain()
            return ["PTP chain sealed"]
        if kind == "ensure_otc":
            self.twin.ensure_otc_chain()
            return ["OTC chain sealed"]
        if kind == "otc_payment":
            return self.twin.ensure_customer_payment_ready()
        if kind == "ensure_abap":
            return self.twin.ensure_abap_debug_ready()
        return []

    def ensure_online_session(self) -> bool:
        """
        Bind or create a scriptable SAP GUI session. Product entry gate.
        Returns True only if COM session is usable.
        """
        if not self.use_live_gui:
            self.gui_bind_error = "use_live_gui=False (CI offline)"
            return False
        os.environ["SAPILOT_LIVE_GUI"] = "1"
        os.environ["SAPILOT_FORCE_COM_BIND"] = "1"
        if self.show_mouse:
            os.environ["SAPILOT_SHOW_MOUSE"] = "1"

        ok, bound, err = run_with_timeout(
            lambda: self.operator.try_bind_open_session(),
            timeout_s=6.0,
            default=False,
        )
        if ok and bound:
            self.gui_session_bound = True
            self.say("ONLINE: scriptable SAP session bound — mouse navigation enabled")
            return True

        # Try vault login (Vista) then re-bind
        self.say("ONLINE: no open session — attempting vault logon (vista)…")
        try:
            from sapilot.connect.logon import gui_logon_from_vault
            from sapilot.security.vault import CredentialVault

            def _login() -> str:
                vault = CredentialVault(
                    passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE") or "sapilot-local"
                )
                name = os.environ.get("SAPILOT_CONNECTION") or "vista"
                gui_logon_from_vault(name, vault)
                return "ok"

            lok, _, lerr = run_with_timeout(_login, timeout_s=60.0, default="")
            if lok:
                ok2, bound2, err2 = run_with_timeout(
                    lambda: self.operator.try_bind_open_session(),
                    timeout_s=8.0,
                    default=False,
                )
                if ok2 and bound2:
                    self.gui_session_bound = True
                    self.say("ONLINE: logged on via vault + session bound")
                    return True
                self.gui_bind_error = f"post-login bind failed: {err2}"
            else:
                self.gui_bind_error = f"vault login failed: {lerr or err}"
        except Exception as e:
            self.gui_bind_error = f"login path error: {e}"

        self.gui_session_bound = False
        self.say(
            "ONLINE BLOCKED: " + (self.gui_bind_error or err or "no SAP GUI scripting session")
        )
        self.say(
            "Fix: SAP Logon → Enable Scripting; RZ11 sapgui/user_scripting=TRUE; "
            "log into Vista; re-run with SAPILOT_SHOW_MOUSE=1"
        )
        return False

    # ------------------------------------------------------------------ fleet
    def run_all(self) -> dict[str, Any]:
        self.say("=" * 60)
        self.say("SUPER SUCCESS BOT — ONLINE GUI FIRST (product mode)")
        self.say(
            f"require_gui={self.require_gui} live_gui={self.use_live_gui} "
            f"show_mouse={self.show_mouse} offline_ci={_offline_ci_mode()}"
        )
        self.say("=" * 60)
        self.log_chain(
            "super_start",
            {
                "ts": utc_iso(),
                "missions": len(ALL_MISSIONS),
                "live_gui": self.use_live_gui,
                "require_gui": self.require_gui,
                "product": "online_gui_first",
            },
        )

        # ONLINE GATE — do not pretend GUI will work later
        if self.require_gui:
            bound = self.ensure_online_session()
            self.log_chain(
                "online_gate",
                {"bound": bound, "error": self.gui_bind_error},
            )
            if not bound:
                self.say(
                    "ABORTING FLEET AS ONLINE FAILURE — twin data will still run for "
                    "diagnostics but SUCCESS is impossible without GUI"
                )

        # Twin still prepares/verifies data (support channel)
        self.twin.ensure_po_chain()
        self.twin.ensure_otc_chain()
        self.twin.ensure_vendor_payment_ready()
        self.twin.ensure_customer_payment_ready()
        self.twin.ensure_abap_debug_ready()
        inv = verify_document_chain_invariants(self.twin)
        self.log_chain("chain_invariants", {"ok": len(inv) == 0, "errors": inv})
        if inv:
            self.say(f"Chain invariant warnings: {inv}")

        self.plans = []
        for mission in ALL_MISSIONS:
            plan = build_mission_plan(mission)
            # Product criterion: GUI must have run
            if self.require_gui:
                plan.criteria.append(
                    SuccessCriteria(
                        id="gui_online",
                        description="Live SAP GUI navigation executed (not skipped)",
                        check=lambda c: bool(c.get("gui_ok")),
                        severity="blocker",
                    )
                )
            plan.context["require_gui"] = self.require_gui
            self.say(f"—— {plan.mission_id}: {plan.title} ——")
            result = self.engine.run_plan(plan)
            self.plans.append(result)
            self.log_chain(
                "mission_result",
                {
                    "id": result.mission_id,
                    "outcome": result.outcome,
                    "score": result.success_score,
                    "verified": result.verified,
                },
            )
            self.journal.append("super_mission", result.to_dict())

        # Fleet invariants again
        inv_post = verify_document_chain_invariants(self.twin)
        chain_ok, chain_errs = self.chain.verify_chain()

        success_n = sum(1 for p in self.plans if p.outcome == "SUCCESS" and p.verified)
        partial_n = sum(1 for p in self.plans if p.outcome == "PARTIAL")
        fail_n = sum(1 for p in self.plans if p.outcome == "FAIL")
        avg_score = (
            sum(p.success_score for p in self.plans) / len(self.plans) if self.plans else 0
        )

        # Process chain integrity: all PTP then all OTC ordered
        ptp_ok = all(
            p.outcome == "SUCCESS"
            for p in self.plans
            if p.mission_id in PROCESS_CHAINS["PTP"]
        )
        otc_ok = all(
            p.outcome == "SUCCESS"
            for p in self.plans
            if p.mission_id in PROCESS_CHAINS["OTC"]
        )
        abap_ok = all(
            p.outcome == "SUCCESS"
            for p in self.plans
            if p.mission_id in PROCESS_CHAINS["ABAP"]
        )
        ptp_n = sum(1 for p in self.plans if p.mission_id.startswith("S") and p.outcome == "SUCCESS")
        otc_n = sum(1 for p in self.plans if p.mission_id.startswith("O") and p.outcome == "SUCCESS")
        abap_n = sum(1 for p in self.plans if p.mission_id.startswith("A") and p.outcome == "SUCCESS")
        gui_ok_n = sum(1 for p in self.plans if p.context.get("gui_ok"))
        fleet_ok = (
            ptp_n >= FLEET_REQUIRED["ptp"]
            and otc_n >= FLEET_REQUIRED["otc"]
            and abap_n >= FLEET_REQUIRED["abap"]
            and success_n == FLEET_REQUIRED["total"]
        )
        # Product all_success requires online GUI when require_gui
        online_ok = (not self.require_gui) or (
            self.gui_session_bound and gui_ok_n == len(self.plans)
        )
        all_success = (
            success_n == len(self.plans)
            and fleet_ok
            and len(inv_post) == 0
            and chain_ok
            and online_ok
        )

        summary = {
            "success_count": success_n,
            "partial_count": partial_n,
            "fail_count": fail_n,
            "total": len(self.plans),
            "required_total": FLEET_REQUIRED["total"],
            "ptp_ok_count": ptp_n,
            "otc_ok_count": otc_n,
            "abap_ok_count": abap_n,
            "gui_ok_count": gui_ok_n,
            "gui_session_bound": self.gui_session_bound,
            "require_gui": self.require_gui,
            "online_product": True,
            "true_online": bool(self.gui_session_bound and gui_ok_n == len(self.plans) and all_success),
            "gui_bind_error": self.gui_bind_error,
            "all_success": all_success,
            "avg_score": round(avg_score, 4),
            "ptp_chain_ok": ptp_ok,
            "otc_chain_ok": otc_ok,
            "abap_chain_ok": abap_ok,
            "fleet_exhausted": fleet_ok and online_ok,
            "document_invariants": inv_post,
            "journal_chain_valid": chain_ok,
            "journal_chain_errors": chain_errs,
            "chain_path": str(self.chain.path),
            "run_journal": str(self.journal.path),
            "standard": "SuperSuccessBot ONLINE-GUI-FIRST 10PTP+10OTC+2ABAP v3",
        }
        self.log_chain("super_end", summary)

        out = Path(os.environ.get("SAPILOT_DATA", _ROOT / "data")) / "runs" / "SUPER_BOT_22.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": summary,
            "missions": [p.to_dict() for p in self.plans],
            "messages": self.message_log[-200:],
        }
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        summary["report"] = str(out)

        self._print_board(summary)
        return summary

    def _print_board(self, summary: dict[str, Any]) -> None:
        print()
        print("=" * 72)
        print("SUPER SUCCESS BOT — SCOREBOARD")
        print("=" * 72)
        for p in self.plans:
            flag = {
                "SUCCESS": "PASS",
                "PARTIAL": "PART",
                "FAIL": "FAIL",
            }.get(p.outcome, p.outcome)
            print(
                f"  {flag:4}  {p.mission_id:16}  score={p.success_score:.2f}  "
                f"verified={p.verified}  {p.title[:40]}"
            )
        print("=" * 72)
        print(
            f"SUCCESS: {summary['success_count']}/{summary['total']}  "
            f"GUI: {summary.get('gui_ok_count')}/{summary['total']}  "
            f"session={summary.get('gui_session_bound')}  "
            f"true_online={summary.get('true_online')}  "
            f"all_success={summary['all_success']}  "
            f"PTP={summary['ptp_ok_count']}/10 OTC={summary['otc_ok_count']}/10 "
            f"ABAP={summary['abap_ok_count']}/2 fleet={summary['fleet_exhausted']}"
        )
        print("Report:", summary.get("report"))
        print("Chain: ", summary.get("chain_path"))


def main() -> int:
    os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
    os.environ.setdefault("SAPILOT_LAB", "1")
    os.environ.setdefault("SAPILOT_DATA", str(_ROOT / "data"))
    # Product defaults: online GUI + mouse unless CI set SAPILOT_OFFLINE=1
    if not _offline_ci_mode():
        os.environ.setdefault("SAPILOT_LIVE_GUI", "1")
        os.environ.setdefault("SAPILOT_FORCE_COM_BIND", "1")
        os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")
    bot = SuperSuccessBot()
    summary = bot.run_all()
    if not summary.get("gui_session_bound") and summary.get("require_gui"):
        print(
            "\n*** PRODUCT MODE: ONLINE GUI REQUIRED ***\n"
            "Mouse did not run because SAP scripting session was unavailable.\n"
            "This is a FAILURE for the product bar — not a deliberate skip.\n"
            f"Detail: {summary.get('gui_bind_error')}\n"
        )
    return 0 if summary.get("all_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
