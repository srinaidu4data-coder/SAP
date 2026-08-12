"""
SAPILOT Co-pilot — local web UI (http://127.0.0.1:8765)

Controls real SAP Logon (Vista), scenarios, NL goals, screen dump.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Ensure project root on path when frozen / launched as script
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask, jsonify, render_template, request

from sapilot.env_load import load_dotenv

load_dotenv(_ROOT / ".env")
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_DATA", str(_ROOT / "data"))
os.environ.setdefault("SAPILOT_VAULT_PASSPHRASE", os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local"))

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# In-memory session state for the web UI
_STATE: dict = {
    "last_login": None,
    "last_result": None,
    "journal_path": None,
}


def _vault():
    from sapilot.security.vault import CredentialVault

    return CredentialVault(passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local"))


def _save_creds(system: str, client: str, user: str, password: str) -> None:
    v = _vault()
    existing = v.get("vista") or {}
    existing.update(
        {
            "system": system,
            "description": system,
            "client": client,
            "user": user,
            "passwd": password,
            "lang": "EN",
            "ashost": existing.get("ashost") or "apex.sapvista.com",
            "sysnr": existing.get("sysnr") or "00",
        }
    )
    v.set("vista", existing)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    openai = bool(os.environ.get("OPENAI_API_KEY"))
    return jsonify({"ok": True, "openai": openai, "root": str(_ROOT)})


@app.get("/api/status")
def status():
    try:
        from sapilot.connect.gui import GuiSession

        sessions = GuiSession.list_open_sessions()
        saplogon = True
        try:
            import win32com.client

            win32com.client.GetObject("SAPGUI")
        except Exception as e:
            saplogon = False
            sessions = [{"error": str(e)}]
        return jsonify({"saplogon": saplogon, "sessions": sessions, "state": _STATE})
    except Exception as e:
        return jsonify({"saplogon": False, "error": str(e), "sessions": []}), 200


@app.post("/api/login")
def login():
    """Open SAP Logon system and type client / user / password."""
    data = request.get_json(force=True, silent=True) or {}
    system = (data.get("system") or "Vista").strip()
    client = (data.get("client") or "100").strip()
    user = (data.get("user") or "").strip()
    password = data.get("password") or ""

    if not user:
        # try vault
        try:
            from sapilot.connect.logon import load_gui_logon_params

            p = load_gui_logon_params("vista", _vault())
            user = user or p["user"]
            password = password or p["password"]
            client = client or p["client"]
            system = system or p["system_description"]
        except Exception:
            pass

    if not client:
        return jsonify({"ok": False, "error": "Client is required (e.g. 100) — separate from username"}), 400
    if not user or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400
    if client.strip() == user.strip():
        return jsonify({
            "ok": False,
            "error": f"Client and username are both '{client}'. Client must be the SAP mandt (e.g. 100), username is the user id.",
        }), 400

    try:
        _save_creds(system, client, user, password)
    except Exception as e:
        log_err = f"vault warn: {e}"
    else:
        log_err = None

    try:
        from sapilot.connect.logon import gui_logon
        from sapilot.exceptions import CredentialsEnteredNoScripting

        try:
            gui = gui_logon(system, client, user, password, "EN")
            snap = gui.snapshot()
            _STATE["last_login"] = {
                "system": system,
                "client": client,
                "user": user,
                "method": "com",
                "title": snap.title,
                "tcode": snap.tcode,
            }
            return jsonify(
                {
                    "ok": True,
                    "credentials_entered": True,
                    "scriptable": True,
                    "title": snap.title,
                    "tcode": snap.tcode,
                    "message": f"Logged in via COM scripting. Screen: {snap.title}",
                }
            )
        except CredentialsEnteredNoScripting as e:
            _STATE["last_login"] = {
                "system": system,
                "client": client,
                "user": user,
                "method": e.method,
                "scriptable": False,
            }
            return jsonify(
                {
                    "ok": True,
                    "credentials_entered": True,
                    "scriptable": False,
                    "message": str(e),
                    "hint": "Username/password typed. For full Co-pilot, Basis must enable sapgui/user_scripting=TRUE.",
                }
            )
    except Exception as e:
        return jsonify(
            {
                "ok": False,
                "error": str(e),
                "trace": traceback.format_exc()[-1500:],
                "vault_note": log_err,
            }
        ), 500


@app.post("/api/goto")
def goto():
    data = request.get_json(force=True, silent=True) or {}
    tcode = (data.get("tcode") or "F110").strip().upper()
    try:
        from sapilot.copilot.engine import Copilot

        cp = Copilot(mock=False, attach=True, use_rfc=False)
        try:
            info = cp.goto(tcode)
            _STATE["last_result"] = info
            return jsonify({"ok": True, **info})
        finally:
            cp.disconnect()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1200:]}), 500


@app.post("/api/screen")
def screen():
    try:
        from sapilot.copilot.engine import Copilot

        cp = Copilot(mock=False, attach=True, use_rfc=False)
        try:
            summary = cp.screen()
            # trim for UI
            els = (summary.get("elements") or [])[:60]
            summary["elements"] = els
            _STATE["last_result"] = {"tcode": summary.get("tcode"), "title": summary.get("title")}
            return jsonify({"ok": True, "screen": summary})
        finally:
            cp.disconnect()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1200:]}), 500


@app.post("/api/scenario")
def scenario():
    data = request.get_json(force=True, silent=True) or {}
    scenario_id = data.get("scenario_id") or "f110_parameters"
    mock = bool(data.get("mock"))
    attach = bool(data.get("attach", not mock))
    params = {
        "bukrs": data.get("bukrs") or "1000",
        "method": data.get("method") or "A",
        "lifnr": data.get("lifnr") or "0000100001",
        "laufd": data.get("laufd") or "20260812",
        "laufi": data.get("laufi") or "DEMO01",
        "table": data.get("table") or "T042E",
        "land1": "US",
    }
    try:
        from sapilot.copilot.engine import Copilot

        cp = Copilot(
            mock=mock,
            attach=attach and not mock,
            connection=None if mock or attach else "vista",
            use_rfc=not mock,
            cccategory="D" if mock else None,
        )
        try:
            result = cp.run_scenario(scenario_id, params)
            _STATE["journal_path"] = str(cp.journal.path)
            _STATE["last_result"] = {"ok": result.get("ok"), "steps": result.get("steps_run")}
            return jsonify(
                {
                    "ok": bool(result.get("ok")),
                    "steps_run": result.get("steps_run"),
                    "report": result.get("report"),
                    "journal": result.get("journal") or str(cp.journal.path),
                    "vars_keys": list((result.get("vars") or {}).keys()),
                }
            )
        finally:
            cp.disconnect()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 500


@app.post("/api/goal")
def goal():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("goal") or "").strip()
    mock = bool(data.get("mock"))
    attach = bool(data.get("attach", not mock))
    max_steps = int(data.get("max_steps") or 12)
    if not text:
        return jsonify({"ok": False, "error": "goal text required"}), 400
    try:
        from sapilot.copilot.engine import Copilot

        cp = Copilot(
            mock=mock,
            attach=attach and not mock,
            connection=None if mock or attach else "vista",
            use_rfc=False,
            cccategory="D" if mock else None,
        )
        try:
            outcome = cp.run_goal(text, max_steps=max_steps)
            _STATE["journal_path"] = str(cp.journal.path)
            return jsonify(
                {
                    "ok": True,
                    "outcome": outcome.value,
                    "journal": str(cp.journal.path),
                    "tier": cp.tier_ctx.tier.value if cp.tier_ctx else None,
                }
            )
        finally:
            cp.disconnect()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 500


@app.get("/api/scenarios")
def scenarios():
    from sapilot.copilot.scenarios import list_scenarios

    return jsonify({"scenarios": list_scenarios()})


@app.get("/api/packs")
def packs():
    from sapilot.know.gather import list_packs

    return jsonify({"packs": list_packs()})


@app.post("/api/mouse-demo")
def mouse_demo():
    """Visibly move the mouse across the open SAP window."""
    try:
        os.environ["SAPILOT_SHOW_MOUSE"] = "1"
        from sapilot.connect.mouse import demo_wiggle, mouse_enabled

        demo_wiggle()
        return jsonify({"ok": True, "mouse_enabled": mouse_enabled(), "message": "Cursor moved on SAP window"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



def _data_rfc(mock: bool = True):
    if mock:
        from sapilot.connect.rfc import MockRfcClient
        from sapilot.demo_data_ptp import seed_ptp_tables

        rfc = MockRfcClient()
        seed_ptp_tables(rfc)
        return rfc, "mock"
    try:
        from sapilot.security.vault import CredentialVault
        from sapilot.connect.logon import load_connection
        from sapilot.connect.rfc import RfcClient

        params = load_connection(
            "vista",
            CredentialVault(passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local")),
        )
        rfc = RfcClient(params)
        rfc.connect()
        return rfc, "live"
    except Exception:
        from sapilot.connect.rfc import MockRfcClient
        from sapilot.demo_data_ptp import seed_ptp_tables

        rfc = MockRfcClient()
        seed_ptp_tables(rfc)
        return rfc, "mock-fallback"


@app.post("/api/gather")
def gather():
    """Multi-table data pack + readiness debug for a scenario."""
    data = request.get_json(force=True, silent=True) or {}
    pack_id = data.get("pack_id") or "ptp_full_chain"
    mock = bool(data.get("mock", True))
    params = data.get("params") or {}
    try:
        from sapilot.know.gather import ScenarioDataGatherer
        from sapilot.report.journal import RunJournal

        rfc, mode = _data_rfc(mock)
        pack = ScenarioDataGatherer(rfc).gather(pack_id, params)
        j = RunJournal()
        j.append("gather", pack.to_dict())
        _STATE["journal_path"] = str(j.path)
        return jsonify({"ok": True, "mode": mode, "pack": pack.to_dict(), "journal": str(j.path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1200:]}), 500


@app.post("/api/debug")
def debug_api():
    """Debug a symptom by reading the right multi-table pack."""
    data = request.get_json(force=True, silent=True) or {}
    symptom = (data.get("symptom") or "").strip()
    if not symptom:
        return jsonify({"ok": False, "error": "symptom required"}), 400
    mock = bool(data.get("mock", True))
    params = data.get("params") or {}
    try:
        from sapilot.know.gather import ScenarioDataGatherer
        from sapilot.report.journal import RunJournal

        rfc, mode = _data_rfc(mock)
        pack = ScenarioDataGatherer(rfc).debug_message(symptom, params)
        j = RunJournal()
        j.append("debug", pack.to_dict())
        _STATE["journal_path"] = str(j.path)
        return jsonify({"ok": True, "mode": mode, "pack": pack.to_dict(), "journal": str(j.path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1200:]}), 500


@app.post("/api/prepare-run")
def prepare_run():
    """Gather multi-table data then execute scenario."""
    data = request.get_json(force=True, silent=True) or {}
    scenario_id = data.get("scenario_id") or "ptp_06_purchase_order"
    mock = bool(data.get("mock", True))
    require_ready = bool(data.get("require_ready", False))
    params = data.get("params") or {}
    try:
        from sapilot.connect.driver import GuiDriver
        from sapilot.connect.gui import MockGuiSession
        from sapilot.copilot.engine import _mock_screens
        from sapilot.know.execute_with_data import ScenarioOrchestrator
        from sapilot.report.journal import RunJournal

        rfc, mode = _data_rfc(mock)
        gui = MockGuiSession(screens=_mock_screens(), initial="SESSION_MANAGER")
        orch = ScenarioOrchestrator(rfc, driver=GuiDriver(gui, settle_seconds=0.0), journal=RunJournal())
        result = orch.execute(scenario_id, params, require_ready=require_ready)
        _STATE["journal_path"] = result.get("journal")
        return jsonify({"ok": bool(result.get("ok")), "mode": mode, **{k: v for k, v in result.items() if k != "vars"}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 500



@app.get("/api/journal")
def journal_tail():
    """Only allow reading journal.jsonl under data/runs (no arbitrary file read)."""
    runs_root = (_ROOT / "data" / "runs").resolve()
    path_arg = request.args.get("path") or _STATE.get("journal_path")
    path: Path | None = None
    if path_arg:
        cand = Path(path_arg).resolve()
        try:
            cand.relative_to(runs_root)
        except ValueError:
            return jsonify({"ok": False, "error": "path not allowed"}), 403
        if cand.name != "journal.jsonl" or not cand.is_file():
            return jsonify({"ok": False, "error": "path not allowed"}), 403
        path = cand
    if path is None or not path.exists():
        runs = sorted(runs_root.glob("*/journal.jsonl"), key=lambda p: p.stat().st_mtime)
        if not runs:
            return jsonify({"lines": [], "path": None})
        path = runs[-1]
    lines = path.read_text(encoding="utf-8").splitlines()[-80:]
    return jsonify({"path": str(path), "lines": lines})


def main(host: str = "127.0.0.1", port: int = 8765, debug: bool = False) -> None:
    print(f"SAPILOT Co-pilot UI → http://{host}:{port}")
    print("Keep this window open. Open the URL in your browser.")
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
