"""
Mega SAP Co-pilot — localhost control plane (LIVE default).

http://127.0.0.1:8777
"""

from __future__ import annotations

import os
import sys
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
os.environ.setdefault("SAPILOT_VAULT_PASSPHRASE", os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local"))
os.environ.setdefault("SAPILOT_SHOW_MOUSE", "1")

app = Flask(__name__)

# Singleton mega instance for the UI session
_MEGA = None


def mega():
    global _MEGA
    from sapilot.mega.engine import MegaCopilot

    if _MEGA is None:
        _MEGA = MegaCopilot(allow_mock=False, show_mouse=True)
    return _MEGA


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Mega SAP Co-pilot</title>
<style>
:root {
  --bg:#070b12; --card:#121a27; --line:#243247; --text:#e8eef8; --mut:#8b9bb4;
  --a:#6366f1; --g:#22c55e; --y:#f59e0b; --r:#ef4444;
}
*{box-sizing:border-box} body{margin:0;font-family:Segoe UI,system-ui,sans-serif;background:
radial-gradient(900px 500px at 0% 0%,#1e1b4b 0%,transparent 50%),
radial-gradient(800px 400px at 100% 0%,#0c4a6e 0%,transparent 45%),var(--bg);color:var(--text)}
header{padding:1rem 1.5rem;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.brand b{font-size:1.35rem;letter-spacing:.04em}
.brand span{color:var(--mut);margin-left:.6rem;font-size:.9rem}
.pill{padding:.35rem .75rem;border-radius:999px;border:1px solid var(--line);font-size:.8rem}
.pill.on{border-color:#166534;color:#86efac}
main{max-width:1280px;margin:0 auto;padding:1rem 1.5rem 2rem;display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1rem 1.15rem}
.wide{grid-column:1/-1}
h2{margin:0 0 .4rem;font-size:1.05rem}
.hint{color:var(--mut);font-size:.85rem;margin:0 0 .9rem;line-height:1.45}
label{display:block;font-size:.78rem;color:var(--mut);margin-bottom:.65rem}
input,select,textarea{width:100%;margin-top:.28rem;padding:.55rem .65rem;border-radius:8px;border:1px solid var(--line);background:#0a101a;color:var(--text);font:inherit}
.row{display:flex;flex-wrap:wrap;gap:.5rem;margin:.5rem 0 .8rem}
button{border:1px solid var(--line);background:#1c2740;color:var(--text);padding:.55rem .9rem;border-radius:8px;cursor:pointer;font:inherit}
button.p{background:linear-gradient(180deg,#6366f1,#4f46e5);border-color:#4338ca;font-weight:600}
button.g{background:linear-gradient(180deg,#22c55e,#16a34a);border-color:#15803d;font-weight:600}
button:hover{filter:brightness(1.08)}
pre{background:#0a101a;border:1px solid var(--line);border-radius:8px;padding:.75rem;font:12px/1.4 Consolas,monospace;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word;margin:0}
.steps{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:1rem}
.steps i{font-style:normal;padding:.3rem .65rem;border-radius:999px;background:#0a101a;border:1px solid var(--line);font-size:.75rem;color:var(--mut)}
.steps i.a{color:#c7d2fe;border-color:#4338ca}
footer{text-align:center;color:var(--mut);font-size:.78rem;padding-bottom:1.5rem}
@media(max-width:900px){main{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <div class="brand"><b>MEGA SAP COPILOT</b><span>online · extract · inject · execute</span></div>
  <div id="status" class="pill">offline</div>
</header>
<main>
  <section class="card wide">
    <div class="steps">
      <i class="a">1 Login GUI</i><i class="a">2 Extract tables</i><i class="a">3 Debug</i>
      <i class="a">4 Inject data</i><i class="a">5 Execute scenario</i><i class="a">6 Journal</i>
    </div>
    <p class="hint">Live SAP only by default. Mouse movement ON. Data comes from real tables (RFC or SE16N), then is typed back into GUI for the scenario.</p>
  </section>

  <section class="card">
    <h2>1 · Online SAP Logon</h2>
    <p class="hint">Opens Logon Pad, types <b>Client → User → Password</b> with visible mouse.</p>
    <label>System<input id="system" value="Vista"/></label>
    <label>Client (not username)<input id="client" value="100" maxlength="3"/></label>
    <label>Username<input id="user" value="SV3_000349"/></label>
    <label>Password<input id="password" type="password" placeholder="vault if empty"/></label>
    <div class="row">
      <button class="g" id="btnLogin">Login online</button>
      <button id="btnAttach">Attach open session</button>
      <button id="btnMouse">Move mouse</button>
      <button id="btnCaps">Status</button>
    </div>
  </section>

  <section class="card">
    <h2>2 · Extract real data</h2>
    <p class="hint">Multi-table pack from the live system (or SE16N if no RFC).</p>
    <label>Data pack<select id="pack"></select></label>
    <div class="row">
      <button class="p" id="btnGather">Extract pack</button>
      <button id="btnDebug">Debug symptom</button>
    </div>
    <label>Symptom<input id="symptom" value="payment method not found"/></label>
    <label>Ad-hoc tables (comma-separated)<input id="tables" value="EKKO,EKPO,LFA1,BSIK"/></label>
    <button id="btnTables">Extract tables</button>
  </section>

  <section class="card">
    <h2>3 · Inject + execute</h2>
    <p class="hint">Put extracted row values into the current SAP screen, then run the scenario.</p>
    <label>Scenario / pack id<select id="scenario"></select></label>
    <label>Inject from table<input id="injectTable" value="EKKO"/></label>
    <div class="row">
      <button id="btnInject">Inject first row into GUI</button>
      <button class="p" id="btnRun">Extract → inject → run</button>
      <button id="btnGoto">Goto tcode</button>
      <input id="tcode" value="ME23N" style="width:7rem"/>
    </div>
    <label class="hint"><input type="checkbox" id="requireReady"/> Require data pack READY before run</label>
  </section>

  <section class="card">
    <h2>4 · Screen</h2>
    <button id="btnScreen">Read current screen tree</button>
    <pre id="screen" style="margin-top:.7rem;max-height:200px">—</pre>
  </section>

  <section class="card wide">
    <h2>Output</h2>
    <pre id="out">Mega Co-pilot ready. Login online, then Extract pack.</pre>
  </section>
</main>
<footer>Localhost only · mouse ON · credentials in vault · RT controls apply</footer>
<script>
const out = (x) => document.getElementById('out').textContent = typeof x==='string'?x:JSON.stringify(x,null,2);
const api = async (path, body) => {
  const r = await fetch(path, {method: body?'POST':'GET', headers:{'Content-Type':'application/json'}, body: body?JSON.stringify(body):undefined});
  const j = await r.json();
  if (!r.ok && j.ok===false) throw new Error(j.error||r.statusText);
  return j;
};
async function refreshCaps(){
  try{
    const c = await api('/api/mega/status');
    const el = document.getElementById('status');
    el.textContent = c.online ? ('ONLINE · '+(c.extract_mode||'gui')) : 'offline';
    el.className = 'pill '+(c.online?'on':'');
  }catch(e){ document.getElementById('status').textContent='api down'; }
}
async function loadLists(){
  const p = await api('/api/mega/packs');
  const pack = document.getElementById('pack');
  const sc = document.getElementById('scenario');
  pack.innerHTML = sc.innerHTML = '';
  (p.packs||[]).forEach(x=>{
    const o=document.createElement('option'); o.value=x.id; o.textContent=`${x.id} — ${x.title} (${x.tables} tables)`;
    pack.appendChild(o); sc.appendChild(o.cloneNode(true));
  });
}
document.getElementById('btnLogin').onclick = async ()=>{
  out('Logging into SAP GUI online… watch mouse + login fields');
  try{ out(await api('/api/mega/login',{system:system.value,client:client.value,user:user.value,password:password.value})); await refreshCaps(); }
  catch(e){ out(String(e)); }
};
document.getElementById('btnAttach').onclick = async ()=>{ out(await api('/api/mega/attach',{})); await refreshCaps(); };
document.getElementById('btnMouse').onclick = async ()=>{ out(await api('/api/mega/mouse',{})); };
document.getElementById('btnCaps').onclick = async ()=>{ out(await api('/api/mega/status')); await refreshCaps(); };
document.getElementById('btnGather').onclick = async ()=>{
  out('Extracting multi-table pack online…');
  try{ out(await api('/api/mega/gather',{pack_id:pack.value,params:{}})); }catch(e){out(String(e));}
};
document.getElementById('btnDebug').onclick = async ()=>{
  out('Debugging with live tables…');
  try{ out(await api('/api/mega/debug',{symptom:symptom.value,params:{}})); }catch(e){out(String(e));}
};
document.getElementById('btnTables').onclick = async ()=>{
  const tables = tables.value.split(',').map(s=>s.trim()).filter(Boolean);
  out(await api('/api/mega/tables',{tables}));
};
document.getElementById('btnInject').onclick = async ()=>{
  out(await api('/api/mega/inject',{table:injectTable.value}));
};
document.getElementById('btnRun').onclick = async ()=>{
  out('Mega pipeline: extract → inject → execute…');
  try{ out(await api('/api/mega/run',{scenario_id:scenario.value,inject_table:injectTable.value,require_ready:requireReady.checked,params:{}})); }
  catch(e){out(String(e));}
};
document.getElementById('btnGoto').onclick = async ()=>{ out(await api('/api/mega/goto',{tcode:tcode.value})); };
document.getElementById('btnScreen').onclick = async ()=>{
  const s = await api('/api/mega/screen',{});
  document.getElementById('screen').textContent = JSON.stringify(s,null,2);
  out(s);
};
(async()=>{ await loadLists(); await refreshCaps(); })();
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(HTML)


@app.get("/api/mega/status")
def status():
    try:
        m = mega()
        return jsonify(m.list_capabilities())
    except Exception as e:
        return jsonify({"online": False, "error": str(e)})


@app.get("/api/mega/packs")
def packs():
    from sapilot.know.gather import list_packs

    return jsonify({"packs": list_packs()})


@app.post("/api/mega/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    global _MEGA
    from sapilot.mega.engine import MegaCopilot

    _MEGA = MegaCopilot(
        system=data.get("system") or "Vista",
        client=data.get("client") or "100",
        user=data.get("user"),
        password=data.get("password") or None,
        allow_mock=False,
        show_mouse=True,
    )
    try:
        return jsonify({"ok": True, **_MEGA.login()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 500


@app.post("/api/mega/attach")
def attach():
    try:
        return jsonify({"ok": True, **mega().attach()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/mega/mouse")
def mouse():
    try:
        mega().mouse_demo()
        return jsonify({"ok": True, "message": "mouse moved"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/mega/gather")
def gather():
    data = request.get_json(force=True, silent=True) or {}
    try:
        pack = mega().gather(data.get("pack_id") or "ptp_full_chain", data.get("params"))
        return jsonify({"ok": True, "pack": pack})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 500


@app.post("/api/mega/debug")
def debug():
    data = request.get_json(force=True, silent=True) or {}
    try:
        pack = mega().debug(data.get("symptom") or "", data.get("params"))
        return jsonify({"ok": True, "pack": pack})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/mega/tables")
def tables():
    data = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify({"ok": True, **mega().extract_tables(data.get("tables") or [])})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/mega/inject")
def inject():
    data = request.get_json(force=True, silent=True) or {}
    try:
        table = data.get("table") or "EKKO"
        return jsonify({"ok": True, **mega().inject_from_last_pack(table, data.get("fields"))})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/mega/run")
def run():
    data = request.get_json(force=True, silent=True) or {}
    try:
        result = mega().run_scenario(
            data.get("scenario_id") or "ptp_06_purchase_order",
            data.get("params"),
            require_ready=bool(data.get("require_ready")),
            inject_table=data.get("inject_table"),
            inject_fields=data.get("inject_fields"),
        )
        return jsonify({"ok": bool(result.get("ok")), **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 500


@app.post("/api/mega/goto")
def goto():
    data = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify({"ok": True, **mega().goto(data.get("tcode") or "ME23N")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/mega/screen")
def screen():
    try:
        return jsonify({"ok": True, "screen": mega().screen()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def main(host: str = "127.0.0.1", port: int = 8777) -> None:
    print("=" * 60)
    print("  MEGA SAP COPILOT")
    print(f"  Open → http://{host}:{port}")
    print("  LIVE login · multi-table extract · inject · execute")
    print("  Mouse ON · keep this window open")
    print("=" * 60)
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
