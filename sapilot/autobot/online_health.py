"""
Online readiness probes with hard timeouts (COM can hang forever).

Karpathy-loop gate: we only claim ONLINE when these pass under timeout.
"""

from __future__ import annotations

import concurrent.futures
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def run_with_timeout(fn: Callable[[], T], timeout_s: float = 5.0, default: T | None = None) -> tuple[bool, T | None, str]:
    """Run fn in a thread; return (ok, result, error). Never hangs the main thread."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return True, fut.result(timeout=timeout_s), ""
        except concurrent.futures.TimeoutError:
            return False, default, f"timeout after {timeout_s}s"
        except Exception as e:
            return False, default, f"{type(e).__name__}: {e}"


@dataclass
class OnlineHealth:
    ts: float = field(default_factory=time.time)
    sapgui_com: bool = False
    scripting_engine: bool = False
    open_sessions: int = 0
    session_info: list[dict[str, str]] = field(default_factory=list)
    scripting_note: str = ""
    vault_ok: bool = False
    vault_connections: list[str] = field(default_factory=list)
    env_system: str = ""
    env_user_set: bool = False
    offline_super_ok: bool = False
    offline_mission_ok: bool = False
    online_capable: bool = False
    blockers: list[str] = field(default_factory=list)
    score: float = 0.0  # 0..1 toward online perfection

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_online_health(*, com_timeout_s: float = 4.0) -> OnlineHealth:
    h = OnlineHealth()
    h.env_system = os.environ.get("SAPILOT_SYSTEM") or os.environ.get("SAPILOT_CONNECTION") or "Vista"
    h.env_user_set = bool(os.environ.get("SAPILOT_USER") or os.environ.get("SAPILOT_PASSWORD"))

    # Vault (try env passphrase, then lab default, then DPAPI)
    def _vault() -> list[str]:
        from sapilot.security.vault import CredentialVault, _is_lab

        candidates = [
            os.environ.get("SAPILOT_VAULT_PASSPHRASE"),
            "sapilot-local" if _is_lab() else None,
            None,  # DPAPI
        ]
        last_err: Exception | None = None
        for pw in candidates:
            try:
                v = CredentialVault(passphrase=pw)
                return v.list_names()
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(str(last_err) if last_err else "vault unavailable")

    ok, names, err = run_with_timeout(_vault, 3.0, [])
    if ok and names is not None:
        h.vault_ok = True
        h.vault_connections = list(names)
        if not names:
            h.blockers.append("vault empty — store vista with: sapilot vault set vista ...")
    else:
        h.blockers.append(f"vault: {err or 'empty'}")

    # COM / scripting with timeout
    def _com() -> dict[str, Any]:
        import win32com.client  # type: ignore

        sap = win32com.client.GetObject("SAPGUI")
        app = sap.GetScriptingEngine
        out: dict[str, Any] = {"conns": int(app.Children.Count), "sessions": []}
        for ci in range(int(app.Children.Count)):
            conn = app.Children(ci)
            for si in range(int(conn.Children.Count)):
                ses = conn.Children(si)
                info = {"conn": str(ci), "ses": str(si)}
                try:
                    info["system"] = str(ses.Info.SystemName)
                    info["client"] = str(ses.Info.Client)
                    info["user"] = str(ses.Info.User)
                    info["tcode"] = str(ses.Info.Transaction)
                except Exception as e:
                    info["error"] = str(e)[:80]
                out["sessions"].append(info)
        return out

    ok, com, err = run_with_timeout(_com, com_timeout_s, None)
    if ok and com:
        h.sapgui_com = True
        h.scripting_engine = True
        h.open_sessions = len(com.get("sessions") or [])
        h.session_info = com.get("sessions") or []
        if h.open_sessions == 0:
            h.blockers.append("SAP Logon up but no logged-on session")
            h.scripting_note = "Open Vista and log in (client 100)"
        else:
            h.scripting_note = "scriptable session present"
    else:
        h.sapgui_com = False
        h.scripting_engine = False
        h.scripting_note = err or "SAP GUI Scripting unavailable"
        if "timeout" in (err or ""):
            h.blockers.append(
                "SAP GUI COM hung/timeout — set sapgui/user_scripting=TRUE (RZ11) "
                "and enable scripting in SAP Logon Options"
            )
        else:
            h.blockers.append(f"no SAPGUI COM: {err}")

    # Offline perfection signals (files)
    from pathlib import Path

    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    # Prefer 22-fleet artifacts; fall back to legacy 20
    super_candidates = [
        root / "runs" / "SUPER_BOT_22.json",
        root / "runs" / "SUPER_BOT_20.json",
    ]
    mc_candidates = [
        root / "runs" / "MISSION_CRITICAL_22.json",
        root / "runs" / "MISSION_CRITICAL_20.json",
    ]
    try:
        import json

        for super_p in super_candidates:
            if super_p.exists():
                s = json.loads(super_p.read_text(encoding="utf-8")).get("summary") or {}
                h.offline_super_ok = bool(s.get("all_success"))
                break
        for mc_p in mc_candidates:
            if mc_p.exists():
                s = json.loads(mc_p.read_text(encoding="utf-8")).get("summary") or {}
                h.offline_mission_ok = bool(s.get("all_pass"))
                break
    except Exception:
        pass

    if not h.offline_super_ok:
        h.blockers.append("offline Super Bot not green — run scripts/run_super_bot.py")
    if not h.offline_mission_ok:
        h.blockers.append("offline mission-critical not green")

    # Score toward online perfection
    parts = [
        0.15 if h.offline_super_ok else 0.0,
        0.15 if h.offline_mission_ok else 0.0,
        0.15 if h.vault_ok else 0.0,
        0.25 if h.scripting_engine else 0.0,
        0.30 if h.open_sessions > 0 else 0.0,
    ]
    h.score = round(sum(parts), 3)
    h.online_capable = h.scripting_engine and h.open_sessions > 0 and h.offline_super_ok
    if h.online_capable and "ready for online scenarios" not in h.scripting_note:
        h.scripting_note = "ONLINE CAPABLE — run online scenarios"
    return h
