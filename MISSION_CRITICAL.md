# Mission-Critical Operating Standard

This system is built to **fail closed**, **verify after change**, and **prove** results — not “hope”.

Precision here means **engineering controls with automated evidence**, not marketing language.

## Engineering principles (NASA / SpaceX style)

| Principle | Implementation |
|-----------|----------------|
| Fail closed | Unknown / missing data / empty gate = **NO-GO** |
| Exact fingerprints | All 20 packs have published `PACK_EXACT` keys in `sapilot/mission/precision.py` |
| Amount precision | Decimal-safe compare (`amount_equal`, 2 places) for NETWR / RMWWR / WRBTR |
| Document chain invariants | PO.NETWR == IR.RMWWR; SO.NETWR == BILL.NETWR == AR.WRBTR; PO.MENGE == GR.MENGE |
| No silent wrong field | Tcode strings **abort** if targeted at LIFNR/KUNNR/etc. (precision + navigator + executor) |
| Tamper-evident log | SHA-256 hash chain + monotonic `seq` → `MISSION_CRITICAL_CHAIN.jsonl` |
| Manifest hash | `manifest_hash()` of all fingerprints published at mission start |
| Deterministic missions | Fixed packs + expected values for regression |
| Safe GUI | `StartTransaction` / okcd only — never form-body tcode typing |
| Executor choke-point | `GroundedExecutor` SET_TEXT refuses `/n…` outside ok-code field |

## Run (evidence required)

```bat
python scripts\run_mission_critical_20.py
python -m pytest tests/test_mission_precision.py -q
```

Exit code **0** only if:

- `ok_count == 20`
- `all_pass == true`
- `journal_chain_valid == true`
- `fingerprint_coverage == 20/20`
- document chain invariants empty

Artifacts:

- `data/runs/MISSION_CRITICAL_20.json` — per-mission gate board + table counts  
- `data/runs/MISSION_CRITICAL_CHAIN.jsonl` — append-only hash chain  

## Go / No-Go (per scenario)

A scenario **PASS** only if **all** hold:

1. Fingerprint for pack is **published** before run  
2. Multi-table extract succeeds (`extract_channel_present`)  
3. No tcode garbage in business keys (`no_tcode_in_master_data`)  
4. **Exact** fingerprint match on critical fields  
5. Structural READY after remediations  
6. GUI fill (if scriptable) never writes `/n…` into data fields  
7. Hash chain remains valid for the full run  

Empty MissionGate → **NO-GO** (fail closed). Soft “looks ready” paths were removed.

## What this does *not* claim

True live SAP production control still requires:

- `sapgui/user_scripting = TRUE` for COM-driven GUI  
- RFC SDK (pyrfc / NWRFC) for direct production table reads  
- Change control / dual control / approvals for real postings  
- Environment-specific master data (fingerprints are twin/demo contractual IDs)

This codebase enforces **precision on the bot’s own logic and twin**, **safe patterns** for live GUI so the `/NF110 in Supplier` class of errors is **hard-aborted**, and **tamper-evident proof** of every autonomous mission.

## Code map

| Module | Role |
|--------|------|
| `sapilot/mission/precision.py` | Gates, fingerprints, hash chain, invariants |
| `sapilot/mission/critical_runner.py` | 20-scenario fail-closed runner |
| `scripts/run_mission_critical_20.py` | CLI entry |
| `tests/test_mission_precision.py` | Regression bar |
| `sapilot/act/executor.py` | SET_TEXT choke-point for tcode-in-data |
| `sapilot/autobot/navigator.py` / `human_operator.py` | Safe StartTransaction / field fill |
