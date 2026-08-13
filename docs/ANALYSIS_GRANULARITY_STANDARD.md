# Analysis wing — granularity standard

Use this for **every** future process (Product Costing, Collections, Disputes, OTC, PTP, R2R). A 50-page memo that skips a leaf is incomplete.

## 1. Mind-map shape (every process, every time)

```
PROCESS
├── PHASE
│   ├── SCENARIO
│   │   ├── Trigger (who/what starts it)
│   │   ├── Org keys (BUKRS, WERKS, KOKRS, VKORG, BWKEY, …)
│   │   ├── Config (SPRO table + field + legal value)
│   │   ├── Master (table-FIELD, not just table)
│   │   ├── Transaction (header + item + status + history)
│   │   ├── Quantity / value / currency / period
│   │   ├── Partner / account / cost object
│   │   ├── T-code create / change / display / list / due
│   │   ├── BAPI + commit
│   │   ├── BAdI / user-exit / substitution / validation
│   │   ├── Output / IDoc / API / bank / tax engine
│   │   ├── FI/CO posting keys (BKPF, BSEG, COEP, COSP)
│   │   ├── Status that blocks the next hop
│   │   ├── Who (ERNAM / USNAM / AGR)
│   │   ├── Ticket if this leaf breaks
│   │   └── 6–60 month process change if this leaf is unused or wrong
```

**Granularity rule:** stop at **table-FIELD + legal value + next hop**, not at table name.

Wrong: “Collections uses BSID.”  
Right: “BSID-BUKRS=1710 · BSID-KUNNR · BSID-UMSKZ (special G/L) · BSID-ZFBDT (baseline) · BSID-ZTERM · BSID-ZLSPR (block) · hop → F150 / UDM_GENIL / dispute case.”

## 2. Census rule (never again)

| Forbidden | Required |
|---|---|
| SE16N List Output “500 hits” as a count | **Number of Entries** popup |
| Printer icon | Text **Number of Entries** |
| “Table is small” | Cap vs census labeled |
| Mix LIVE and CATALOG | Rank every number |

## 3. What was missing last time (must be first-class next time)

These are **processes**, not footnotes:

| Process | Why it was underspecified | Granular spine |
|---|---|---|
| **Collections** | OTC stopped at BSID count | Promise-to-pay, dunning (F150/T047*), collection worklist (UDM_*), contact, dispute link, write-off, agency |
| **Disputes** | Not opened | FSCM Dispute (UDM_DISPUTE), case type, reason, amounts, linked BSID, promise, write-off, root-cause to SD/MM |
| **Credit** | KNKK=0 noted, not mapped | FSCM UKM_* vs classic KNKK, check at VA01, blocked SO, VKM1, limit, risk class |
| **Deduction management** | Absent | Residual, reason codes (T053R), auto-write-off, cash disc |
| **Bank statement / lockbox** | Absent | FEBKO/FEBEP, FEBAN, interpretation algorithms |
| **Unbilled / cutoff** | Implied | LIKP GI vs VBRK, VF04 due list, period close |
| **Intercompany** | Types seen, not walked | IVA/IV, STOs, markup, elimination |
| **Output / e-invoice** | NAST 928 only | NACE, partner, eDocument, tax engine |
| **Product costing** | Not started | This ask — CK11N/CK40N/CKMLCP/ML |

## 4. Other analyses to add (backlog)

1. **Record-to-Report** — leading ledger, close calendar, GR/IR, FX, interco elim  
2. **Material Ledger / Actual Costing** — CKMLCP, CKM3, PUP vs S, not-distributed, not-allocated  
3. **Production execution** — order types, confirmations, scrap, WIP, variance  
4. **QM** — inspection lots, UD, QM in procurement (the TG10/PD cousin)  
5. **EWM / WM** — bins, HU, wave, GI delay vs billing  
6. **TM / LE** — freight, shipment cost to CO-PC  
7. **Treasury / Cash** — already started; link to collections  
8. **Tax / eDocument** — tax codes, reporting, India GST vs US/UK 1710  
9. **Master data quality** — incomplete KNVV, MVKE, MBEW, CACS  
10. **Authorization / SoD** — AGR_USERS vs create t-codes  
11. **Integration ops** — EDIDC error codes, partner profiles, retry  
12. **Support telemetry** — ticket forecast from unused F4 types + empty KNKK  

Each of the above must use this same mind-map, not a new essay style.

## 5. Product Costing is the next full run

See `docs/PRODUCT_COSTING_MINDMAP.md`. Live census: `data/runs/analysis_copc/`.
