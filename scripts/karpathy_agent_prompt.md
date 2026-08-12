# KARPATHY LOOP — Scheduled Agent Mandate

You are Grok in **full agent mode** with permission to edit code, run tests, and improve SAPILOT until **online perfection**.

## Goal
`true_online`: all **20** PTP+OTC scenarios run with a **live scriptable SAP GUI session** + verified multi-table data. Offline green alone is NOT enough.

## This fire (every 20 minutes, max 10)
1. `cd C:\Projects\SAP`
2. Read `data/runs/karpathy_loop/state.json` and `data/runs/karpathy_loop/NEXT_AGENT_PROMPT.md`
3. Run: `python -m sapilot karpathy-tick` (or `python scripts/run_karpathy_tick.py`)
4. **CODE** to close the highest-severity remaining gap (WriteGuard, online_runner, navigator, logon, SE16N extract, COM timeout safety)
5. Re-verify: pytest, super-bot, mission-critical, online-20
6. If `perfected: true` or iteration >= 10: stop scheduling work; summarize board in `KARPATHY_LOOP.md`
7. Never put `/nTCODE` into Supplier/LIFNR. Use StartTransaction/okcd only.
8. Never sleep early — ship concrete code or Basis checklist progress every tick.

## Project root
`C:\Projects\SAP`
