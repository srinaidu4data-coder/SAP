"""
Vision-only human operator for the whole SAP GUI. No SAP GUI Scripting.

Works on any transaction. ME21N / SE16N in callers are examples, not scope.

Loop: look → decide → move (servo) → verify (OCR / pixel change) → type.
A document is CREATED only if the named table returns a row.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sapilot.autobot.eyes import (
    ScreenView,
    click_point_for_label,
    find_label,
    look,
    ocr_available,
    parse_status_bar,
    proof_from_view,
    region_changed,
    words_contain,
)
from sapilot.autobot.hands import Jacobian, abs_from_frac, click_xy
from sapilot.autobot.vision_operator import Op

log = logging.getLogger(__name__)


@dataclass
class ActResult:
    ok: bool
    action: str
    detail: str = ""
    view: ScreenView | None = None
    claimed: bool = False  # True ONLY after table proof


class HumanEyesHands:
    """Acts like a person at the keyboard. Independent of Basis scripting."""

    def __init__(self, shot_dir: str | None = None, hwnd: int | None = None):
        root = Path(os.environ.get("SAPILOT_DATA", "data")) / "runs" / "operator"
        self.shot_dir = shot_dir or str(root)
        Path(self.shot_dir).mkdir(parents=True, exist_ok=True)
        self.hwnd = hwnd
        self.jac = Jacobian()
        self.log: list[dict[str, Any]] = []
        self._seq = 0

    def _op(self) -> Op:
        return Op.for_session(self.shot_dir, hwnd=self.hwnd)

    def _note(self, action: str, **kw: Any) -> None:
        rec = {"action": action, **kw, "ts": time.time()}
        self.log.append(rec)
        log.info("OPERATOR %s %s", action, {k: v for k, v in kw.items() if k != "secret"})

    def see(self, name: str | None = None) -> ScreenView:
        op = self._op()
        self.hwnd = op.hwnd
        self._seq += 1
        view = look(op.hwnd, self.shot_dir, name or f"see_{self._seq:03d}")
        self._note("see", path=view.path, words=len(view.words), status=(view.status.text if view.status else ""))
        return view

    def _title(self) -> str:
        try:
            import win32gui  # type: ignore

            return win32gui.GetWindowText(self._op().hwnd) or ""
        except Exception:
            return ""

    @staticmethod
    def _title_kind(title: str) -> str:
        t = (title or "").strip().lower()
        if "easy access" in t:
            return "menu"
        if t in {"sap", ""}:
            return "shell"
        return "tx"

    def _focus_okcd(self) -> None:
        from sapilot.connect.hwnd_input import bind_session, find_okcd_hwnd

        try:
            import win32api  # type: ignore
            import win32con  # type: ignore
            import win32gui  # type: ignore

            sess = bind_session(hwnd=self._op().hwnd)
            okcd = find_okcd_hwnd(sess.hwnd)
            sess.focus(0.1)
            l, t, r, b = win32gui.GetWindowRect(okcd)
            win32api.SetCursorPos(((l + r) // 2, (t + b) // 2))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.03)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.08)
        except Exception:
            pass

    def _leave_blank_shell(self) -> bool:
        """Blank SAP shell after /n from Easy Access. Click Start SAP Easy Access."""
        view = self.see("shell")
        hit = find_label(view.words, ["Start SAP Easy Access", "Easy Access"])
        if hit is None:
            return False
        rx, ry = click_point_for_label(hit, side="on")
        self.click_frac(rx, ry)
        time.sleep(0.2)
        self.key("ENTER", settle=1.6)
        return self._title_kind(self._title()) == "menu"

    def goto(self, tcode: str, *, _retry: bool = True) -> ActResult:
        """Click the command box, type the t-code, Enter. Confirm we left the last screen."""
        from sapilot.connect.hwnd_input import bind_session, send_text_unicode
        from sapilot.policy.guard import authorize_write

        code = (tcode or "").strip().lstrip("/").upper()
        if code.startswith("N") and len(code) > 1 and not code[1:].isdigit():
            code = code[1:]
        authorize_write("start_transaction", tcode=code, target=code, logical="navigate")
        op = self._op()
        sess = bind_session(hwnd=op.hwnd)
        kind0 = self._title_kind(self._title())
        if kind0 == "shell" and not self._leave_blank_shell():
            return ActResult(False, "goto", "blank SAP shell — Start Easy Access failed")
        kind0 = self._title_kind(self._title())
        # /n from Easy Access opens the empty shell. Type the t-code bare on the menu.
        typed = code if kind0 == "menu" else f"/n{code}"
        self._focus_okcd()
        sess.clear_field()
        send_text_unicode(typed)
        time.sleep(0.08)
        sess.send_key("ENTER")
        time.sleep(1.6)
        title = self._title()
        kind = self._title_kind(title)
        if kind == "shell":
            if _retry and self._leave_blank_shell():
                return self.goto(code, _retry=False)
            return ActResult(False, "goto", "landed on blank SAP shell")
        if kind == "menu":
            sess.send_key("ENTER")
            time.sleep(1.5)
            title = self._title()
            kind = self._title_kind(title)
        view = self.see(f"goto_{code}")
        title = self._title() or title
        landed = self._title_kind(title) == "tx"
        self._note("goto", tcode=code, typed=typed, title=title, landed=landed)
        return ActResult(landed, "goto", title or code, view)

    def click_frac(self, rx: float, ry: float, *, double: bool = False) -> ActResult:
        op = self._op()
        x, y = abs_from_frac(op.rect(), rx, ry)
        res = click_xy(x, y, jac=self.jac, double=double)
        self._note("click", rx=rx, ry=ry, ok=res.ok, loops=res.loops)
        return ActResult(res.ok, "click", res.reason)

    def click_label(self, aliases: list[str], *, side: str = "right") -> ActResult:
        view = self.see("before_label")
        hit = find_label(view.words, aliases)
        if hit is None:
            self._note("label_miss", aliases=aliases)
            return ActResult(False, "click_label", f"not seen: {aliases}")
        rx, ry = click_point_for_label(hit, side=side)
        before = view.path
        acted = self.click_frac(rx, ry)
        time.sleep(0.15)
        after = self.see("after_label")
        delta = region_changed(before, after.path)
        ok = acted.ok and delta >= 0.002
        self._note("click_label", label=hit.text, rx=rx, ry=ry, delta=round(delta, 4), ok=ok)
        return ActResult(ok, "click_label", hit.text, after)

    def type_value(
        self,
        value: str,
        *,
        clear: bool = True,
        enter: bool = False,
        steal_focus: bool = False,
    ) -> ActResult:
        """Type into the already-focused field. Do not steal caret to the frame."""
        from sapilot.connect.hwnd_input import bind_window
        from sapilot.policy.guard import authorize_write

        authorize_write("type_text", target="focused", value=value[:40], logical="field")
        op = self._op()
        w = bind_window(op.hwnd)
        w.type_text(value, clear=clear, steal_focus=steal_focus)
        if enter:
            if steal_focus:
                w.send_key("ENTER")
            else:
                from sapilot.connect.hwnd_input import send_key_name

                send_key_name("ENTER")
            time.sleep(0.8)
        else:
            time.sleep(0.15)
        self._note("type", value=value[:40], steal_focus=steal_focus)
        return ActResult(True, "type", value[:40])

    def fill_se16n_table(self, table: str) -> ActResult:
        """Put a table name in SE16N Data base. Never type into the selection ALV."""
        from sapilot.connect.hwnd_input import bind_session, send_key_name, send_text_unicode
        from sapilot.policy.guard import authorize_write
        from sapilot.product.se16n_field import locate_database

        name = (table or "").strip().upper()
        authorize_write("type_text", target="SE16N Data base", value=name[:40], logical="field")
        # Fresh /nSE16N puts the caret in Data base. That is how you enter the table.
        self.goto("SE16N")
        time.sleep(0.45)
        sess = bind_session(hwnd=self._op().hwnd)
        # After /nSE16N, Belize often leaves the caret in the command field.
        # Click the Data base box, clear leftover name, then type.
        self.click_frac(0.28, 0.248)
        time.sleep(0.1)
        for _ in range(16):
            send_key_name("BACK")
        send_text_unicode(name)
        send_key_name("ENTER")
        time.sleep(0.9)
        view = self.see(f"{name.lower()}_typed")
        blob = " ".join(w.text for w in (view.words or []))
        status = (view.status.text if view.status else "") or ""
        from sapilot.product.sap_status import assess_load

        judged = assess_load(status, blob, name)
        if judged["fatal"]:
            self._note(
                "fill_se16n",
                table=name,
                via="autofocus",
                error=judged["kind"],
                status=(judged["text"] or "")[:120],
            )
            return ActResult(False, "fill_se16n", judged["text"] or judged["kind"], view)
        if name.replace(" ", "") in blob.upper().replace(" ", "") and judged["loaded"]:
            self._note("fill_se16n", table=name, via="autofocus")
            return ActResult(True, "fill_se16n", name)

        rx, ry, how = locate_database(view.words)
        self.click_frac(rx, ry)
        time.sleep(0.12)
        sess.type_text(name, clear=True, steal_focus=False)
        send_key_name("ENTER")
        time.sleep(0.5)
        # → immediately to the right of Data base loads the table.
        self.click_frac(min(0.46, rx + 0.12), ry)
        time.sleep(0.8)
        view = self.see(f"{name.lower()}_retyped")
        blob = " ".join(w.text for w in (view.words or []))
        status = (view.status.text if view.status else "") or ""
        judged = assess_load(status, blob, name)
        if judged["fatal"]:
            self._note("fill_se16n", table=name, via=how, error=judged["kind"], status=(judged["text"] or "")[:120])
            return ActResult(False, "fill_se16n", judged["text"] or judged["kind"], view)
        self._note("fill_se16n", table=name, via=how, rx=rx, ry=ry)
        return ActResult(True, "fill_se16n", name)

    def fill_label(
        self,
        aliases: list[str],
        value: str,
        *,
        side: str = "right",
        enter: bool = False,
        verify: bool = True,
    ) -> ActResult:
        clicked = self.click_label(aliases, side=side)
        if not clicked.ok:
            return clicked
        self.type_value(value, enter=enter)
        view = self.see("after_fill")
        if verify and view.words:
            ok = words_contain(view.words, value)
            self._note("verify_typed", value=value[:40], ok=ok)
            if not ok:
                return ActResult(False, "fill_label", f"typed {value!r} but screen does not show it", view)
        return ActResult(True, "fill_label", value, view)

    def key(self, name: str, settle: float = 0.35) -> ActResult:
        self._op().key(name, settle=settle)
        self._note("key", name=name)
        return ActResult(True, "key", name)

    def save_doc(self) -> ActResult:
        """F11/Ctrl+S then read the status strip. Does NOT claim a document."""
        from sapilot.policy.guard import authorize_write

        authorize_write("save", target="document", logical="save")
        self._op().save()
        time.sleep(1.4)
        view = self.see("after_save")
        st = view.status or parse_status_bar("")
        self._note("save", kind=st.kind, text=st.text[:80], hint_doc=st.docno)
        if st.kind == "E":
            return ActResult(False, "save", st.text, view)
        return ActResult(True, "save", st.text or "saved (unproven)", view)

    def click_dialog(self, title: str, button: str) -> ActResult:
        """Click a button on a SAP #32770 dialog (Messages, Exit Document, F4)."""
        from sapilot.autobot.vision_operator import Op, find_popup

        h = find_popup(title, exclude=self._op().hwnd)
        if h is None:
            return ActResult(False, "dialog", f"no SAP dialog matching {title!r}")
        pop = Op(hwnd=h, shot_dir=self.shot_dir)
        view = look(h, self.shot_dir, "dialog")
        hit = find_label(view.words, [button])
        if hit is None:
            return ActResult(False, "dialog", f"{title}: button {button!r} not seen", view)
        rx, ry = click_point_for_label(hit, side="on")
        x, y = abs_from_frac(pop.rect(), rx, ry)
        res = click_xy(x, y, jac=self.jac)
        time.sleep(0.4)
        self._note("dialog", title=title, button=button, ok=res.ok)
        return ActResult(res.ok, "dialog", f"{title} / {button}", view)

    def prove_in_table(
        self,
        table: str,
        field_label: str,
        value: str,
        *,
        created_by: str | None = None,
    ) -> ActResult:
        """
        SE16N the way a consultant proves a posting: table, key, List Output.
        CREATED is true only if the result is filtered (not a 500-row dump)
        and the key is on that result.
        """
        from sapilot.autobot.vision_operator import open_table_browse

        op = self._op()
        open_table_browse(op, table, shot_name="prove_open")
        time.sleep(0.4)
        filled = self.fill_label(
            [field_label, field_label.replace(".", "")],
            value,
            verify=False,
        )
        if not filled.ok:
            self.click_frac(0.22, 0.30)
            self.type_value(value)
        if created_by:
            self.fill_label(["Created By", "ERNAM"], created_by, verify=False)
        list_btn = find_label(self.see("prove_before_list").words, ["List Output", "List"])
        if list_btn is not None:
            rx, ry = click_point_for_label(list_btn, side="on")
            self.click_frac(rx, ry)
        else:
            self.click_frac(0.04, 0.965)
        time.sleep(2.0)
        view = self.see("prove_result")
        ok, detail = proof_from_view(view, value)
        self._note("prove", table=table, value=value, detail=detail, claimed=ok)
        return ActResult(ok, "prove", detail if ok else f"{table}: {detail}", view, claimed=ok)

    def capabilities(self) -> dict[str, Any]:
        return {
            "scripting": False,
            "ocr": ocr_available(),
            "closed_loop_click": True,
            "prove_in_se16n": True,
            "claim_without_table": False,
        }
