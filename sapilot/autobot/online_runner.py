"""
Online scenario runner — goal of Karpathy loops.

Cascade when live:
  1. Bind/create scriptable session (timeout-safe)
  2. Policy bind T1 lab / approved T2
  3. Multi-table extract: RFC else twin warm-start + SE16N attempt
  4. SafeNavigator mission GUI
  5. Verify fingerprints where twin/canon; live rows structural ready

When not online-capable: fail closed with remediation list (never fake online).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sapilot.autobot.consultant import ALL_MISSIONS
from sapilot.autobot.digital_twin import DigitalTwin
from sapilot.autobot.human_operator import HumanOperator
from sapilot.autobot.online_health import OnlineHealth, probe_online_health, run_with_timeout
from sapilot.autobot.navigator import SafeNavigator
from sapilot.know.gather import ScenarioDataGatherer
from sapilot.mission.precision import (
    PACK_EXACT,
    scan_rows_for_tcode_pollution,
    utc_iso,
    verify_pack_exact,
)
from sapilot.report.journal import RunJournal

log = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class OnlineMissionResult:
    id: str
    title: str
    ok: bool
    mode: str  # online_gui | hybrid | offline_fallback | blocked
    pack_ready: bool = False
    gui_ok: bool = False
    exact_errors: list[str] = field(default_factory=list)
    notes: str = ""
    table_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OnlineScenarioRunner:
    def __init__(self, *, allow_offline_fallback: bool | None = None):
        # Product default: NO offline success. CI only: SAPILOT_OFFLINE=1
        offline = os.environ.get("SAPILOT_OFFLINE", "").strip().lower() in {"1", "true", "yes"}
        if allow_offline_fallback is None:
            self.allow_offline_fallback = offline
        else:
            self.allow_offline_fallback = allow_offline_fallback
        os.environ.setdefault("SAPILOT_LIVE_GUI", "1")
        os.environ.setdefault("SAPILOT_FORCE_COM_BIND", "1")
        os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")
        self.health = probe_online_health()
        self.twin = DigitalTwin()
        self.operator = HumanOperator(
            show_mouse=os.environ.get("SAPILOT_SHOW_MOUSE", "1").strip() not in {"0", "false"}
        )
        self.journal = RunJournal()
        self.results: list[OnlineMissionResult] = []
        self._bind_policy()

    def _bind_policy(self) -> None:
        try:
            from sapilot.policy.guard import bind_write_context, is_lab_mode
            from sapilot.policy.tier import TierContext
            from sapilot.schemas import Tier

            tier = Tier.T1_SANDBOX if is_lab_mode() else Tier.T3_OBSERVE
            bind_write_context(
                TierContext(tier, os.environ.get("SAPILOT_CLIENT", "100"), "D"),
                approval_token=os.environ.get("SAPILOT_APPROVAL_TOKEN"),
                source="online_runner",
            )
        except Exception as e:
            log.warning("policy bind: %s", e)

    def _try_bind_session(self) -> bool:
        os.environ["SAPILOT_FORCE_COM_BIND"] = "1"
        os.environ["SAPILOT_LIVE_GUI"] = "1"
        if not self.health.scripting_engine and self.health.open_sessions == 0:
            self.health = probe_online_health()
        # Always attempt timeout-safe bind when COM exists; health may lag
        ok, bound, err = run_with_timeout(
            lambda: self.operator.try_bind_open_session(),
            timeout_s=5.0,
            default=False,
        )
        if ok and bound:
            return True
        # Optional auto-login from vault if no session
        if self.health.vault_ok and not bound:
            try:
                from sapilot.connect.logon import gui_logon_from_vault
                from sapilot.security.vault import CredentialVault

                def _login() -> bool:
                    vault = CredentialVault(
                        passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE") or "sapilot-local"
                    )
                    name = os.environ.get("SAPILOT_CONNECTION") or "vista"
                    gui_logon_from_vault(name, vault)
                    return True

                lok, _, lerr = run_with_timeout(_login, timeout_s=45.0, default=False)
                if lok:
                    ok2, bound2, _ = run_with_timeout(
                        lambda: self.operator.try_bind_open_session(),
                        timeout_s=5.0,
                        default=False,
                    )
                    return bool(ok2 and bound2)
                log.info("auto-login: %s", lerr)
            except Exception as e:
                log.info("auto-login skipped: %s", e)
        return False

    def run_all(self) -> dict[str, Any]:
        self.health = probe_online_health()
        self.journal.append("online_start", {"health": self.health.to_dict(), "ts": utc_iso()})
        # Always attempt online bind in product mode — never "skip on purpose"
        os.environ["SAPILOT_LIVE_GUI"] = "1"
        os.environ["SAPILOT_FORCE_COM_BIND"] = "1"
        os.environ["SAPILOT_SHOW_MOUSE"] = "1"
        bound = self._try_bind_session()

        self.twin.ensure_po_chain()
        self.twin.ensure_otc_chain()
        self.twin.ensure_vendor_payment_ready()
        self.twin.ensure_customer_payment_ready()
        self.twin.ensure_abap_debug_ready()

        if bound:
            mode_global = "online_gui"
        elif self.allow_offline_fallback:
            mode_global = "offline_fallback_ci_only"
        else:
            mode_global = "online_required_failed"

        for mission in ALL_MISSIONS:
            self.results.append(self._run_one(mission, bound=bound, mode=mode_global))

        ok_n = sum(1 for r in self.results if r.ok)
        # Online perfection: all ok AND actually used GUI or hybrid with session
        true_online = bound and ok_n == len(self.results)
        summary = {
            "ts": utc_iso(),
            "ok_count": ok_n,
            "total": len(self.results),
            "all_ok": ok_n == len(self.results),
            "true_online": true_online,
            "session_bound": bound,
            "mode": mode_global,
            "health": self.health.to_dict(),
            "health_score": self.health.score,
            "blockers": self.health.blockers,
        }
        self.journal.append("online_end", summary)
        out = Path(os.environ.get("SAPILOT_DATA", _ROOT / "data")) / "runs" / "ONLINE_22.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": summary, "results": [r.to_dict() for r in self.results]}, indent=2),
            encoding="utf-8",
        )
        summary["report"] = str(out)
        return summary

    def _run_one(self, mission: dict[str, Any], *, bound: bool, mode: str) -> OnlineMissionResult:
        mid = mission["id"]
        pack_id = mission["pack"]
        g = ScenarioDataGatherer(self.twin.rfc)
        # Prefer twin for reliability; live SE16N is enhancement when bound
        if mission.get("remediate"):
            self._remediate(mission["remediate"])
        pack = g.gather(pack_id)
        exact = verify_pack_exact(pack.tables, PACK_EXACT[pack_id]) if pack_id in PACK_EXACT else []
        pollution = scan_rows_for_tcode_pollution(pack.tables)
        counts = {k: v.count for k, v in pack.tables.items()}

        gui_ok = False
        notes = []
        if bound and self.operator._session is not None:
            try:
                nav = SafeNavigator(self.operator._session, show_mouse=True)
                res = nav.run_mission_gui(mid)
                gui_ok = bool(res.get("ok"))
                notes.append(f"gui tcode={res.get('tcode')} status={res.get('status')!r}")
                for k, v in (res.get("filled") or {}).items():
                    val = str(v.get("value") or "")
                    if val.upper().startswith("/N") or val.upper().startswith("/O"):
                        gui_ok = False
                        notes.append(f"PRECISION FAIL tcode in {k}")
            except Exception as e:
                notes.append(f"gui error: {e}")
                gui_ok = False
        else:
            notes.append("gui skipped — no scriptable session")

        data_ok = pack.ready and not exact and not pollution
        # Product: SUCCESS only with real GUI. Offline fallback = CI diagnostics only.
        if bound:
            ok = data_ok and gui_ok
            used_mode = "online_gui" if gui_ok else "gui_nav_failed"
        else:
            ok = data_ok and self.allow_offline_fallback
            used_mode = (
                "offline_fallback_ci_only" if self.allow_offline_fallback else "online_required_failed"
            )
            if not self.allow_offline_fallback:
                notes.append("PRODUCT FAIL: online GUI required — not skipped deliberately")

        return OnlineMissionResult(
            id=mid,
            title=mission["title"],
            ok=ok,
            mode=used_mode,
            pack_ready=pack.ready,
            gui_ok=gui_ok,
            exact_errors=exact,
            notes="; ".join(notes),
            table_counts=counts,
        )

    def _remediate(self, kind: str) -> None:
        if kind in ("payment_vendor", "payment_full"):
            self.twin.ensure_vendor_payment_ready()
        elif kind == "ensure_chain":
            self.twin.ensure_po_chain()
        elif kind == "ensure_otc":
            self.twin.ensure_otc_chain()
        elif kind == "otc_payment":
            self.twin.ensure_customer_payment_ready()
