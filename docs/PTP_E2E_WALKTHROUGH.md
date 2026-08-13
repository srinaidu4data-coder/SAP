# PTP (Procure-to-Pay) walkthrough — APEX-2023 / client 100

**System:** SAP Easy Access (APEX-2023), S/4HANA 2023 FP500  
**User:** SV3_000349  
**Date:** 2026-08-12  
**Mode:** Live SAP GUI. Prerequisites first, then a new Standard PO was posted.

Target cycle:

`Org + vendor + material` → `ME51N PR` → `ME21N PO` → `MIGO GR` → `MIRO IR`

## Prerequisite checklist

| Layer | What | Table / t-code | Status on this system |
|---|---|---|---|
| Company | Company codes | T001 | Yes (500). PTP docs use **1710**. |
| Plant | Plants | T001W | **Yes — 500 plants** (0001–1710, 1000, 1010, 1100, 1200, 1710). |
| Purch. org | Purchasing organizations | T024E | **Yes — 500.** `1000` Lupin Ltd, `1710` used on POs. |
| Purch. group | Purchasing groups | T024 | Present (T024E confirmed; T024 typeahead collided with T024E). |
| Vendor | General vendor master | LFA1 | **Yes — 500 vendors.** |
| Material plant | Plant material | MARC | **Yes — 500.** Materials `TG11`–`TG21`, plant `0001`. |
| PR | Purchase requisitions | EBAN | **Yes — 500.** Plant **1710**, materials `TG10`/`TG11`/`TG13`, tracking `001`. |
| PO | Purchase orders | EKKO | **Yes — 500.** CoCd **1710**, type `NB`, POrg `1710`, PGrp `002`, USD. |
| BAPI PO create | Function module exists | SE37 `BAPI_PO_CREATE1` | **Yes — exists** (Function Builder opened it). |
| SE38 | ABAP editor + execute | SE38 | **Yes.** Executed an MM report (selection screen). |
| Roles | Role assignments | AGR_USERS | **Yes — 500 assignments.** Composite + single roles. |
| ME51N | Create PR | ME51N | **Opens** (Create Purchase Requisition). |
| ME21N | Create PO | ME21N | **Opens** (Create Purchase Order). |
| ME23N | Display PO | ME23N | **Opens.** Showed STO **100011** (Pranali) and list of POs. |
| ME53N | Display PR | ME53N | **Opens** (Display Purchase Req. 10014061). |
| MIGO | Goods receipt | MIGO | **Opens** (Goods Receipt Purchase Order). |
| MIRO | Invoice | MIRO | Navigation raced; retry if needed. |

## Real keys to use on this client

| Kind | Value | Source |
|---|---|---|
| Company | `1710` | EKKO, EBAN (same as Treasury deals) |
| Plant | `1710` (docs), `0001` (MARC sample) | EBAN / T001W / MARC |
| Purch. org | `1710` | EKKO EKORG |
| Purch. group | `002` | EKKO EKGRP |
| Material | `TG10`, `TG11`, `TG13` | EBAN |
| Vendor (from POs) | `USSU-VSF01`, `C6-100`, `USSU-VSF06` | EKKO LIFNR |
| Sample PR | `10000000` / `10014061` | EBAN / ME53N |
| Sample PO | `4500000002` (NB), STO `100011` | EKKO / ME23N |

## Steps executed

### Step 0 — Leave Treasury

- Bound the same SAP process (pid 20608). It was on TPM20.
- `/nSESSION_MANAGER` returned to Easy Access.

### Step 1 — Plants (SE16N / T001W)

- **500 plants.** `0001` Werk 0001, `1000` Plant 1, `1010` Plant 2 Dresden, `1100`, `1200`, `1710`.
- Screenshot: `data/runs/live_ptp_e2e/se16n_T001W2.png`

### Step 2 — Purchasing orgs (SE16N / T024E)

- **500 purchasing organizations.** `1000` Lupin Ltd, `0001`, `0002`, …
- POs later showed purch. org **1710**.
- Screenshot: `data/runs/live_ptp_e2e/se16n_T024E.png`

### Step 3 — Vendors (SE16N / LFA1)

- **500 vendor masters.** Prerequisite for ME21N / MIRO is met at general-data level.
- Screenshot: `data/runs/live_ptp_e2e/se16n_LFA1.png`

### Step 4 — Plant materials (SE16N / MARC)

