"""Pick the next glass action from memory. Record what happened."""
from __future__ import annotations

from typing import Any

from sapilot.learn.memory import NavMemory, default_memory
from sapilot.product.navigate import classify


def signature(title: str, status: str = "", blob: str = "", intent: str = "") -> str:
    rec = classify(title, status, blob)
    err = "ok"
    low = f"{status} {blob}".lower()
    if "is not created in language" in low:
        err = "unit_lang"
    elif rec.get("error") == "nav":
        err = "nav"
    elif rec.get("error") == "finding":
        err = "finding"
    elif rec.get("kind") == "create":
        err = "create"
    elif rec.get("kind") == "shell":
        err = "shell"
    return f"{rec.get('kind')}|{err}|{intent or '-'}"


def remember(
    title: str,
    status: str,
    blob: str,
    intent: str,
    action: dict[str, Any],
    reward: int,
    note: str = "",
    mem: NavMemory | None = None,
) -> None:
    (mem or default_memory()).record(
        signature(title, status, blob, intent),
        intent,
        action,
        reward,
        title=title,
        status=status,
        note=note,
    )


def suggest(title: str, status: str, blob: str, intent: str, mem: NavMemory | None = None) -> dict[str, Any] | None:
    mem = mem or default_memory()
    from sapilot.product.sap_status import assess_load

    judged = assess_load(status, blob, "")
    if judged["fatal"] and intent in {"open_list", "count", "focus_database"}:
        return {
            "kind": "stop",
            "why": judged["text"] or judged["kind"],
            "reason": judged["kind"],
        }
    hit = mem.best_action(signature(title, status, blob, intent), intent)
    if hit and hit.get("kind") in {"stop", "back_out"}:
        return hit
    if hit and judged["fatal"]:
        return {"kind": "stop", "why": judged["text"] or judged["kind"]}
    if hit:
        return hit
    return _seed_fallback(intent, title, status, blob)


def _seed_fallback(intent: str, title: str, status: str, blob: str) -> dict[str, Any] | None:
    """Hard priors from public SAP GUI tutorials until the glass overwrites them."""
    rec = classify(title, status, blob)
    if intent == "focus_database":
        return {"kind": "click", "rx": 0.30, "ry": 0.248, "why": "SE16N Data base field (tutorial prior)"}
    if intent == "recover" or rec.get("retry") or rec.get("kind") == "create":
        return {"kind": "back_out", "why": "F12/F3 — never Save (SAP GUI special keys)"}
    if intent == "reset_se16n":
        return {"kind": "goto", "tcode": "SE16N", "why": "/nSE16N from command field (ERP UP /n trick)"}
    if intent == "count":
        return {"kind": "key", "name": "F7", "why": "Number of Entries = F7, not F8 list"}
    if intent == "menu":
        return {"kind": "goto", "tcode": "SESSION_MANAGER", "why": "Easy Access is the safe reset"}
    return None


def apply(hh, action: dict[str, Any]) -> str:
    """Execute one learned/prior action. Never Save."""
    kind = (action or {}).get("kind")
    if kind == "click":
        hh.click_frac(float(action["rx"]), float(action["ry"]))
        return f"click {action.get('rx')},{action.get('ry')}"
    if kind == "key":
        name = str(action.get("name") or "ESCAPE")
        if name.upper() in {"F11", "CTRL+S", "SAVE"}:
            return "refused save"
        hh.key(name, settle=0.45)
        return f"key {name}"
    if kind == "back_out":
        from sapilot.product.navigate import back_out

        back_out(hh, steps=2)
        return "back_out"
    if kind == "goto":
        from sapilot.display.policy import DisplayPolicyError, assert_display_tcode

        code = str(action.get("tcode") or "").upper()
        if code and code != "SESSION_MANAGER":
            try:
                assert_display_tcode(code)
            except DisplayPolicyError:
                return f"refused {code}"
        hh.goto(code)
        return f"goto {code}"
    if kind == "escape":
        hh.key("ESCAPE", settle=0.3)
        return "escape"
    if kind == "stop":
        return f"stop:{action.get('reason') or action.get('why') or 'status'}"
    return "noop"
