"""
Stealth control UI for the autonomous bot.

- Message box to give instructions
- Stealth: hide window / tray mode (UI disappears, bot keeps working)
- Live log of bot actions
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask, jsonify, render_template_string, request

from sapilot.env_load import load_dotenv

load_dotenv(_ROOT / ".env")
os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_DATA", str(_ROOT / "data"))
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")
os.environ.setdefault("SAPILOT_VAULT_PASSPHRASE", "sapilot-local")

app = Flask(__name__)

_STATE = {
    "stealth": False,
    "running": False,
    "last_result": None,
    "log": [],
}
_bot_thread: threading.Thread | None = None


HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>SAP Auto AI Bot</title>
<style>
body{margin:0;font-family:Segoe UI,system-ui;background:#0b1020;color:#e8eefc}
.wrap{max-width:960px;margin:0 auto;padding:1.2rem}
h1{font-size:1.4rem;margin:0 0 .3rem}
.sub{color:#93a4c3;margin-bottom:1rem}
.card{background:#141c2e;border:1px solid #2a3854;border-radius:12px;padding:1rem;margin-bottom:1rem}
textarea,input{width:100%;background:#0a0f1a;border:1px solid #2a3854;color:#e8eefc;border-radius:8px;padding:.6rem;font:inherit}
button{background:#4f46e5;color:#fff;border:0;border-radius:8px;padding:.55rem 1rem;margin:.25rem;cursor:pointer;font-weight:600}
button.s{background:#334155} button.g{background:#059669} button.d{background:#b45309}
pre{background:#0a0f1a;border:1px solid #2a3854;border-radius:8px;padding:.75rem;max-height:360px;overflow:auto;font-size:12px;white-space:pre-wrap}
.row{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center}
.pill{display:inline-block;padding:.2rem .6rem;border-radius:999px;background:#1e293b;font-size:.8rem}
.stealth-banner{display:none;position:fixed;inset:0;background:#000;color:#0f0;font-family:monospace;align-items:center;justify-content:center;font-size:1.2rem;z-index:99}
body.stealth .stealth-banner{display:flex} body.stealth .wrap{opacity:0;pointer-events:none}
</style>
</head>
<body>
<div class="stealth-banner" id="stealthBanner">STEALTH MODE — bot running · press ESC or open http://127.0.0.1:8788 to return</div>
<div class="wrap">
  <h1>SAP Auto AI Bot</h1>
  <div class="sub">Autonomous functional consultant · mouse · tables · creates missing data · 10 scenarios</div>

  <div class="card">
    <div class="row">
      <span class="pill" id="runState">idle</span>
      <span class="pill" id="stealthState">UI visible</span>
    </div>
    <label style="display:block;margin:.7rem 0 .3rem;color:#93a4c3;font-size:.85rem">Message to the bot (what a consultant should do)</label>
    <textarea id="msg" rows="3">Run full PTP like an SAP functional consultant: check master data, PR, PO, GR, IR, open items, fix payment blockers, verify F110 readiness.</textarea>
    <div class="row" style="margin-top:.6rem">
      <button class="g" id="btnGo">GO — run 10 scenarios</button>
      <button class="d" id="btnStealth">Stealth (hide UI)</button>
      <button class="s" id="btnShow">Show UI</button>
      <button class="s" id="btnMouse">Wiggle mouse on SAP</button>
      <button class="s" id="btnStatus">Refresh status</button>
      <button class="s" id="btnTrain">Train: capture screen IDs</button>
      <button class="s" id="btnSeed">Seed field catalog</button>
    </div>
  </div>

  <div class="card">
    <h3 style="margin-top:0">Live log</h3>
    <pre id="log">Ready. Click GO to run 10 autonomous scenarios.</pre>
  </div>
</div>
<script>
const logEl = document.getElementById('log');
const setLog = (x) => { logEl.textContent = typeof x==='string'?x:JSON.stringify(x,null,2); };
const api = async (p,b) => {
  const r = await fetch(p,{method:b?'POST':'GET',headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
  return r.json();
};
document.getElementById('btnGo').onclick = async () => {
  document.getElementById('runState').textContent = 'RUNNING…';
  setLog('Bot started — watch SAP window for mouse movement…');
  const j = await api('/api/bot/run',{message:msg.value, use_live_gui:true});
  setLog(j);
  document.getElementById('runState').textContent = j.ok ? ('DONE '+j.summary) : 'ERROR';
};
document.getElementById('btnStealth').onclick = async () => {
  await api('/api/bot/stealth',{enabled:true});
  document.body.classList.add('stealth');
  document.getElementById('stealthState').textContent = 'STEALTH';
};
document.getElementById('btnShow').onclick = async () => {
  await api('/api/bot/stealth',{enabled:false});
  document.body.classList.remove('stealth');
  document.getElementById('stealthState').textContent = 'UI visible';
};
document.getElementById('btnMouse').onclick = async () => setLog(await api('/api/bot/mouse',{}));
document.getElementById('btnStatus').onclick = async () => setLog(await api('/api/bot/status'));
document.getElementById('btnTrain').onclick = async () => {
  setLog('Capturing live SAP control IDs (scripting required)…');
  setLog(await api('/api/bot/train-capture', {}));
};
document.getElementById('btnSeed').onclick = async () => setLog(await api('/api/bot/train-seed', {}));
document.addEventListener('keydown', (e) => { if(e.key==='Escape') document.getElementById('btnShow').click(); });

// poll log while running
setInterval(async () => {
  const s = await api('/api/bot/status');
  if (s.running) document.getElementById('runState').textContent = 'RUNNING…';
  if (s.log && s.log.length) {
    // keep user log unless they just got a full result
  }
}, 2000);
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(HTML)


@app.get("/api/bot/status")
def status():
    return jsonify(
        {
            "running": _STATE["running"],
            "stealth": _STATE["stealth"],
            "last_result": _STATE["last_result"],
            "log": _STATE["log"][-50:],
        }
    )


@app.post("/api/bot/stealth")
def stealth():
    data = request.get_json(force=True, silent=True) or {}
    _STATE["stealth"] = bool(data.get("enabled"))
    # Best-effort hide console / browser is client-side; also try minimize all chrome of this UI note
    return jsonify({"ok": True, "stealth": _STATE["stealth"]})


@app.post("/api/bot/mouse")
def mouse():
    try:
        from sapilot.connect.mouse import demo_wiggle

        demo_wiggle()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.post("/api/bot/train-capture")
def train_capture():
    try:
        from sapilot.autobot.trainer import BotTrainer

        tr = BotTrainer()
        if not tr.bind_session():
            return jsonify({"ok": False, "error": "No scriptable SAP session. Enable scripting + login."})
        screen = tr.capture_screen()
        return jsonify(
            {
                "ok": True,
                "tcode": screen.tcode,
                "title": screen.title,
                "controls": len(screen.controls),
                "labels": screen.labels,
                "path": str(tr.store.path),
                "hint": "Use: sapilot train label XK03 LIFNR <control_id> to refine",
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-800:]})


@app.post("/api/bot/train-seed")
def train_seed():
    try:
        from sapilot.autobot.nav_catalog import TCODE_SCREENS
        from sapilot.autobot.trainer import TrainingStore, ScreenTraining, ControlHit
        from datetime import datetime, timezone

        store = TrainingStore()
        n = 0
        for tcode, scr in TCODE_SCREENS.items():
            if scr.get("alias_of"):
                continue
            labels = {"OK_CODE": "wnd[0]/tbar[0]/okcd"}
            controls = []
            for label, candidates in (scr.get("fields") or {}).items():
                if candidates:
                    labels[label] = candidates[0]
                    controls.append(ControlHit(id=candidates[0], name=label))
            store.upsert_screen(
                ScreenTraining(
                    tcode=tcode,
                    title=f"Seeded {tcode}",
                    captured_at=datetime.now(timezone.utc).isoformat(),
                    controls=controls,
                    labels=labels,
                    fill_order=[
                        {"label": lab, "control_id": cid}
                        for lab, cid in labels.items()
                        if lab != "OK_CODE"
                    ],
                    notes="Seeded research catalog",
                )
            )
            n += 1
        return jsonify({"ok": True, "seeded": n, "path": str(store.path), "screens": store.list_screens()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.post("/api/bot/run")
def run():

    global _bot_thread
    if _STATE["running"]:
        return jsonify({"ok": False, "error": "already running"})
    data = request.get_json(force=True, silent=True) or {}
    message = data.get("message") or ""
    use_live = bool(data.get("use_live_gui", True))

    def work():
        _STATE["running"] = True
        _STATE["log"] = ["Bot thread started"]
        try:
            from sapilot.autobot.consultant import ConsultantBot

            bot = ConsultantBot(use_live_gui=use_live, show_mouse=True, auto_remediate=True)
            result = bot.run_all_ten(message)
            _STATE["last_result"] = result
            _STATE["log"] = bot.message_log
        except Exception as e:
            _STATE["last_result"] = {"ok": False, "error": str(e), "trace": traceback.format_exc()[-2000:]}
            _STATE["log"].append(str(e))
        finally:
            _STATE["running"] = False

    _bot_thread = threading.Thread(target=work, daemon=True)
    _bot_thread.start()
    # Wait for completion so UI gets full result (10 scenarios)
    _bot_thread.join(timeout=600)
    res = _STATE["last_result"] or {}
    return jsonify({"ok": True, **res} if isinstance(res, dict) else {"ok": True, "result": res})


def main(host: str = "127.0.0.1", port: int = 8788) -> None:
    print("=" * 56)
    print("  SAP AUTO AI BOT")
    print(f"  UI  → http://{host}:{port}")
    print("  GO runs 10 autonomous consultant scenarios")
    print("  Stealth hides UI; bot keeps working")
    print("=" * 56)
    app.run(host=host, port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
