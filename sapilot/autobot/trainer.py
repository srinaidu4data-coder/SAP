"""
Train the SAP bot: where to click, which fields to fill, how to debug.

Industry method (Script Recording / F1 technical info):
  1. Bind live COM session
  2. Dump every control Id + Name + Text + ScreenLeft/Top/Width/Height
  3. Label controls for a mission (command field, Supplier, Enter…)
  4. Save to training store → bot uses learned IDs first

Also supports importing .vbs from SAP Script Recording & Playback.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _training_path() -> Path:
    import os

    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    p = root / "training"
    p.mkdir(parents=True, exist_ok=True)
    return p / "bot_training.json"


@dataclass
class ControlHit:
    id: str
    name: str = ""
    text: str = ""
    type: str = ""
    screen_left: int | None = None
    screen_top: int | None = None
    width: int | None = None
    height: int | None = None
    changeable: bool = False

    def center(self) -> tuple[int, int] | None:
        if self.screen_left is None or self.screen_top is None:
            return None
        w = self.width or 40
        h = self.height or 16
        return int(self.screen_left + w / 2), int(self.screen_top + h / 2)


@dataclass
class ScreenTraining:
    """Training snapshot for one tcode/screen."""

    tcode: str
    title: str = ""
    captured_at: str = ""
    controls: list[ControlHit] = field(default_factory=list)
    # semantic labels → control id
    labels: dict[str, str] = field(default_factory=dict)
    # ordered fill steps: {label, value_key, control_id}
    fill_order: list[dict[str, str]] = field(default_factory=list)
    notes: str = ""


@dataclass
class DebugRecipe:
    symptom_pattern: str
    pack_id: str
    checks: list[str] = field(default_factory=list)
    notes: str = ""


class TrainingStore:
    def __init__(self, path: Path | None = None):
        self.path = path or _training_path()
        self.data: dict[str, Any] = {"version": 1, "screens": {}, "debug": [], "missions": {}}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert_screen(self, screen: ScreenTraining) -> None:
        self.data.setdefault("screens", {})[screen.tcode.upper()] = {
            "tcode": screen.tcode.upper(),
            "title": screen.title,
            "captured_at": screen.captured_at,
            "controls": [asdict(c) for c in screen.controls],
            "labels": screen.labels,
            "fill_order": screen.fill_order,
            "notes": screen.notes,
        }
        self.save()

    def get_screen(self, tcode: str) -> dict[str, Any] | None:
        return (self.data.get("screens") or {}).get(tcode.upper())

    def label(self, tcode: str, label: str, control_id: str) -> None:
        scr = self.get_screen(tcode)
        if not scr:
            raise KeyError(f"No training capture for {tcode}. Run capture first.")
        scr.setdefault("labels", {})[label] = control_id
        self.data["screens"][tcode.upper()] = scr
        self.save()

    def set_fill_order(self, tcode: str, steps: list[dict[str, str]]) -> None:
        scr = self.get_screen(tcode)
        if not scr:
            raise KeyError(f"No training capture for {tcode}")
        scr["fill_order"] = steps
        self.data["screens"][tcode.upper()] = scr
        self.save()

    def add_debug(self, recipe: DebugRecipe) -> None:
        self.data.setdefault("debug", []).append(asdict(recipe))
        self.save()

    def list_screens(self) -> list[str]:
        return sorted((self.data.get("screens") or {}).keys())


class BotTrainer:
    """Capture live SAP screen → train labels → use for navigation."""

    def __init__(self, session: Any | None = None):
        self.session = session
        self.store = TrainingStore()

    def bind_session(self) -> bool:
        try:
            import win32com.client  # type: ignore

            sap = win32com.client.GetObject("SAPGUI")
            app = sap.GetScriptingEngine
            for ci in range(int(app.Children.Count)):
                conn = app.Children(ci)
                for si in range(int(conn.Children.Count)):
                    self.session = conn.Children(si)
                    return True
        except Exception as e:
            log.warning("bind failed: %s", e)
        return False

    def capture_screen(self, tcode_hint: str = "") -> ScreenTraining:
        """Dump full control tree with IDs and screen coordinates for training."""
        if self.session is None and not self.bind_session():
            raise RuntimeError(
                "No scriptable SAP session. Enable sapgui/user_scripting and log in, then train."
            )

        tcode = tcode_hint
        title = ""
        try:
            tcode = tcode or str(self.session.Info.Transaction)
            title = str(self.session.FindById("wnd[0]").Text)
        except Exception:
            pass

        controls: list[ControlHit] = []

        def walk(obj: Any, depth: int = 0) -> None:
            if depth > 14:
                return
            try:
                cid = str(getattr(obj, "Id", "") or "")
                if not cid:
                    return
                hit = ControlHit(
                    id=cid,
                    name=str(getattr(obj, "Name", "") or ""),
                    text=str(getattr(obj, "Text", "") or "")[:80],
                    type=str(getattr(obj, "Type", "") or getattr(obj, "TypeAsNumber", "") or ""),
                    changeable=bool(getattr(obj, "Changeable", False)),
                )
                try:
                    hit.screen_left = int(obj.ScreenLeft)
                    hit.screen_top = int(obj.ScreenTop)
                    hit.width = int(obj.Width)
                    hit.height = int(obj.Height)
                except Exception:
                    pass
                controls.append(hit)
            except Exception:
                return
            try:
                n = int(obj.Children.Count)
                for i in range(n):
                    walk(obj.Children(i), depth + 1)
            except Exception:
                pass

        walk(self.session.FindById("wnd[0]"))

        # Auto-suggest labels from known id fragments
        labels: dict[str, str] = {}
        for c in controls:
            cid_u = c.id.upper()
            name_u = c.name.upper()
            if "OKCD" in cid_u or cid_u.endswith("/OKCD"):
                labels.setdefault("OK_CODE", c.id)
            if "LIFNR" in name_u or "LIFNR" in cid_u:
                labels.setdefault("LIFNR", c.id)
            if "BUKRS" in name_u or "BUKRS" in cid_u:
                labels.setdefault("BUKRS", c.id)
            if "EBELN" in name_u or "EBELN" in cid_u:
                labels.setdefault("EBELN", c.id)
            if "BANFN" in name_u or "BANFN" in cid_u:
                labels.setdefault("BANFN", c.id)
            if "MATNR" in name_u or "MATNR" in cid_u:
                labels.setdefault("MATNR", c.id)
            if "PARTNER" in name_u or "PARTNER_NUMBER" in cid_u:
                labels.setdefault("PARTNER", c.id)
            if "LAUFD" in name_u or "LAUFD" in cid_u:
                labels.setdefault("LAUFD", c.id)
            if "LAUFI" in name_u or "LAUFI" in cid_u:
                labels.setdefault("LAUFI", c.id)
            if "GD-TAB" in cid_u or name_u == "GD-TAB":
                labels.setdefault("TABNAME", c.id)

        screen = ScreenTraining(
            tcode=tcode or "UNKNOWN",
            title=title,
            captured_at=datetime.now(timezone.utc).isoformat(),
            controls=controls,
            labels=labels,
            notes="Auto-captured. Refine labels with train label command.",
        )
        self.store.upsert_screen(screen)
        return screen

    def import_vbs(self, vbs_path: Path, tcode: str) -> int:
        """
        Parse SAP Script Recording .vbs for findById("...") and .text = "..."
        Train fill_order automatically.
        """
        text = vbs_path.read_text(encoding="utf-8", errors="ignore")
        # session.findById("id").text = "value"
        pattern = re.compile(
            r'findById\(\s*"([^"]+)"\s*\)\.(?:text|Text)\s*=\s*"([^"]*)"',
            re.I,
        )
        steps = []
        labels: dict[str, str] = {}
        for m in pattern.finditer(text):
            cid, val = m.group(1), m.group(2)
            # skip okcd navigation lines for fill_order of data
            if "okcd" in cid.lower():
                labels["OK_CODE"] = cid
                continue
            if val.upper().startswith("/N") or val.upper().startswith("/O"):
                labels["OK_CODE"] = cid
                continue
            label = self._guess_label(cid)
            labels[label] = cid
            steps.append({"label": label, "control_id": cid, "example_value": val})

        scr = self.store.get_screen(tcode) or {
            "tcode": tcode.upper(),
            "title": "",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "controls": [],
            "labels": {},
            "fill_order": [],
            "notes": f"Imported from {vbs_path.name}",
        }
        scr["labels"] = {**scr.get("labels", {}), **labels}
        scr["fill_order"] = steps
        scr["notes"] = f"Imported VBS {vbs_path.name}"
        self.store.data.setdefault("screens", {})[tcode.upper()] = scr
        self.store.save()
        return len(steps)

    def _guess_label(self, control_id: str) -> str:
        u = control_id.upper()
        for key in (
            "LIFNR",
            "BUKRS",
            "EBELN",
            "BANFN",
            "MATNR",
            "WERKS",
            "EKORG",
            "LAUFD",
            "LAUFI",
            "BELNR",
            "GJAHR",
            "PARTNER",
            "OKCD",
        ):
            if key in u:
                return "OK_CODE" if key == "OKCD" else key
        return control_id.split("/")[-1][:40]

    def apply_training_to_navigator(self, tcode: str, session: Any, values: dict[str, str]) -> dict[str, Any]:
        """
        Use trained labels to fill a screen after StartTransaction.
        values: {LIFNR: '0000100001', BUKRS: '1000', ...}
        """
        scr = self.store.get_screen(tcode)
        if not scr:
            return {"ok": False, "error": f"No training for {tcode}"}

        from sapilot.autobot.navigator import SafeNavigator

        nav = SafeNavigator(session, show_mouse=True)
        if not nav.go_tcode(tcode):
            return {"ok": False, "error": "navigation failed", "log": nav.log}

        labels = scr.get("labels") or {}
        fill_order = scr.get("fill_order") or []
        results = []

        if fill_order:
            for step in fill_order:
                label = step.get("label", "")
                cid = step.get("control_id") or labels.get(label, "")
                # map label to value
                val = values.get(label) or values.get(label.upper()) or step.get("example_value", "")
                if not cid or val == "":
                    continue
                if str(val).upper().startswith("/N"):
                    results.append({"label": label, "blocked": True, "reason": "tcode in data field"})
                    continue
                ok = nav.set_field([cid], str(val), label=label)
                results.append({"label": label, "id": cid, "value": val, "ok": ok})
        else:
            for label, val in values.items():
                cid = labels.get(label) or labels.get(label.upper())
                if not cid:
                    results.append({"label": label, "ok": False, "reason": "no trained id"})
                    continue
                if str(val).upper().startswith("/N"):
                    results.append({"label": label, "blocked": True})
                    continue
                ok = nav.set_field([cid], str(val), label=label)
                results.append({"label": label, "id": cid, "value": val, "ok": ok})

        try:
            nav.vkey(0)
        except Exception:
            pass
        return {"ok": any(r.get("ok") for r in results), "results": results, "log": nav.log}

    def suggest_debug(self, symptom: str) -> list[dict[str, Any]]:
        """Match trained debug recipes + built-in heuristics."""
        hits = []
        for r in self.store.data.get("debug") or []:
            if re.search(r.get("symptom_pattern", ""), symptom, re.I):
                hits.append(r)
        # built-ins
        builtins = [
            DebugRecipe(
                r"vendor|supplier|/nf110|not been created",
                "ptp_01_vendor_master",
                ["Never put tcode in Supplier", "Use LIFNR from pack", "StartTransaction XK03/BP first"],
                "Supplier field is for vendor number only",
            ),
            DebugRecipe(
                r"payment method|zwels|no valid payment",
                "ptp_10_payment_readiness",
                ["LFB1-ZWELS", "T042E", "T042I", "T042Y", "LFBK"],
                "Payment readiness multi-table",
            ),
            DebugRecipe(
                r"goods receipt|migo|vgabe",
                "ptp_07_goods_receipt",
                ["EKBE VGABE=1", "MSEG", "EKKO"],
                "GR history",
            ),
            DebugRecipe(
                r"purchase order|ekko|me23",
                "ptp_06_purchase_order",
                ["EKKO", "EKPO", "EKBE"],
                "PO extract",
            ),
        ]
        for b in builtins:
            if re.search(b.symptom_pattern, symptom, re.I):
                hits.append(asdict(b))
        return hits

    def export_markdown_report(self) -> Path:
        lines = [
            "# Bot training report",
            "",
            f"Store: `{self.store.path}`",
            "",
            "## Trained screens",
            "",
        ]
        for tcode in self.store.list_screens():
            scr = self.store.get_screen(tcode) or {}
            lines.append(f"### {tcode} — {scr.get('title', '')}")
            lines.append("")
            lines.append(f"Captured: {scr.get('captured_at', '')}")
            lines.append(f"Controls: {len(scr.get('controls') or [])}")
            lines.append("Labels:")
            for k, v in (scr.get("labels") or {}).items():
                lines.append(f"- **{k}** → `{v}`")
            if scr.get("fill_order"):
                lines.append("Fill order:")
                for s in scr["fill_order"]:
                    lines.append(f"- {s}")
            lines.append("")
        path = self.store.path.with_suffix(".md")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
