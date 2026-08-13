# Treasury end-to-end walkthrough — APEX-2023 / client 100

**System:** SAP Easy Access (APEX-2023), S/4HANA 2023 FP500  
**User:** SV3_000349  
**Date:** 2026-08-12  
**Mode:** Live SAP GUI (human operator). Display / table browse only. No post, no save.

This note is the working log. New steps are appended as they are executed.

## Goal

See an end-to-end Treasury process on this sandbox:

Company / banks / product types → financial transactions → position flows → postings.

Create (`FTR_CREATE`) and deal display (`FTR_DISPLAY`, `TM_53`) are **not authorized** for this user. The chain is read from **SE16N** plus display reports that this user can run (`TPM13`).

## Real keys already confirmed in this client

| Object | Table | What we saw |
|---|---|---|
| Company codes | T001 | 500 codes. Includes `00IN` Apex Motors and `1710` (deal company). |
| House banks | T012 | 484. `00IN` has HDFC and ICICI. |
| House bank accounts | T012K | 387. `00IN` / HDFC / `10065476580` / G/L `10006010`. |
| Product types | TZPA | 134 FAM product types (`01A`, `02A`–`02C`, `04*`, `60A`, …). |
| Financial transactions | VTBFHA | **286 deals, all company 1710**, partner `17537001`, user `S4H_FIN`. Example deal `1000000000000` (product `02B`, USD, 15.11.2020). |

## Authorization map (this user)

| T-code | Allowed? |
|---|---|
| SE16N | Yes |
| TPM13 (Position Flows) | Yes |
| FTR_CREATE | No |
| FTR_DISPLAY | No |
| TM_53 | No |

## Steps executed

### Step 0 — Bind the GUI

- Bound `SAP_FRONTEND_SESSION` hwnd+pid (process 20608).
- Command field identified as a real Edit control (not a window-fraction click).

### Step 1 — Company codes (SE16N / T001)

- `/nSE16N` → table `T001` → F8 → List Output.
- **500 hits.** `00IN` Apex Motors India Pvt ltd is present.
- Screenshot: `data/runs/20260812T200234Z_a83f1ea7/shots/se16n_T001.png`

### Step 2 — House banks (SE16N / T012)

- Table `T012` → **484 hits.**
- `00IN` + HDFC / ICICI confirmed.
- Screenshot: `data/runs/20260812T200234Z_a83f1ea7/shots/se16n_T012.png`

### Step 3 — House bank accounts (SE16N / T012K)

- Table `T012K` → **387 hits.**
- `00IN` / HDFC / acct `HDFC0` / bank account `10065476580`.
- Screenshot: `data/runs/20260812T200234Z_a83f1ea7/shots/se16n_T012K.png`

### Step 4 — TRM product types (SE16N / TZPA)

- Table `TZPA` → **134 hits** (Financial Assets Management Product Types).
- Screenshot: `data/runs/20260812T200234Z_a83f1ea7/shots/se16n_TZPA.png`

### Step 5 — Financial transactions (SE16N / VTBFHA)

- Table `VTBFHA` → **286 hits.**
- All rows company **1710**. Product types `02A`/`02B`/`02C` (MM) and `60A`/`60B` (FX).
- Partner `17537001`. Activity 1–3.
- Screenshot: `data/runs/20260812T200234Z_a83f1ea7/shots/se16n_VTBFHA.png`

### Step 6 — Try deal create / display

- `/nFTR_CREATE` → **not authorized.**
- `/nFTR_DISPLAY` → **not authorized.**
- `/nTM_53` → **not authorized.**

Deal header/display tcodes cannot be used. Continue via tables + TPM13.

### Step 7 — Position flows display (TPM13)

- `/nTPM13` authorized. Screen: **Treasury Position Flows – Classic**.
- First compile of `RTPM_TRL_SHOW_FLOWS` took several seconds.
- Filled company **1710**, TRL date **01/01/2020–12/31/2026**, Securities ticked, F8.
- Result: **No positions selected.**
- Meaning: contracts exist in `VTBFHA`, but this Securities selection has no TRL positions. Flows still live on the deal (next steps).