- **500 plant/material rows.** `TG11`–`TG21` on plant `0001`.
- PRs use `TG10`/`TG13` on plant **1710** — those exist in the PR table.
- Screenshot: `data/runs/live_ptp_e2e/se16n_MARC.png`

### Step 5 — Purchase requisitions (SE16N / EBAN)

- **500 PRs.** Document type `NB`, plant **1710**, qty 10, unit `PC`, tracking `001`.
- Materials `TG10`, `TG11`, `TG13`. Status `N` / `B`.
- Screenshot: `data/runs/live_ptp_e2e/se16n_EBAN.png`

### Step 6 — Purchase orders (SE16N / EKKO)

- **500 POs.** CoCd **1710**, type `NB` (and `ZNB`), POrg `1710`, PGrp `002`, USD.
- Example: `4500000002` vendor `USSU-VSF01`, created by `S4H_PURCH`.
- Screenshot: `data/runs/live_ptp_e2e/se16n_EKKO.png`

### Step 7 — BAPI check (SE37)

- `/nSE37` authorized.
- Entered `BAPI_PO_CREATE1`. Function Builder accepted it (**module exists**).
- F7 Display opened `Function Builder: Display BAPI_PO_CREATE1`.
- Not executed (would create a PO). Presence only.
- Screenshot: `data/runs/live_ptp_e2e/se37_BAPI_PO_CREATE1.png`

Related BAPIs to use the same way (same Function Builder):

- `BAPI_PR_CREATE` — PR
- `BAPI_GOODSMVT_CREATE` — GR (MIGO)
- `BAPI_INCOMINGINVOICE_CREATE` — IR (MIRO)
- `BAPI_PO_GETDETAIL1` — read PO

### Step 8 — SE38 program

- `/nSE38` authorized (ABAP Editor: Initial Screen).
- Executed a program (typeahead landed on a subcontracting-stock monitor). **Selection screen ran** — this user can execute ABAP reports.
- Screenshot: `data/runs/live_ptp_e2e/se38_init.png`, `se38_rm06ellb.png`

### Step 9 — Roles (SE16N / AGR_USERS)

- **500 role assignments.** Mix of composite (`Z:COMP_*`) and single (`Z:SING_*`) roles.
- Sample: `21850055` / `Z:COMP_2151_00_N`, `21860003` / `Z:COMP_2161_00_P`.
- This user opened ME51N/ME21N/ME23N/ME53N/MIGO — MM create+display is granted.
- Screenshot: `data/runs/live_ptp_e2e/se16n_AGR_USERS.png`

### Step 10 — Run transactions

| T-code | Result |
|---|---|
| ME23N | Displayed **Stock Transp. Order 100011** (Pranali). Other PO `4500000000` visible. |
| ME53N | **Display Purchase Req. 10014061.** Item 10, material `MZ-FG-C930`, plant `10`, qty 10 PC, tracking `001`. |
| MIGO | **Goods Receipt Purchase Order** opened (header + item grid). |
| ME51N | **Create Purchase Requisition** opened (ready to enter). |
| ME21N | **Create Purchase Order** opened (window title). |

Screenshots: `data/runs/live_ptp_e2e/me23n_blank.png`, `me53n_pr.png`, `tx_MIGO.png`, `tx_ME51N.png`.

## Documents created this session (2026-08-12)

Live create on APEX-2023 / client 100, user SV3_000349. Session pid 20608.

### Keys used (read from tables, then typed)

| Field | Value | Why this value |
|---|---|---|
| Document type | `NB` / Standard PO | EKKO type on existing 1710 POs |
| Vendor | `USSU-VSF01` | EKKO LIFNR on 4500000002+ (United States SU…) |
| Purch. org | `1710` | EKKO EKORG. **Not 1000** — ME21N rejects `USSU-VSF01` on POrg 1000 |
| Purch. group | `002` | EKKO EKGRP |
| Company code | `1710` | EKKO BUKRS (auto-filled from vendor) |
| Material | `TG10` | EBAN / existing PRs. Short text after Enter: `Trad.Good 10,PD,Third Party` |
| Qty / UoM | `10` / `PC` | Same pattern as EBAN |
| Delivery date | `08/31/2026` | After today (08/12/2026) |
| Net price / curr. | `10` / `USD` | MBEW std price band + EKKO WAERS |
| Plant | `1710` | EBAN WERKS / T001W |
| Storage loc. (GR) | `171B` | Used on earlier ME51N plant-1710 rows |
| Cost center (if K) | `1710-10` | CSKS, company 1710 — not needed on this stock line |

