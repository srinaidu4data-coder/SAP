# SAPILOT — Autonomous SAP Execution Agent

Portable Windows agent for SAP payment-run **diagnosis** and (tier-gated) execution.  
Built from the multi-agent reviewed master package: SOD tiers, grounded GUI actions, redaction, governor, full journal.

> **The product is the diagnostic layer.** The autonomous F110 demo is the showcase.

## Quick start (no SAP required)

```bat
python -m pip install -e ".[dev]"
set SAPILOT_ALLOW_UNSIGNED_POLICY=1
python -m sapilot preflight
python -m sapilot diagnose --bukrs 1000 --method A --mock
python -m pytest
```

Or: `run.bat diagnose --bukrs 1000 --method A --mock`

## What you get

| Capability | Status |
|---|---|
| Three-tier policy (`T1`/`T2`/`T3`) from T000 + local policy | Implemented |
| Destructive denylist (F110 Start Immediately, etc.) | Implemented |
| Redaction gate on model egress | Implemented |
| RFC knowledge channel + mock tables | Implemented |
| FBZP / vendor / BSIK diagnostic engine + HTML report | Implemented |
| Grounded GUI executor + MockGuiSession | Implemented |
| Governor (budgets, novelty) | Implemented |
| Agent ReAct loop + critic + SpaceXAI router | Implemented (API key optional; stubs offline) |
| Live pyrfc / SAP GUI attach | Implemented; needs Basis + SDK + GUI |
| ADT debugger (read-only vars) | Scaffold; T1 only |
| Config apply into `SAPILOT_AUTOCFG` | Propose/diff complete; live writer hooks per landscape |

## Architecture

```
sapilot/
  preflight.py          # refuses start with remediation messages
  policy/               # tier, denylist, approval tokens
  connect/              # GUI, logon, RFC, OData, HANA, ADT
  observe/              # screen tree, messages, ALV, vision gate
  know/                 # tables, playbooks, error maps, SQLite memory
  diagnose/             # payment-run diagnostic engine (the product)
  act/                  # grounded executor, config writer
  brain/                # loop, governor, router, critic, prompts
  verify/               # predicates, evidence pack
  report/               # JSONL journal + HTML
  security/             # redaction, DPAPI vault
```

## Mega SAP Co-pilot (online extract + inject + execute)

Full product loop on **live SAP**:

1. Login GUI (Client → User → Password, **mouse visible**)
2. Extract **multiple real tables** (RFC or SE16N GUI)
3. Debug readiness
4. **Inject** extracted values into screens
5. Execute scenario / tcode
6. Journal everything

```bat
start_mega_copilot.bat
REM opens http://127.0.0.1:8777

python -m sapilot mega login --system Vista --client 100 --user SV3_000349
python -m sapilot mega gather ptp_full_chain --attach
python -m sapilot mega run ptp_06_purchase_order --attach --inject-table EKKO
```

Requires: SAP GUI, scripting enabled on server (`sapgui/user_scripting=TRUE`), and ideally `pyrfc`+NW RFC SDK for fast table reads (else SE16N channel).

## Co-pilot — REAL SAP GUI (default)

**Primary mode:** open **SAP Logon Pad**, log in with **your username/password**, drive
the real GUI (clicks, tcodes, table extract). **Mock is only for offline tests (`--mock`).**

### Live login (what you will use)

1. SAP GUI for Windows installed; scripting enabled (`BASIS_PREREQUISITES.md`).
2. `pip install pywin32`
3. Logon Pad system name must match **exactly** (as shown in SAP Logon).

```bat
REM Prompt for password securely:
python -m sapilot copilot login --system "ECC Dev" --client 100 --user MYUSER

REM Or one-shot scenario after Logon Pad login:
python -m sapilot copilot run f110_parameters --system "ECC Dev" --client 100 --user MYUSER

REM Natural language on real GUI:
python -m sapilot copilot goal "Demo Product Costing Run" --system "ECC Dev" --client 100 --user MYUSER

REM Already logged on — attach to open session:
python -m sapilot copilot screen --attach
python -m sapilot copilot goto CK40N --attach
```

Save credentials once (encrypted vault; include Logon description):

```bat
python -m sapilot vault set myecc --system "ECC Dev" --client 100 --user MYUSER --ashost 10.0.0.5
python -m sapilot copilot run f110_diagnose --connection myecc
```

Env alternatives: `SAPILOT_SYSTEM`, `SAPILOT_CLIENT`, `SAPILOT_USER`, `SAPILOT_PASSWORD`.

### Offline mock only (developers / CI)

```bat
python -m sapilot copilot run f110_diagnose --mock
python -m sapilot copilot extract T042E --mock
```

Built-in scenarios: `f110_diagnose`, `f110_parameters`, `vendor_display`, `vendor_line_items`,
`read_table`, `se16_browse`. Add YAML under `sapilot/copilot/scenarios/`.

## Commands

```bat
sapilot preflight
sapilot diagnose --bukrs 1000 --method A --mock
sapilot copilot scenarios
sapilot copilot run f110_diagnose --mock
sapilot vault set myecc --ashost ... --client 100 --user ... --system "My SID"
sapilot approve --scope f110.proposal
sapilot copilot goal "demo ACH payment run for company 1000" --mock
```


## Model keys

```bat
set XAI_API_KEY=...
set SAPILOT_PLANNER_MODEL=grok-4.5
```

See `.env.example`, `SECURITY.md`, `BASIS_PREREQUISITES.md`, `DECISIONS.md`.

## License

Proprietary — consultancy use. Do not deploy to production clients without control-owner sign-off (T3 observe-only diagnostics are the intended prod mode).
