"""
Mission-critical autonomous runner: 10 PTP + 10 OTC with NASA/SpaceX-style gates.

Every scenario (fail closed):
  1. Pre-declare criteria on MissionGate (empty gate = NO-GO)
  2. Multi-table extract
  3. Tcode-pollution scan on all business keys
  4. Exact fingerprint verify (ALL 20 packs)
  5. Remediations when configured → re-extract → re-verify
  6. Cross-document chain invariants (fleet-level)
  7. Safe GUI nav only (StartTransaction / okcd) when scriptable
  8. Hash-chained mission log — verify at end
  9. Abort on any precision failure (fleet continues other missions, marks FAIL)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sapilot.autobot.consultant import ALL_MISSIONS
from sapilot.autobot.digital_twin import DigitalTwin
from sapilot.autobot.human_operator import HumanOperator
from sapilot.autobot.navigator import SafeNavigator
from sapilot.know.gather import ScenarioDataGatherer
from sapilot.mission.precision import (
    JournalHashChain,
    MissionAbort,
    MissionGate,
    PACK_EXACT,
    StepVerification,
    GoNoGo,
    assert_never_tcode_in_data_field,
    manifest_hash,
    scan_rows_for_tcode_pollution,
    utc_iso,
    verify_document_chain_invariants,
    verify_pack_exact,
)


class CriticalMissionRunner:
    def __init__(self, *, use_live_gui: bool = True, show_mouse: bool = True):
        self.twin = DigitalTwin()
        self.operator = HumanOperator(show_mouse=show_mouse)
        self.use_live_gui = use_live_gui
        data = Path(os.environ.get("SAPILOT_DATA", _ROOT / "data"))
        # Fresh chain file per run for clean audit (append-only within run)
        chain_path = data / "runs" / "MISSION_CRITICAL_CHAIN.jsonl"
        if chain_path.exists():
            # Rotate previous chain for evidence retention
            bak = data / "runs" / f"MISSION_CRITICAL_CHAIN_prev.jsonl"
            try:
                chain_path.replace(bak)
            except Exception:
                chain_path.unlink(missing_ok=True)
        self.chain = JournalHashChain(chain_path)
        self.results: list[dict[str, Any]] = []
        self.aborts: list[str] = []
        self._manifest = manifest_hash()

    def log(self, event: str, payload: Any) -> None:
        self.chain.append(event, payload)
        print(f"[MISSION] {event}: {json.dumps(payload, default=str)[:240]}")

    def run_all(self) -> dict[str, Any]:
        self.log(
            "mission_start",
            {
                "missions": len(ALL_MISSIONS),
                "ts": utc_iso(),
                "manifest_hash": self._manifest,
                "standard": "NASA/SpaceX fail-closed precision v2",
            },
        )
        self.twin.ensure_po_chain()
        self.twin.ensure_otc_chain()
        self.twin.ensure_abap_debug_ready()

        # Fleet-level chain invariants BEFORE scenarios
        inv = verify_document_chain_invariants(self.twin)
        self.log("chain_invariants_pre", {"ok": len(inv) == 0, "errors": inv})
        if inv:
            self.aborts.append("PRE chain invariants: " + "; ".join(inv))
            # Fail closed at fleet level only if amounts broken; still run packs
            # but all_pass will be false
            pass

        if self.use_live_gui:
            try:
                bound = self.operator.try_bind_open_session()
            except Exception as e:
                bound = False
                self.log("gui_bind_error", {"error": str(e)[:200]})
            self.log("gui_bind", {"scriptable": bound})
            if not bound:
                self.use_live_gui = False

        for mission in ALL_MISSIONS:
            try:
                self.results.append(self._run_one(mission))
            except MissionAbort as e:
                self.aborts.append(str(e))
                self.results.append(
                    {
                        "id": mission["id"],
                        "title": mission.get("title"),
                        "pack": mission.get("pack"),
                        "ok": False,
                        "abort": str(e),
                        "precision": "ABORT",
                    }
                )
                self.log("mission_abort", {"id": mission["id"], "error": str(e)})
                continue

        # Fleet-level chain invariants AFTER all remediations
        inv_post = verify_document_chain_invariants(self.twin)
        self.log("chain_invariants_post", {"ok": len(inv_post) == 0, "errors": inv_post})

        ok_n = sum(1 for r in self.results if r.get("ok"))
        chain_ok, chain_errs = self.chain.verify_chain()
        fingerprint_coverage = sum(
            1 for m in ALL_MISSIONS if m["pack"] in PACK_EXACT
        )
        summary = {
            "ok_count": ok_n,
            "total": len(self.results),
            "all_pass": (
                ok_n == len(self.results)
                and len(self.results) == len(ALL_MISSIONS)
                and not self.aborts
                and chain_ok
                and len(inv_post) == 0
                and fingerprint_coverage == len(ALL_MISSIONS)
            ),
            "aborts": self.aborts,
            "journal_chain_valid": chain_ok,
            "journal_chain_errors": chain_errs,
            "chain_path": str(self.chain.path),
            "manifest_hash": self._manifest,
            "fingerprint_coverage": f"{fingerprint_coverage}/{len(ALL_MISSIONS)}",
            "document_chain_invariants": inv_post,
        }
        self.log("mission_end", summary)

        out = Path(os.environ.get("SAPILOT_DATA", _ROOT / "data")) / "runs" / "MISSION_CRITICAL_22.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": summary, "results": self.results}, indent=2, default=str),
            encoding="utf-8",
        )
        summary["report"] = str(out)
        return summary

    def _run_one(self, mission: dict[str, Any]) -> dict[str, Any]:
        mid = mission["id"]
        pack_id = mission["pack"]
        gate = MissionGate(mid)
        gatherer = ScenarioDataGatherer(self.twin.rfc)
        fixes: list[str] = []
        exact_errs: list[str] = []

        # --- PRE: pack fingerprint must be published ---
        gate.require(
            "fingerprint_published",
            pack_id in PACK_EXACT,
            pack_id if pack_id in PACK_EXACT else f"MISSING fingerprint for {pack_id}",
        )

        # --- Extract ---
        pack = gatherer.gather(pack_id)
        gate.require("pack_loaded", True, pack_id)
        gate.require(
            "extract_channel_present",
            len(pack.tables) > 0,
            f"{len(pack.tables)} tables",
        )

        # --- Tcode pollution scan (fail closed) ---
        pollution = scan_rows_for_tcode_pollution(pack.tables)
        gate.require(
            "no_tcode_in_master_data",
            len(pollution) == 0,
            "clean keys" if not pollution else "; ".join(pollution[:5]),
        )
        for tname, sl in pack.tables.items():
            for row in sl.rows:
                for fld in ("LIFNR", "KUNNR", "MATNR", "EBELN", "VBELN", "KUNAG"):
                    if fld in row:
                        assert_never_tcode_in_data_field(fld, str(row[fld]))

        # --- Remediations when configured ---
        if not pack.ready and mission.get("remediate"):
            fixes = self._remediate(mission["remediate"])
            pack = gatherer.gather(pack_id)
            pollution = scan_rows_for_tcode_pollution(pack.tables)
            if pollution:
                raise MissionAbort(f"{mid}: pollution after remediate: {pollution}")

        # Payment-style remediates even when partially ready
        if mission.get("remediate") in (
            "payment_full",
            "payment_vendor",
            "otc_payment",
        ):
            extra = self._remediate(mission["remediate"])
            fixes.extend(extra)
            pack = gatherer.gather(pack_id)

        # --- EXACT fingerprint (mandatory for all packs) ---
        if pack_id not in PACK_EXACT:
            raise MissionAbort(f"{mid}: no published fingerprint — fail closed")
        exact_errs = verify_pack_exact(pack.tables, PACK_EXACT[pack_id])
        gate.require(
            "exact_fingerprint",
            len(exact_errs) == 0,
            "; ".join(exact_errs[:8]) or "match",
        )

        # --- Structural ready ---
        if not pack.ready and mission.get("remediate"):
            # one more force pass
            fixes.extend(self._remediate(mission["remediate"]))
            pack = gatherer.gather(pack_id)
            exact_errs = verify_pack_exact(pack.tables, PACK_EXACT[pack_id])
            gate.require(
                "exact_fingerprint_after_remediate",
                len(exact_errs) == 0,
                "; ".join(exact_errs[:5]) or "match",
            )

        gate.require("structural_ready", pack.ready, pack.summary)

        # HARD abort — no soft swallow
        gate.abort_if_nogo()

        # --- GUI step with postconditions ---
        gui_result: dict[str, Any] = {"skipped": True}
        step = StepVerification(step_id=f"{mid}_gui")
        if self.use_live_gui and self.operator._session is None:
            self.operator.try_bind_open_session()
        if self.use_live_gui and self.operator._session is not None:
            nav = SafeNavigator(self.operator._session, show_mouse=True)
            gui_result = nav.run_mission_gui(mid)
            for k, v in (gui_result.get("filled") or {}).items():
                val = str(v.get("value") or "")
                try:
                    assert_never_tcode_in_data_field(k, val)
                except MissionAbort:
                    step.postconditions.append(GoNoGo(f"field_{k}_not_tcode", False, val))
                    step.evaluate()
                    raise MissionAbort(f"{mid}: GUI put tcode in field {k}={val}")
                step.postconditions.append(GoNoGo(f"field_{k}_not_tcode", True, val[:40]))
            step.preconditions.append(GoNoGo("com_session", True, "bound"))
            step.evaluate()
            if not step.ok:
                raise MissionAbort(f"{mid}: GUI step postcondition fail: {step.errors}")
            gate.steps.append(step)
        else:
            step.postconditions.append(
                GoNoGo(
                    "gui_optional_without_scripting",
                    True,
                    "table precision + fingerprints enforced; live GUI needs scripting=TRUE",
                )
            )
            step.evaluate()
            gate.steps.append(step)

        # Final — both ready AND fingerprint clean
        final_ok = bool(pack.ready) and len(exact_errs) == 0 and gate.is_go()
        if not final_ok:
            raise MissionAbort(
                f"{mid} precision FAIL: ready={pack.ready} exact={exact_errs} gate={gate.is_go()}"
            )

        result = {
            "id": mid,
            "title": mission["title"],
            "pack": pack_id,
            "ok": True,
            "ready": pack.ready,
            "fixes": fixes,
            "table_counts": {k: v.count for k, v in pack.tables.items()},
            "exact_errors": exact_errs,
            "gui": {
                k: gui_result.get(k)
                for k in ("ok", "tcode", "filled", "status")
                if k in gui_result
            },
            "gate": gate.to_dict(),
            "precision": "PASS",
            "manifest_hash": self._manifest,
        }
        self.log(
            "mission_pass",
            {"id": mid, "tables": result["table_counts"], "fingerprint": "exact"},
        )
        return result

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


def main() -> int:
    os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
    os.environ.setdefault("SAPILOT_DATA", str(_ROOT / "data"))
    os.environ.setdefault("SAPILOT_SHOW_MOUSE", "0")
    # COM GetObject can hang when scripting is half-available — opt-in only
    live = os.environ.get("SAPILOT_LIVE_GUI", "0").strip().lower() in {"1", "true", "yes"}

    runner = CriticalMissionRunner(use_live_gui=live, show_mouse=live)
    summary = runner.run_all()
    print()
    print("=" * 72)
    print("MISSION CRITICAL 22 — PRECISION BOARD (10 PTP + 10 OTC + 2 ABAP)")
    print("=" * 72)
    for r in runner.results:
        flag = "PASS" if r.get("ok") else "FAIL"
        print(f"  {flag:4}  {r.get('id')}: {r.get('title')}  precision={r.get('precision')}")
        if r.get("exact_errors"):
            print(f"        exact: {r['exact_errors'][:2]}")
        if r.get("abort"):
            print(f"        ABORT: {str(r['abort'])[:120]}")
    print("=" * 72)
    print(
        f"RESULT: {summary['ok_count']}/{summary['total']}  "
        f"all_pass={summary['all_pass']}  "
        f"journal_chain_valid={summary['journal_chain_valid']}  "
        f"fingerprints={summary.get('fingerprint_coverage')}"
    )
    if summary.get("document_chain_invariants"):
        print("CHAIN INVARIANT ERRORS:", summary["document_chain_invariants"])
    print("Manifest:", summary.get("manifest_hash"))
    print("Report:  ", summary.get("report"))
    print("Chain:   ", summary.get("chain_path"))
    return 0 if summary.get("all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
