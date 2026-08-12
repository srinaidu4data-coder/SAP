# Research: building a comprehensive SAP Auto AI Bot

## What the market uses (2024–2026)

| Approach | Tools | Notes |
|----------|--------|------|
| **SAP GUI Scripting** | Python `win32com`, VBS recordings | Best fidelity; needs `sapgui/user_scripting=TRUE` |
| **RPA without scripting** | UiPath UIExplorer AA, Power Automate desktop, **pywinauto** | Mouse/keyboard + accessibility when scripting blocked |
| **Hybrid** | COM + Windows API mouse/keyboard | Same pattern as security testing blogs (AFINE 2025) |
| **API / BAPI** | `pyrfc`, `BAPI_PO_CREATE1`, RFC_READ_TABLE | Headless create/read; no mouse; needs NW RFC SDK |
| **Orchestration** | BotCity, UiPath, custom Flask UI | Deploy, schedule, human-in-the-loop messages |

Sources: SAP Community GUI Scripting+Python; Microsoft PAD SAP scripting docs; UiPath forums (scripting disabled → AA selectors); BAPI_PO_CREATE1 for PO create; GitHub SAP-LOGON-GUI-Automation (pywinauto).

## Our architecture (invented hybrid → Super Success)

```
SuperSuccessBot (primary)
    → SuccessEngine: Plan → Execute → Reflect → Verify
    → Playbooks: 20 deterministic PTP+OTC skill plans
    → Channel cascade: knowledge (tables) → twin invent → GUI COM
    → Exact fingerprints + document chain invariants
    → WriteGuard policy + hash-chained journal
    → Scoreboard: verified success only (no unverified claims)

Legacy ConsultantBot still available for simple walks.
```

When live scripting is off: **still complete 20 scenarios** by self-healing the twin. GUI is opt-in (`SAPILOT_LIVE_GUI=1`).

See `SUPER_BOT.md` for the research map and run commands.

## Stealth

Browser UI at :8788 — **Stealth** blacks out UI; bot thread continues. ESC / Show UI restores.

## Autonomy criteria (consultant-like)

1. Read multi-table packs  
2. Detect blockers  
3. **Create missing** config/master (twin / future BAPI)  
4. Re-verify  
5. Navigate GUI with mouse  
6. Log everything  