ME59N auto-PO was **not** the create path. Assigned PRs for vendor `17300001` / POrg 1710 / PGrp **001** failed with “Requisition could not be converted”. Existing posted POs use PGrp **002** and vendor `USSU-VSF01`.

### Step 11 — ME21N create PO

1. `/n` out of ME59N to Easy Access, then `ME21N`.
2. Document type already **Standard PO**.
3. Vendor field (right of Standard PO, not the PO number): `USSU-VSF01` + Enter.
4. Header → Org. Data auto-filled **1710 / 002 / 1710**.
5. Item overview first row: TG10, qty 10, PC, 08/31/2026, price 10, USD, plant 1710. Enter.
6. Short text and material group **L001** filled from the material.
7. Status: **Standard PO created under the number 4500002260**.

Screenshot: `data/runs/live_ptp_create/item_valid.png`, `po_created_msg.png`.

### Step 12 — MIGO goods receipt

1. Easy Access → `MIGO`. Opens **Goods Receipt Purchase Order**.
2. PO number `4500002260` + Enter. Item 10 loaded: TG10, 10 PC, plant 1710, vendor USSU-VSF01.
3. Item OK checked. Stor. loc. `171B` on the Where tab. Movement 101.
4. Post (Ctrl+S) returned:

   **Deficit of PU GR quantity 10 PC : TG10 1710 171B**

   MIGO still shows the PO. GR was **not** posted. TG10 short text is “Third Party”; plant/SLoc 1710/171B has no PU GR stock to receive against (typical for a PD third-party trading good that is not inventory-managed at that sloc).

Screenshot: `data/runs/live_ptp_create/nf2_load.png`, `migo_post.png`.

### Created document

| Doc | Number | Status |
|---|---|---|
| Purchase requisition | **10014063** | Proven in ME53N. K / TG10 × 10 PC / plant 1710 / sloc 171B / vendor USSU-VSF01 / POrg 1710 / PGrp 002 / CC 1710-10 |
| Purchase order | **4500002262** | Created this restart. NB, vendor USSU-VSF01, 1710/002/1710, acct **K** / CC **1710-10** / G/L **610000**, item TG10 × 10 PC @ 10 USD, plant 1710 |
| Purchase order | **4500002260** | Earlier create (no acct assignment) |
| Goods receipt | — | Blocked: deficit of PU GR qty TG10 / 1710 / 171B |
| Invoice (MIRO) | — | Not started; needs a posted GR |

## End-to-end picture

```
T001W plants (incl. 1710)
  + T024E purch. orgs (1710)
  + LFA1 vendors (USSU-VSF01)
  + MARC / MBEW materials (TG10)
        ↓
ME21N  Standard PO 4500002260   1710 / 002 / USSU-VSF01 / TG10 × 10 PC @ 10 USD
        ↓
MIGO   Goods Receipt 101 against 4500002260 loaded
        ↓
       Post blocked: Deficit of PU GR quantity 10 PC : TG10 1710 171B
        ↓
MIRO   not started (needs a posted GR)
```

PO **4500002260** is in EKKO. GR needs a stock-managed sloc (or a non-third-party material) before MIRO.

## How to run a new PR → PO → GR on this client

1. Focus Easy Access.
2. `/nME51N` — material `TG10`, plant `1710`, qty `10`, PC. Save. Note BANFN.
3. `/nME21N` — vendor `USSU-VSF01` (or the PR vendor), adopt the PR, purch. org `1710`, group `002`. Save. Note EBELN.
4. `/nMIGO` — Goods Receipt / Purchase Order / that EBELN. Post.
5. `/nMIRO` — company `1710`, that EBELN. Post.

Or create via SE37 `BAPI_PO_CREATE1` / `BAPI_GOODSMVT_CREATE` if GUI create is blocked later.

## Gaps

- PR **10014063** is saved and displayed in ME53N. 10014062 was not found in ME53N.
- ME59N cannot convert the 17300001 / PGrp 001 assigned PRs — use vendor `USSU-VSF01` / PGrp `002`.
- GR 101 on TG10 / plant 1710 / sloc 171B: **Deficit of PU GR quantity**. Material short text is Third Party; try a stock sloc from MARD, or a non-PD material, then MIRO.
- `T024` browse hit `T024E` via typeahead — group `002` is proven on EKKO and on the new PO.
- Do not execute create BAPIs from SE37 without a test payload — they post.
