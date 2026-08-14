# Display walk — PTP example (APEX-2023 / client 100)

**Mode:** display t-codes only. Nothing in this file was created.  
**Product:** `sapilot display walk ptp` — see `DISPLAY_WING.md`.  
**Runs:** `data/runs/display_ptp_20260813T165902Z` and `…T170307Z`.

`ME21N` was refused at the CLI (`Use display twin ME23N`) and was never opened.

## Spine on the glass (LIVE titles)

| Phase | T-code | Window title we saw | What it is |
|---|---|---|---|
| Org | SE16N | General Table Display | Enterprise table display. Not OX02. |
| Master | XK03 | Display Supplier: Initial Screen | Display-only supplier. Mandatory Supplier field empty — we did not post. |
| Master | MM03 | Display Material (Initial Screen) | Display-only material. |
| Transaction | ME53N | Display Purchase Req. | Display-only PR. Personal Settings overlay opened; **not saved**. |
| Transaction | ME23N | Stock Transp. Order **100011** Created by **pranali** | Existing STO. Item 10 / material `11000000000001196` Speaker / supplying plant SP99 / 22.12.2025. **Looked at. Not created.** |
| Transaction | MIR4 | Display Invoice Document | Display-only IR. Never MIRO. |
| Financial | FBL1N | Vendor Line Item Display | Display report. Never F-53 / F110. |
| Transaction | MB03 | (blank SAP shell on first pass) | Display twin of MIGO. Did not land cleanly this run. |

## Drill

ME23N showed **Document Overview On** on STO 100011. That is the document-flow hinge for PTP (PO → GR → IR) without leaving display.

## What we did **not** do

- No ME21N / ME51N / MIGO / MIRO / FB50.
- No Save / Post / Hold on any screen.
- Shortcut wizard “Create New SAP Shortcut” is a GUI favorite, not a business document. Cancelled.
- Personal Settings on ME53N — Cancel / X only.

## CO-PC example (`display walk copc`)

`data/runs/display_copc_20260813T170700Z`

| T-code | Title | Rank |
|---|---|---|
| SE16N | General Table Display | LIVE |
| KS03 | Display Cost Center: Initial Screen | LIVE |
| MM03 / CK13N / CO03 / CKM3N | stayed on cost-center display (goto did not leave) | not landed — not claimed |

`CK11N` / `CK24` / `CKMLCP` were never opened.

## Keys used as *look-up*, not creates

1710 / USSU-VSF01 / TG10 / PR 10014061 / PO 4500000002 — from the analysis book. Fill often missed the field; the **titles** are the evidence the t-code is in display mode. STO 100011 is the one document body we fully saw.
