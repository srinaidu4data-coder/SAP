"""
Preflight — verifies prerequisites and refuses to start with specific remediation.
Tests Basis + client scripting + RFC + policy readiness.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, asdict
from typing import Any, Callable

from sapilot.exceptions import PreflightError


@dataclass
class CheckResult:
    id: str
    ok: bool
    message: str
    remediation: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _check(id_: str, ok: bool, message: str, remediation: str, required: bool = True) -> CheckResult:
    return CheckResult(id=id_, ok=ok, message=message, remediation=remediation, required=required)


def check_python() -> CheckResult:
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 11)
    return _check(
        "python",
        ok,
        f"Python {major}.{minor}",
        "Use Python 3.11+ (embedded runtime or system install)",
    )


def check_platform() -> CheckResult:
    ok = platform.system() == "Windows"
    return _check(
        "platform",
        ok,
        f"OS={platform.system()}",
        "Profile A requires Windows with SAP GUI for Windows installed",
        required=False,  # allow unit tests on other OS for knowledge layer
    )


def check_pywin32() -> CheckResult:
    try:
        import win32com.client  # noqa: F401

        return _check("pywin32", True, "pywin32 available", "")
    except ImportError:
        return _check(
            "pywin32",
            False,
            "pywin32 not installed",
            "pip install pywin32  (required for GUI channel)",
            required=False,
        )


def check_sapgui_scripting_client() -> CheckResult:
    """Best-effort: registry / COM availability. Does not modify settings."""
    if platform.system() != "Windows":
        return _check(
            "sapgui_client_scripting",
            False,
            "Not Windows — SAP GUI Scripting client check skipped",
            "Run on Windows consultant laptop with SAP GUI",
            required=False,
        )
    try:
        import win32com.client  # type: ignore

        try:
            win32com.client.GetObject("SAPGUI")
            return _check(
                "sapgui_client_scripting",
                True,
                "SAPGUI COM object reachable",
                "",
            )
        except Exception:
            return _check(
                "sapgui_client_scripting",
                False,
                "SAP GUI not running or scripting engine unavailable",
                "Start SAP Logon; Options → Accessibility & Scripting → Enable Scripting; "
                "uncheck both 'Notify when...' boxes",
                required=False,
            )
    except ImportError:
        return _check(
            "sapgui_client_scripting",
            False,
            "Cannot test SAP GUI COM without pywin32",
            "pip install pywin32",
            required=False,
        )


def check_pyrfc() -> CheckResult:
    try:
        import pyrfc  # noqa: F401

        return _check("pyrfc", True, "pyrfc importable", "")
    except ImportError:
        return _check(
            "pyrfc",
            False,
            "pyrfc not installed",
            "Install SAP NW RFC SDK, set SAPNWRFC_HOME / PATH, then pip install pyrfc. "
            "Or use --mock for offline diagnostic demos.",
            required=False,
        )


def check_nwrfc_path() -> CheckResult:
    home = os.environ.get("SAPNWRFC_HOME", "")
    root = os.environ.get("SAPILOT_HOME", "")
    side = os.path.join(root, "runtime", "nwrfcsdk") if root else ""
    ok = bool(home) or (side and os.path.isdir(side))
    return _check(
        "nwrfc_sdk",
        ok,
        f"SAPNWRFC_HOME={home or '(unset)'}",
        "Place NW RFC SDK under runtime/nwrfcsdk or set SAPNWRFC_HOME",
        required=False,
    )


def check_policy_file() -> CheckResult:
    from pathlib import Path

    from sapilot.policy.tier import load_policy, verify_policy_signature

    try:
        pol = load_policy()
        sig_ok = verify_policy_signature(pol)
        if not sig_ok:
            return _check(
                "policy",
                False,
                "Policy signature invalid",
                "Sign local_policy.yaml or set SAPILOT_ALLOW_UNSIGNED_POLICY=1 for lab only",
            )
        return _check("policy", True, "Policy file loadable", "")
    except Exception as e:
        return _check(
            "policy",
            False,
            f"Policy load failed: {e}",
            "Ensure sapilot/policy/local_policy.yaml exists",
        )


def check_denylist() -> CheckResult:
    try:
        from sapilot.policy.denylist import load_denylist

        dl = load_denylist()
        ok = "tiers" in dl and "global_deny" in dl
        return _check(
            "denylist",
            ok,
            "denylist.yaml loaded" if ok else "denylist incomplete",
            "Restore sapilot/policy/denylist.yaml",
        )
    except Exception as e:
        return _check("denylist", False, str(e), "Restore denylist.yaml")


def check_server_scripting_hint() -> CheckResult:
    """
    Cannot read RZ11 without a live RFC session. Emit instructional check.
    When SAPILOT_PREFLIGHT_ASSUME_BASIS=1, mark ok for lab pipelines.
    """
    assume = os.environ.get("SAPILOT_PREFLIGHT_ASSUME_BASIS", "0") == "1"
    return _check(
        "server_scripting_params",
        assume,
        "Server profile parameters not probed (need live RFC)"
        if not assume
        else "Assumed OK via SAPILOT_PREFLIGHT_ASSUME_BASIS=1",
        "Basis: RZ11 sapgui/user_scripting=TRUE; "
        "sapgui/user_scripting_disable_recording=FALSE; "
        "sapgui/user_scripting_force_notification=FALSE (sandbox); "
        "persist via RZ10. Auth: S_SCR, S_RFC (SDTX/SUTL), S_TABU_DIS/NAM",
        required=False,
    )


DEFAULT_CHECKS: list[Callable[[], CheckResult]] = [
    check_python,
    check_platform,
    check_policy_file,
    check_denylist,
    check_pywin32,
    check_sapgui_scripting_client,
    check_pyrfc,
    check_nwrfc_path,
    check_server_scripting_hint,
]


def run_preflight(
    *,
    strict: bool = False,
    extra: list[Callable[[], CheckResult]] | None = None,
) -> list[dict[str, Any]]:
    checks = list(DEFAULT_CHECKS)
    if extra:
        checks.extend(extra)
    results = [c().to_dict() for c in checks]
    failed_required = [r for r in results if r["required"] and not r["ok"]]
    if strict and failed_required:
        raise PreflightError(results)
    # Soft mode: only raise if python/policy hard fails
    hard = [r for r in results if r["id"] in {"python", "policy", "denylist"} and not r["ok"]]
    if hard:
        raise PreflightError(results)
    return results
