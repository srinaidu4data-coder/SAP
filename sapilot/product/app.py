"""
SAPILOT product console — http://127.0.0.1:8800

Live SAP GUI operator. Any module, any t-code. Display wing never creates.
"""
from __future__ import annotations

import base64
import os
import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask, jsonify, request, send_file, send_from_directory

from sapilot.env_load import load_dotenv

load_dotenv(_ROOT / ".env")
try:
    from sapilot.learn.ingest import seed as _seed_learn
    from sapilot.learn.mind import seed_priors as _seed_mind

    _seed_learn()
    _seed_mind()
except Exception:
    pass
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_DATA", str(_ROOT / "data"))
os.environ.setdefault("SAPILOT_LAB", "1")
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
_SHOT = Path(os.environ["SAPILOT_DATA"]) / "runs" / "product"
_SHOT.mkdir(parents=True, exist_ok=True)

INSIGHTS = [
    {
        "id": "funnel",
        "title": "Cash leaks in three places at once",
        "body": "12,255 orders → 7,959 deliveries → 5,982 invoices → 3,014 still unpaid. Most invoices never produced a customer letter (928 outputs). Fix only collections and you call people about bills they never saw. Sequence: unbilled, then send the bill, then credit.",
    },
    {
        "id": "two-economies",
        "title": "Wrong material = a different P&L",
        "body": "Stock (MZ-RM) builds inventory and a real cost. Drop-ship (TG10) often never hits the warehouse. Mixing them makes every margin report a blend of two economies. Name the paths. Do not let one material play both roles.",
    },
    {
        "id": "costing",
        "title": "Costing is the honesty of every sales invoice",
        "body": "74 costing recipes, one almost-unused overhead sheet, 3,472 estimates, years of actual costing. Products look cheaper than they are. That fake margin funds discounts and uncollected cash.",
    },
    {
        "id": "credit",
        "title": "Credit, output, and collections are one process",
        "body": "Credit master is empty. Collection works when someone does it (5,174 cleared). Reminders almost never go out. Do not buy a collections suite until statements exist.",
    },
    {
        "id": "menu",
        "title": "Unused configuration is a ticket machine",
        "body": "376 sales types, 139 purchasing types, 74 costing recipes. Daily work uses a handful. Hide the rest. Certify about fifteen. Same rule, every module.",
    },
]


def _hh():
    from sapilot.autobot.operator import HumanEyesHands

    return HumanEyesHands(shot_dir=str(_SHOT))


def _sap_windows() -> dict:
    """Distinguish Logon Pad vs a logged-in session. Never match File Explorer."""
    out = {"title": "", "kind": "none", "ok": False}
    try:
        import win32gui
        from sapilot.autobot.vision_operator import find_sap_session

        try:
            h = find_sap_session()
            title = (win32gui.GetWindowText(h) or "").strip()
            if title:
                return {"title": title, "kind": "session", "ok": True}
        except Exception:
            pass

        found = []

        def cb(h, _):
            if not win32gui.IsWindowVisible(h):
                return
            t = (win32gui.GetWindowText(h) or "").strip()
            low = t.lower()
            if not t or "explorer" in low or "sapilot" in low:
                return
            if "sap logon" in low:
                found.append(("logon", t))
            elif low.startswith("sap") or "easy access" in low:
                found.append(("session", t))

        win32gui.EnumWindows(cb, None)
        sessions = [x for x in found if x[0] == "session"]
        if sessions:
            kind, title = sessions[0]
            return {"title": title, "kind": kind, "ok": True}
        if found:
            kind, title = found[0]
            return {"title": title, "kind": kind, "ok": kind == "session"}
    except Exception:
        pass
    return out


def _shot_payload(view, extra: dict | None = None) -> dict:
    rec = {
        "ok": True,
        "title": "",
        "status": "",
        "words": 0,
        "shot": None,
        "path": None,
    }
    try:
        rec["title"] = _sap_windows().get("title") or ""
        if view is not None:
            rec["path"] = str(view.path)
            rec["words"] = len(view.words or [])
            if view.status:
                rec["status"] = view.status.text or ""
            p = Path(view.path)
            if p.exists():
                rec["shot"] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
    except Exception as e:
        rec["ok"] = False
        rec["error"] = str(e)
    if extra:
        rec.update(extra)
    return rec


