# SAPILOT System Status

**Generated:** 2026-08-12T04:27:45.034447+00:00
**Overall:** READY

| Check | Result | Detail |
|-------|--------|--------|
| unit_tests | PASS | ....................................................                     [100%]  |
| rt_probes | PASS | . Client is the 3-digit mandt (e. PASS - web binds 127.0.0.1  PASS - journal append  PASS - diagnose no BAPI post  PASS  |
| mission_critical_20 | PASS | illing document  precision=PASS   PASS  O9_AR: Customer open items AR  precision=PASS   PASS  O10_INCOMING: Incoming pay |
| auto_20_ptp_otc | PASS | -material info   OK  O4_SALES_ORG: Sales area configuration   OK  O5_SO: Sales order   OK  O6_DN: Outbound delivery   OK |
| policy_chokepoint | PASS | T3 blocked |

## Go-live controls closed

- Single WriteGuard on GuiDriver / inject / mega goto / scenarios
- Denylist → POLICY_VIOLATION hard-fail (agent loop HARD_FAIL)
- Vault DPAPI-first; weak default passphrase banned outside lab
- Portable HMAC approval tokens + JSONL ledger
- RunJournal SHA-256 hash chain
- Mission fingerprints 20/20 + document chain invariants

## Commands

```bat
python scripts\system_complete.py
python -m sapilot mission-critical --no-gui
python -m sapilot system-status
python -m sapilot auto-20
python scripts\rt_probes.py
```

## Live SAP still requires

- `sapgui/user_scripting = TRUE`
- Optional RFC (pyrfc) for direct table reads
- Dual control tokens for T2 (`sapilot approve --scope gui_write`)
