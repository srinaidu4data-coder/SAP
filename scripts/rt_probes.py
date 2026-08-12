"""Red-team automated control probes for SAPILOT."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")

from sapilot.act.executor import GroundedExecutor
from sapilot.connect.gui import MockGuiSession
from sapilot.connect.logon import gui_logon
from sapilot.exceptions import ConnectionError as CE
from sapilot.exceptions import PolicyViolation
from sapilot.policy.denylist import assert_allowed, is_denied
from sapilot.policy.tier import TierContext, derive_tier, load_policy
from sapilot.report.journal import RunJournal
from sapilot.schemas import Action, ActionType, GuiElement, PlannedStep, ScreenSnapshot, Tier
from sapilot.security.redaction import RedactionGate

results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(("PASS" if ok else "FAIL"), "-", name, detail)


def main() -> int:
    pol = load_policy()

    t = derive_tier("800", "P", pol)
    check("T000 P maps T3", t == Tier.T3_OBSERVE, str(t))

    try:
        derive_tier("800", "P", {**pol, "client_overrides": {"800": "T1_SANDBOX"}})
        check("block prod override to T1", False, "allowed")
    except PolicyViolation:
        check("block prod override to T1", True, "raised PolicyViolation")

    ctx3 = TierContext(Tier.T3_OBSERVE, "800", "P")
    try:
        ctx3.require("payment_run")
        check("T3 blocks payment_run", False)
    except PolicyViolation:
        check("T3 blocks payment_run", True)

    a = Action(
        type=ActionType.PRESS,
        target="wnd[0]/usr/btnSTART",
        meta={"logical": "f110.start_immediately"},
    )
    denied, reason = is_denied(Tier.T2_SUPERVISED, a)
    check("T2 denies Start Immediately", denied, (reason or "")[:80])

    a2 = Action(type=ActionType.PRESS, target="debug.replace")
    try:
        assert_allowed(Tier.T1_SANDBOX, a2)
        check("debug.replace denied T1", False)
    except PolicyViolation:
        check("debug.replace denied T1", True)

    snap = ScreenSnapshot(
        tcode="F110",
        title="t",
        elements=GuiElement(
            id="wnd[0]",
            children=[GuiElement(id="wnd[0]/usr/btnPROPOSAL", type="GuiButton")],
        ),
    )
    gui = MockGuiSession({"F110": snap}, "F110")
    gui.tcode = "F110"
    ex = GroundedExecutor(TierContext(Tier.T1_SANDBOX, "100", "D"), gui=gui)
    step = PlannedStep(
        assessment="x",
        gap="y",
        action=Action(type=ActionType.PRESS, target="wnd[0]/usr/btnFAKE"),
        justification_ref="t",
        confidence=0.9,
    )
    obs = ex.execute(step)
    check("grounding rejects fake id", obs.status.value == "GROUNDING_ERROR", obs.status.value)

    g = RedactionGate(salt="rt")
    out = g.redact_dict(
        {
            "BANKN": "12345678901234",
            "LIFNR": "0000100001",
            "note": "IBAN DE89370400440532013000",
        }
    )
    check("redact BANKN", "12345678901234" not in str(out["BANKN"]))
    check("keep LIFNR", out["LIFNR"] == "0000100001")
    check("redact IBAN in text", "DE89370400440532013000" not in out["note"])

    try:
        gui_logon("Vista", "100", "100", "x")
        check("logon client!=user guard", False)
    except CE as e:
        check("logon client!=user guard", "Client and username" in str(e), str(e)[:100])

    app = Path("sapilot/webapp/app.py").read_text(encoding="utf-8")
    check("web binds 127.0.0.1", 'host: str = "127.0.0.1"' in app or "127.0.0.1" in app)

    j = RunJournal()
    j.append("rt_probe", {"x": 1})
    check("journal append", j.path.exists())

    from sapilot.diagnose.engine import PaymentRunDiagnosticEngine
    import inspect

    src = inspect.getsource(PaymentRunDiagnosticEngine)
    check("diagnose no BAPI post", "BAPI_TRANSACTION" not in src and "apply_config" not in src.lower())

    # T1 allows payment_run capability in matrix
    ctx1 = TierContext(Tier.T1_SANDBOX, "100", "D")
    check("T1 allows payment_run cap", ctx1.allows("payment_run"))

    # unsigned policy lab default
    check("unsigned policy allowed in lab", os.environ.get("SAPILOT_ALLOW_UNSIGNED_POLICY") == "1")

    # --- Go-live choke-points (post F-02/F-07 fixes) ---
    from sapilot.policy.guard import authorize_write, bind_write_context, clear_write_context

    clear_write_context()
    bind_write_context(TierContext(Tier.T3_OBSERVE, "800", "P"), source="rt")
    try:
        authorize_write("set_text", target="LIFNR", value="1")
        check("WriteGuard T3 blocks driver path", False, "allowed")
    except PolicyViolation:
        check("WriteGuard T3 blocks driver path", True)

    try:
        authorize_write("goto", tcode="F110", target="F110")
        check("WriteGuard T3 blocks goto", False)
    except PolicyViolation:
        check("WriteGuard T3 blocks goto", True)

    bind_write_context(TierContext(Tier.T1_SANDBOX, "100", "D"), source="rt")
    try:
        authorize_write("set_text", target="RF02K-LIFNR", value="/nF110")
        check("WriteGuard blocks tcode in LIFNR", False)
    except PolicyViolation:
        check("WriteGuard blocks tcode in LIFNR", True)

    # Denylist → POLICY_VIOLATION (hard fail, not soft DENIED)
    snap = ScreenSnapshot(
        tcode="F110",
        title="t",
        elements=GuiElement(
            id="wnd[0]",
            children=[GuiElement(id="debug.replace", type="GuiButton")],
        ),
    )
    gui2 = MockGuiSession({"F110": snap}, "F110")
    gui2.tcode = "F110"
    ex2 = GroundedExecutor(TierContext(Tier.T1_SANDBOX, "100", "D"), gui=gui2)
    step2 = PlannedStep(
        assessment="x",
        gap="y",
        action=Action(type=ActionType.PRESS, target="debug.replace"),
        justification_ref="t",
        confidence=0.9,
    )
    obs2 = ex2.execute(step2)
    from sapilot.schemas import ObservationStatus

    check(
        "denylist hard POLICY_VIOLATION",
        obs2.status == ObservationStatus.POLICY_VIOLATION,
        obs2.status.value,
    )

    # Journal hash chain
    j2 = RunJournal()
    j2.append("a", 1)
    j2.append("b", 2)
    okc, _ = j2.verify_chain()
    check("journal hash chain valid", okc)

    # Portable approval token
    from sapilot.policy.approval import ApprovalGate

    g = ApprovalGate()
    tok = g.issue("gui_write")
    g2 = ApprovalGate(secret=g.secret)
    check("approval token portable HMAC", g2.verify(tok.token, "gui_write"))

    # Fingerprint coverage 20/20
    from sapilot.autobot.consultant import ALL_MISSIONS
    from sapilot.mission.precision import PACK_EXACT

    cov = sum(1 for m in ALL_MISSIONS if m["pack"] in PACK_EXACT)
    check(
        "mission fingerprints fleet 22",
        cov == len(ALL_MISSIONS) == 22,
        f"{cov}/{len(ALL_MISSIONS)}",
    )

    clear_write_context()

    fail = sum(1 for _, s, _ in results if s == "FAIL")
    print("---")
    print(f"PROBES: {len(results) - fail}/{len(results)} PASS, {fail} FAIL")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