@app.get("/")
def index():
    resp = send_from_directory(Path(__file__).parent / "static", "index.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.after_request
def _no_cache(resp):
    if "text/html" in (resp.content_type or ""):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/live")
def live():
    w = _sap_windows()
    hint = {
        "session": "Logged in. Click Look at SAP.",
        "logon": "SAP Logon is open. Double-click a system, log in, then click Look at SAP.",
        "none": "Open SAP Logon and log in. Leave the SAP window visible.",
    }.get(w["kind"], "")
    return jsonify(
        {
            "ok": w["ok"],
            "kind": w["kind"],
            "title": w["title"] or "No SAP window found",
            "hint": hint,
            "product": "General SAP GUI operator — any module, any t-code.",
        }
    )


@app.get("/api/insights")
def insights():
    return jsonify({"insights": INSIGHTS})


@app.get("/api/catalog")
def catalog():
    from sapilot.display.catalog import CYCLES

    return jsonify(
        {
            "note": "Examples only. The product is any process.",
            "examples": [
                {
                    "name": c.name,
                    "title": c.title,
                    "spine": c.spine,
                    "steps": len(c.steps),
                }
                for c in CYCLES.values()
            ],
        }
    )


@app.post("/api/analyze")
def analyze():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("process") or data.get("name") or data.get("message") or "").strip()
    from sapilot.product.fast_analyze import run_fast
    from sapilot.product.research import public_job

    rec = run_fast(name)
    if not rec.get("ok"):
        return jsonify(rec), 400
    return jsonify(public_job(rec))


@app.post("/api/fast")
def fast():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or data.get("process") or "").strip()
    from sapilot.product.fast_analyze import run_fast
    from sapilot.product.research import public_job

    rec = run_fast(message)
    if not rec.get("ok"):
        return jsonify(rec), 400
    return jsonify(public_job(rec))


@app.post("/api/chat")
def chat():
    """Natural-language ask. Starts live glass research when SAP is up."""
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or data.get("question") or data.get("text") or "").strip()
    live = data.get("live", True)
    if live:
        from sapilot.product.research import start_research

        rec = start_research(message, _sap_windows)
        if not rec.get("ok"):
            return jsonify(rec), 400
        return jsonify(rec)
    from sapilot.product.chat import answer

    rec = answer(message)
    if not rec.get("ok"):
        return jsonify(rec), 400
    return jsonify(rec)


@app.get("/api/learn")
def learn_status():
    from sapilot.learn.loop import status

    return jsonify({"ok": True, **status()})


@app.get("/api/mind")
def mind_status():
    from sapilot.learn.mind import snapshot

    return jsonify({"ok": True, **snapshot()})


@app.post("/api/learn/ingest")
def learn_ingest():
    from sapilot.learn.ingest import ingest_web

    return jsonify(ingest_web())


@app.post("/api/learn/practice")
def learn_practice():
    data = request.get_json(force=True, silent=True) or {}
    laps = int(data.get("laps") or 1)
    from sapilot.learn.loop import practice

    rec = practice(_sap_windows, laps=laps)
    if not rec.get("ok"):
        return jsonify(rec), 400
    return jsonify(rec)


@app.post("/api/research/start")
def research_start():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or data.get("question") or "").strip()
    from sapilot.product.research import start_research

    rec = start_research(message, _sap_windows, max_tables=data.get("max_tables"))
    if not rec.get("ok"):
        return jsonify(rec), 400
    return jsonify(rec)


@app.get("/api/research/active")
def research_active():
    from sapilot.product.research import active_job, latest_job, public_job

    j = active_job() or latest_job()
    if not j:
        return jsonify({"ok": True, "id": None})
    return jsonify(public_job(j))


@app.get("/api/research/latest")
def research_latest():
    from sapilot.product.research import latest_job, public_job

    j = latest_job()
    if not j:
        return jsonify({"ok": False, "error": "No research sitting yet."}), 404
    return jsonify(public_job(j))


