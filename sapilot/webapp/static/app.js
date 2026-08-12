async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok && data.ok !== true) {
    const err = data.error || res.statusText;
    throw new Error(err + (data.trace ? "\n" + data.trace : ""));
  }
  return data;
}

function setOut(obj) {
  document.getElementById("out").textContent =
    typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

function busy(btn, on) {
  if (!btn) return;
  btn.disabled = !!on;
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    document.getElementById("statusBox").textContent = JSON.stringify(s, null, 2);
  } catch (e) {
    document.getElementById("statusBox").textContent = String(e);
  }
}

async function refreshJournal() {
  try {
    const j = await api("/api/journal");
    document.getElementById("journal").textContent =
      (j.path || "") + "\n\n" + (j.lines || []).join("\n");
  } catch (e) {
    document.getElementById("journal").textContent = String(e);
  }
}

async function loadScenarios() {
  const data = await api("/api/scenarios");
  const sel = document.getElementById("scenario");
  sel.innerHTML = "";
  (data.scenarios || []).forEach((s) => {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = `${s.id} — ${s.title}`;
    sel.appendChild(o);
  });
}

async function loadPacks() {
  const data = await api("/api/packs");
  const sel = document.getElementById("pack");
  if (!sel) return;
  sel.innerHTML = "";
  (data.packs || []).forEach((p) => {
    const o = document.createElement("option");
    o.value = p.id;
    o.textContent = `${p.id} — ${p.title} (${p.tables} tables)`;
    sel.appendChild(o);
  });
}

document.getElementById("btnLogin").onclick = async () => {
  const btn = document.getElementById("btnLogin");
  busy(btn, true);
  setOut("Logging in… watch SAP Logon / login window.");
  try {
    const body = {
      system: document.getElementById("system").value,
      client: document.getElementById("client").value,
      user: document.getElementById("user").value,
      password: document.getElementById("password").value,
    };
    const data = await api("/api/login", { method: "POST", body: JSON.stringify(body) });
    setOut(data);
    await refreshStatus();
  } catch (e) {
    setOut("Login error:\n" + e.message);
  } finally {
    busy(btn, false);
  }
};

document.getElementById("btnStatus").onclick = () => refreshStatus();

document.getElementById("btnMouse").onclick = async () => {
  setOut("Moving mouse on SAP window — watch your cursor…");
  try {
    const data = await api("/api/mouse-demo", { method: "POST", body: "{}" });
    setOut(data);
  } catch (e) {
    setOut("Mouse demo error:\n" + e.message);
  }
};

document.getElementById("btnGoto").onclick = async () => {
  setOut("Starting transaction…");
  try {
    const data = await api("/api/goto", {
      method: "POST",
      body: JSON.stringify({ tcode: document.getElementById("tcode").value }),
    });
    setOut(data);
  } catch (e) {
    setOut("Goto error:\n" + e.message);
  }
};

document.getElementById("btnScreen").onclick = async () => {
  setOut("Reading screen…");
  try {
    const data = await api("/api/screen", { method: "POST", body: "{}" });
    setOut(data);
  } catch (e) {
    setOut("Screen error:\n" + e.message);
  }
};

document.getElementById("btnGoal").onclick = async () => {
  const btn = document.getElementById("btnGoal");
  busy(btn, true);
  setOut("Running AI goal…");
  try {
    const data = await api("/api/goal", {
      method: "POST",
      body: JSON.stringify({
        goal: document.getElementById("goal").value,
        mock: document.getElementById("goalMock").checked,
        attach: !document.getElementById("goalMock").checked,
        max_steps: 12,
      }),
    });
    setOut(data);
    await refreshJournal();
  } catch (e) {
    setOut("Goal error:\n" + e.message);
  } finally {
    busy(btn, false);
  }
};

document.getElementById("btnGather").onclick = async () => {
  setOut("Gathering multi-table data pack…");
  try {
    const data = await api("/api/gather", {
      method: "POST",
      body: JSON.stringify({
        pack_id: document.getElementById("pack").value,
        mock: document.getElementById("dataMock").checked,
        params: {},
      }),
    });
    setOut(data);
    await refreshJournal();
  } catch (e) {
    setOut("Gather error:\n" + e.message);
  }
};

document.getElementById("btnDebug").onclick = async () => {
  setOut("Debugging across tables…");
  try {
    const data = await api("/api/debug", {
      method: "POST",
      body: JSON.stringify({
        symptom: document.getElementById("symptom").value,
        mock: document.getElementById("dataMock").checked,
        params: {},
      }),
    });
    setOut(data);
    await refreshJournal();
  } catch (e) {
    setOut("Debug error:\n" + e.message);
  }
};

document.getElementById("btnPrepareRun").onclick = async () => {
  setOut("Gather data then execute scenario…");
  try {
    const data = await api("/api/prepare-run", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: document.getElementById("pack").value,
        mock: document.getElementById("dataMock").checked,
        require_ready: false,
        params: {},
      }),
    });
    setOut(data);
    await refreshJournal();
  } catch (e) {
    setOut("Prepare-run error:\n" + e.message);
  }
};

document.getElementById("btnScenario").onclick = async () => {
  const btn = document.getElementById("btnScenario");
  busy(btn, true);
  setOut("Running scenario…");
  try {
    const data = await api("/api/scenario", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: document.getElementById("scenario").value,
        mock: document.getElementById("scMock").checked,
        attach: !document.getElementById("scMock").checked,
      }),
    });
    setOut(data);
    await refreshJournal();
  } catch (e) {
    setOut("Scenario error:\n" + e.message);
  } finally {
    busy(btn, false);
  }
};

(async function init() {
  try {
    const h = await api("/api/health");
    const el = document.getElementById("health");
    el.textContent = h.openai ? "OpenAI ready · local UI" : "UI up · set OPENAI_API_KEY";
    el.className = "pill ok";
  } catch {
    const el = document.getElementById("health");
    el.textContent = "API down";
    el.className = "pill bad";
  }
  await loadScenarios();
  await loadPacks();
  await refreshStatus();
  await refreshJournal();
})();
