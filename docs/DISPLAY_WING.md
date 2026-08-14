# Display wing

Sibling of the [analysis wing](ANALYSIS_WING.md).

Analysis **counts** (SE16N Number of Entries).  
This wing **walks the glass** in **display t-codes only** so a human can see
the full cycle: enterprise structure → master data → transactional flow →
financial line.

**It does not create anything.** Existing documents are looked at.

## Product (process-agnostic)

```
sapilot display list
sapilot display plan <cycle>
sapilot display goto <DISPLAY_TCODE>
sapilot display walk <cycle> [--key name=value]
```

A cycle is a **spine**, not a module brand:

```
org → master → transaction → document flow → financial display
```

PTP, OTC, CO-PC, R2R, Collections are **example spines**. The operator is
still a general SAP GUI person. A t-code used in an example is not the product.

## Hard rules

1. Create / change / post / customizing t-codes are a **hard refuse**
   (`ME21N`, `VA01`, `MIGO`, `MIRO`, `FB50`, `CK11N`, `SM30`, `SPRO`, …).
2. Asking for a create t-code does **not** silently open it. The twin is
   suggested (`ME21N` → use `ME23N`) but never auto-opened as the create screen.
3. If the window title looks like Create / Post / Goods Receipt / Enter Invoice,
   the walker hits **F12** and aborts. It never presses Save, Post, or Hold.
4. Empty keys: still open the **Display** initial screen. That is evidence
   the t-code exists in display mode. It is not a document proof.
5. Never claim CREATED. This wing has no `prove` for creates.

## Example spines (not the product)

| Cycle | Spine | Display t-codes |
|---|---|---|
| `ptp` | company → vendor → material → PR → PO → GR doc → IR → vendor line | SE16N, XK03, MM03, ME53N, ME23N, MB03, MIR4, FBL1N |
| `otc` | sales org → customer → material → SO → DN → bill → AR | SE16N, XD03, MM03, VA03, VA05, VL03N, VF03, FBL5N |
| `copc` | CO assignment → cost center → material → estimate → order → ML | SE16N, KS03, MM03, CK13N, CO03, CKM3N |
| `r2r` | company → G/L → FI doc → G/L line | SE16N, FS03, FB03, FBL3N |
| `collections` | customer → AR line → credit display → bill | XD03, FBL5N, FD33, VF03 |

## Evidence

Each walk writes:

- `data/runs/display_<cycle>_<ts>/walk.json`
- `data/runs/display_<cycle>_<ts>/WALK.md`
- one screenshot per step (`*_open.png`, `*_after.png`)

Ranks stay the same as the analysis wing: **LIVE** (we opened the display
screen) / **ABSENT** (t-code refused or write screen aborted).

## First live walk (APEX-2023)

See `DISPLAY_WALK_PTP.md`. Display titles opened: SE16N, XK03, MM03, ME53N, ME23N (STO 100011 / Pranali), MIR4, FBL1N. `ME21N` refused. Nothing created.

## Relationship to analysis

| Wing | Question | Glass |
|---|---|---|
| Analysis | What is configured / used / one hop away? | SE16N Number of Entries, SE37 display |
| Display | What does the cycle **look like** end to end? | ME23N, VA03, CK13N, FB03, … |
| Hands | Create (not this wing) | refused here |