### Step 8 — Deal conditions (SE16N / VTBFINKO)

- Table `VTBFINKO` (Financial Transaction Conditions).
- **1,634 hits.** Company 1710, deal `1000000000000`, activities 1–3.
- Conditions `1100` (interest), condition types `1` and `3`, currency **USD**.
- Rates seen: 2.5000000, 2.5312500, 8.0000000. Payment freq `01` / `12`.
- Screenshot: `data/runs/live_treasury_e2e/se16n_VTBFINKO.png`

### Step 9 — Deal flows (SE16N / VTBFHAPO)

- Table `VTBFHAPO` (transaction activity / flow items).
- **At least 500 hits** (list capped).
- Deal `1000000000000`, activity `1` and `2`, flow `1`, company 1710.
- Screenshot: `data/runs/live_treasury_e2e/se16n_VTBFHAPO.png`

### Step 10 — Deal activities (SE16N / VTBFHAZU)

- Table `VTBFHAZU` (transaction activity header).
- **At least 500 hits.**
- Activity `1` = contract; activity `2` = subsequent activity (settle / roll).
- Same deal numbers as VTBFHA / VTBFHAPO.
- Screenshot: `data/runs/live_treasury_e2e/se16n_VTBFHAZU.png`

### Step 11 — Tables that do not exist here

- `VTBFFO` — does not exist.
- `TRLT_TRANSACT` / `TRLT_TRANSACTION` / `TRLT_FLOW` — do not exist (S/4 uses other TRL names).
- Do not use these names on this system.

### Step 12 — Posting journal (TPM20) — end of the chain

- `/nTPM20` authorized. Screen: **Treasury Posting Journal – Classic**.
- Entered company **1710**, executed display.
- **Result: live posting journal.** Green status, company 1710.
- Example posted deals: `1000000000021`, `1000000000022`, `1000000000023`.
- Product types `51A` / `51B` / `51C`. Update type / payment `1100`.
- Posted dates from 2021 through 2026. Many document numbers (`RFHAID` 1, 5, 247, …).
- Screenshots: `data/runs/live_treasury_e2e/tpm20_filled.png`, `tpm20_result.png`

This is the FI end of the Treasury process: deal → activity → flow → **posted journal**.

---

## End-to-end chain (this sandbox)

```
T001 company 1710
  → T012 / T012K house banks (also 00IN HDFC/ICICI)
  → TZPA product types (02A/02B/02C MM, 51A–C, 60A FX)
  → VTBFHA          286 deal headers          (user S4H_FIN, partner 17537001)
  → VTBFHAZU        500+ activities           (1 = contract, 2 = next activity)
  → VTBFINKO        1,634 conditions          (interest 2.5%–8%, USD)
  → VTBFHAPO        500+ deal flows
  → TPM20           posting journal           (FI docs on 1710, deals …021–023)
```

TPM13 position flows were empty for Securities / 1710. Deals are posted (TPM20) even when TRL position display shows nothing for that product-group selection.

## How to replay (display only)

1. Log on to APEX-2023, focus SAP Easy Access.
2. `/nSE16N` → `T001` → F8 → List Output (companies).
3. Repeat for `T012`, `T012K`, `TZPA`, `VTBFHA`, `VTBFINKO`, `VTBFHAPO`, `VTBFHAZU`.
4. `/nTPM20` → company `1710` → tick the product groups you need → F8.
5. Optional: `/nTPM13` for TRL position flows (may be empty depending on product group).
6. Do **not** use `FTR_CREATE` / `FTR_DISPLAY` / `TM_53` with user SV3_000349 — not authorized.

## Gaps (if you want a create-to-post demo later)

- This user cannot create or display a single deal on `FTR_*`.
- Need role with `FTR_CREATE` / `FTR_DISPLAY`, or a different user (deals were created by `S4H_FIN`).
- `00IN` has banks but **no** VTBFHA deals; all 286 deals are company **1710**.
