# Analysis — start here

**If you are a process consultant, read
[CONSULTANT_BRIEFING.md](CONSULTANT_BRIEFING.md) first.**

That briefing is the analysis: how buy, sell, make, cost, and collect
connect on company 1710; where the P&L is lying; the trade-offs; and which
operating model to choose. It is not a list of counts.

This file is only the product note for the team that runs the glass.

---

## What this wing does (one sentence)

It **looks** at a live SAP system and answers: *which business processes
already run here, where cash and cost get stuck, and what a consultant should
change in the operating model — not what to configure next.*

It does not create documents. The display wing walks display screens only
([DISPLAY_WING.md](DISPLAY_WING.md)).

## How to publish a finding

Write it so a functional consultant can act without a data dictionary.

Wrong: “TCK03 = 74, KEKO = 3,472, KNKK = 0.”  
Right: “There are 74 costing recipes and no credit limits. Pick one recipe.
Decide whether orders stay unsecured.”

The briefing is the template. Table names belong in an appendix.

## Evidence (still required)

Every number in the briefing was counted on the live system (true population,
not a 500-row list). We do not invent counts. We do not call a 500-row list
“the whole table.”

## Technical appendices (not the briefing)

| Process | Technical map |
|---|---|
| Buy / pay | `PTP_OPPORTUNITY_MAP.md` |
| Sell / collect | `OTC_EXHAUSTIVE_ANALYSIS.md` |
| Credit / dunning / disputes | `COLLECTIONS_DISPUTES_MINDMAP.md` |
| Make / cost | `PRODUCT_COSTING_MINDMAP.md` |
| Display walks | `DISPLAY_WING.md` |
| Next processes | `ANALYSIS_FUTURE_MODULES.md` |
