# Super Success Bot

Research-maximized autonomous SAP consultant — built to **win on evidence**, not hope.

## Research encoded into the design

| Source pattern | How we use it |
|----------------|---------------|
| Plan–Execute–Reflect (OpenSearch / agent PDCA) | `SuccessEngine` fixed plan, step retries, recovery replan |
| Never claim success without verifier | Final `verify()` on published criteria; score weighted 65% criteria |
| SAP GUI Scripting golden rules | `StartTransaction` / okcd only — never `/n` into Supplier |
| Hybrid RPA (UiPath-style cascade) | knowledge (tables) → twin invent → GUI optional |
| BAPI-first create when live blocked | Digital twin = `BAPI_PO_CREATE1` analog |
| Closed-loop document integrity | PO.NETWR=IR; SO=Billing=AR invariants |
| Pre-action authorization | WriteGuard on every GUI write |
| Fail closed / max thrash limit | 3 attempts/step, 2 replans, then FAIL |
| Tamper-evident audit | Hash-chained `SUPER_BOT_CHAIN.jsonl` |

## Run

```bat
python scripts\run_super_bot.py
python -m sapilot super-bot
python -m sapilot super-bot --live-gui
python -m pytest tests\test_super_bot.py -q
```

## Success definition (super)

A mission is **SUCCESS** only if:

1. Plan steps complete (or GUI legitimately skipped)  
2. Multi-table pack **READY** (zero blockers)  
3. **Exact fingerprint** match on critical fields  
4. **Zero** tcode pollution in LIFNR/KUNNR/…  
5. Fleet: PTP chain + OTC chain + journal chain valid  
6. Avg success score ≥ 0.99 across 20 missions  

## Architecture

```
SuperSuccessBot
  ├─ SuccessEngine (Plan→Exec→Reflect→Verify)
  ├─ Playbooks (20 deterministic skill plans)
  ├─ DigitalTwin (self-heal master/config/docs)
  ├─ ScenarioDataGatherer (multi-table)
  ├─ SafeNavigator (GUI COM, optional)
  └─ JournalHashChain + RunJournal
```

## Artifacts

- `data/runs/SUPER_BOT_20.json`  
- `data/runs/SUPER_BOT_CHAIN.jsonl`  
