"""
Execute navigation catalog against a live COM session.
Implements the rules every SAP GUI Scripting tutorial teaches.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sapilot.autobot.nav_catalog import (
    MISSION_NAV,
    NAVIGATE,
    VKEY,
    resolve_screen,
)

log = logging.getLogger(__name__)


class SafeNavigator:
    def __init__(self, session: Any, show_mouse: bool = True):
        self.session = session
        self.show_mouse = show_mouse
        self.log: list[dict[str, Any]] = []

    def _note(self, **kw: Any) -> None:
        self.log.append(kw)
        log.info("NAV %s", kw)

    def go_tcode(self, tcode: str) -> bool:
        """Rule #1: StartTransaction or okcd only."""
        tcode = tcode.strip().upper().lstrip("/N").lstrip("/O")
        try:
            self.session.StartTransaction(Transaction=tcode)
            time.sleep(0.5)
            self._note(action="StartTransaction", tcode=tcode, ok=True)
            return True
        except Exception as e:
            self._note(action="StartTransaction", tcode=tcode, ok=False, err=str(e))
        try:
            okcd_id = NAVIGATE["fallback_okcd"]
            okcd = self.session.FindById(okcd_id)
            if self.show_mouse:
                try:
                    from sapilot.connect.mouse import click_sap_component

                    click_sap_component(okcd)
                except Exception:
                    pass
            okcd.Text = f"/n{tcode}"
            self.session.FindById("wnd[0]").SendVKey(0)
            time.sleep(0.5)
            self._note(action="okcd", tcode=tcode, ok=True)
            return True
        except Exception as e:
            self._note(action="okcd", tcode=tcode, ok=False, err=str(e))
            return False

    def set_field(self, candidates: list[str], value: str, label: str = "") -> bool:
        """Set first matching FindById — business values only. Fail closed on tcode pollution."""
        val = str(value).strip()
        # Hard ban: never put navigation strings in data fields (mission-critical)
        try:
            from sapilot.mission.precision import assert_never_tcode_in_data_field, is_tcode_command

            assert_never_tcode_in_data_field(label or (candidates[0] if candidates else ""), val)
            if is_tcode_command(val):
                self._note(action="blocked_tcode_in_field", label=label, value=val)
                return False
        except Exception as e:
            if val.upper().startswith("/N") or val.upper().startswith("/O"):
                self._note(action="blocked_tcode_in_field", label=label, value=val, err=str(e))
                return False
        for fid in candidates:
            try:
                el = self.session.FindById(fid)
                if self.show_mouse:
                    try:
                        from sapilot.connect.mouse import click_sap_component

                        click_sap_component(el)
                    except Exception:
                        pass
                el.Text = val
                try:
                    el.caretPosition = len(val)
                except Exception:
                    pass
                self._note(action="set", field=fid, label=label, value=val[:40], ok=True)
                return True
            except Exception:
                continue
        self._note(action="set", label=label, value=val[:40], ok=False, tried=candidates[:3])
        return False

    def vkey(self, key: int | str) -> None:
        code = VKEY.get(key, key) if isinstance(key, str) else key
        self.session.FindById("wnd[0]").SendVKey(int(code))
        time.sleep(0.35)
        self._note(action="vkey", key=code)

    def run_mission_gui(self, mission_id: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        """
        Full consultant step for one mission:
          StartTransaction → fill business fields from catalog (+ training) → Enter/F8
        """
        params = params or {}
        plan = MISSION_NAV.get(mission_id)
        if not plan:
            return {"ok": False, "error": f"no nav plan for {mission_id}"}

        tcode = plan["tcode"]
        defaults = plan.get("defaults") or {}
        merged = {**defaults, **params}

        if not self.go_tcode(tcode):
            return {"ok": False, "error": f"cannot navigate to {tcode}", "log": self.log}

        screen = resolve_screen(tcode)
        # S/4 may redirect XK03 → BP; still try XK03 field list first, then BP
        field_map = dict(screen.get("fields") or {})
        if screen.get("redirects_to"):
            alt = resolve_screen(screen["redirects_to"])
            for k, v in (alt.get("fields") or {}).items():
                field_map.setdefault(k, v)

        # Prefer TRAINED control IDs when available
        try:
            from sapilot.autobot.trainer import TrainingStore

            trained = TrainingStore().get_screen(tcode) or {}
            for lab, cid in (trained.get("labels") or {}).items():
                if lab == "OK_CODE":
                    continue
                field_map[lab] = [cid] + list(field_map.get(lab) or [])
            # If BP title, also merge BP training
            for alt_t in ("BP", "XK03"):
                t2 = TrainingStore().get_screen(alt_t) or {}
                for lab, cid in (t2.get("labels") or {}).items():
                    if lab == "OK_CODE":
                        continue
                    field_map[lab] = list(field_map.get(lab) or []) + [cid]
        except Exception:
            pass

        fill_plan = plan.get("fill") or {}
        filled = {}
        for screen_key, param_key in fill_plan.items():
            value = merged.get(param_key, defaults.get(param_key, ""))
            candidates = field_map.get(screen_key) or [screen_key]
            if isinstance(candidates, str):
                candidates = [candidates]
            ok = self.set_field(list(candidates), value, label=screen_key)
            filled[screen_key] = {"value": value, "ok": ok}

        vkey = screen.get("after_fill_vkey", 0)
        try:
            self.vkey(vkey)
        except Exception as e:
            self._note(action="vkey_fail", err=str(e))

        # Status bar
        status = ""
        try:
            status = str(self.session.FindById("wnd[0]/sbar").Text)
        except Exception:
            pass

        return {
            "ok": any(v.get("ok") for v in filled.values()) or not fill_plan,
            "tcode": tcode,
            "filled": filled,
            "status": status,
            "log": list(self.log),
        }