@app.get("/research/<job_id>")
def research_document(job_id: str):
    """Standalone consultant report. This is the document link shown in the UI."""
    from sapilot.product.report import render_html, write_report
    from sapilot.product.research import get_job

    j = get_job(job_id)
    if not j:
        return jsonify({"ok": False, "error": "No such research sitting."}), 404
    html = render_html(j)
    try:
        write_report(j)
    except Exception:
        pass
    resp = app.response_class(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/research/<job_id>")
def research_status(job_id: str):
    from sapilot.product.research import get_job, public_job

    j = get_job(job_id)
    if not j:
        return jsonify({"ok": False, "error": "No such research sitting."}), 404
    return jsonify(public_job(j))


@app.post("/api/research/<job_id>/stop")
def research_stop(job_id: str):
    from sapilot.product.research import public_job, stop_job

    j = stop_job(job_id)
    if not j:
        return jsonify({"ok": False, "error": "No such research sitting."}), 404
    return jsonify(public_job(j))


@app.get("/api/research/<job_id>/shot")
def research_shot(job_id: str):
    from sapilot.product.research import get_job

    j = get_job(job_id)
    if not j:
        return jsonify({"ok": False, "error": "No such sitting."}), 404
    name = j.get("shot_name")
    if not name:
        return jsonify({"ok": False, "error": "No screenshot yet."}), 404
    path = Path(j["dir"]) / name
    if not path.exists():
        return jsonify({"ok": False, "error": "Shot file missing."}), 404
    resp = send_file(path, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _safe_evidence(name: str, job_dir: str | None = None) -> Path | None:
    """Job-local PNG or a proven LIVE_COUNTS shot under data/runs. No path escape."""
    raw = (name or "").replace("\\", "/").lstrip("/")
    if not raw.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    candidates: list[Path] = []
    if job_dir:
        candidates.append(Path(job_dir) / Path(raw).name)
    data_root = Path(os.environ.get("SAPILOT_DATA", str(_ROOT / "data"))).resolve()
    if "data/runs/" in raw:
        rel = raw[raw.index("data/runs/") :]
        candidates.append((_ROOT / rel).resolve())
        candidates.append((data_root.parent / rel).resolve())
        candidates.append((data_root / rel[len("data/") :]).resolve())
    else:
        candidates.append((data_root / "runs" / Path(raw).name).resolve())
    runs = (data_root / "runs").resolve()
    for p in candidates:
        try:
            p = p.resolve()
        except Exception:
            continue
        if not p.is_file():
            continue
        if job_dir and Path(job_dir).resolve() in p.parents:
            return p
        if runs == p.parent or runs in p.parents:
            return p
    return None


@app.get("/api/research/<job_id>/file/<path:name>")
def research_file(job_id: str, name: str):
    from sapilot.product.research import get_job

    j = get_job(job_id)
    job_dir = j.get("dir") if j else None
    path = _safe_evidence(name, job_dir)
    if not path:
        return jsonify({"ok": False, "error": "File not found."}), 404
    suf = path.suffix.lower()
    mime = "image/png"
    if suf == ".xlsx":
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif suf == ".html":
        mime = "text/html"
    elif suf == ".json":
        mime = "application/json"
    return send_file(path, mimetype=mime, as_attachment=suf == ".xlsx", download_name=path.name)


@app.post("/api/see")
def see():
    w = _sap_windows()
    if not w.get("ok"):
        return jsonify(
            {
                "ok": False,
                "error": w.get("title") or "No logged-in SAP session",
                "hint": "Log into SAP (Easy Access or any transaction), leave that window visible, then Look again.",
            }
        )
    try:
        hh = _hh()
        view = hh.see("live")
        return jsonify(_shot_payload(view, {"action": "see"}))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-800:]}), 200


@app.post("/api/goto")
def goto():
    data = request.get_json(force=True, silent=True) or {}
    tcode = (data.get("tcode") or "").strip()
    display_only = bool(data.get("display_only", True))
    if not tcode:
        return jsonify({"ok": False, "error": "Type any t-code."}), 400
    try:
        if display_only:
            from sapilot.display.policy import DisplayPolicyError, assert_display_tcode

            try:
                tcode = assert_display_tcode(tcode)
            except DisplayPolicyError as e:
                return jsonify({"ok": False, "refused": True, "error": str(e)}), 400
        w = _sap_windows()
        if not w.get("ok"):
            return jsonify(
                {
                    "ok": False,
                    "error": "No logged-in SAP session. Log in, then Go.",
                    "tcode": tcode,
                }
            )
        hh = _hh()
        r = hh.goto(tcode)
        view = hh.see("after_goto")
        return jsonify(
            _shot_payload(
                view,
                {"action": "goto", "tcode": tcode, "nav_ok": r.ok, "nav": r.detail},
            )
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-800:]}), 200


@app.post("/api/key")
def key():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "ENTER").strip()
    try:
        hh = _hh()
        hh.key(name, settle=0.8)
        view = hh.see("after_key")
        return jsonify(_shot_payload(view, {"action": "key", "name": name}))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def main() -> int:
    import logging

    port = int(os.environ.get("SAPILOT_PRODUCT_PORT", "8800"))
    debug = os.environ.get("SAPILOT_PRODUCT_DEBUG", "").strip() in {"1", "true", "yes", "on"}
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("sapilot").setLevel(logging.DEBUG if debug else logging.INFO)
    print(f"SAPILOT product  http://127.0.0.1:{port}  debug={'on' if debug else 'off'}")
    print("Attach to the open SAP GUI. Display-only is on by default.")
    # Reloader off: one process owns the live SAP operator thread.
    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False, threaded=True)
    return 0
