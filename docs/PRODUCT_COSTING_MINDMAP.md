# Make and cost — technical appendix

**Consultant briefing (read first):** [CONSULTANT_BRIEFING.md](CONSULTANT_BRIEFING.md)

**In business language:** this plant already costs and manufactures. There are
thousands of standard cost estimates and years of actual costing. There are
74 costing recipes and only one overhead sheet. Pick one recipe for plant
1710. Do not cost the drop-ship material as if it were manufactured. Zero or
old standard prices make the margin on customer invoices a lie.

The rest of this file is the **object map** for a CO analyst.

---

# Product Costing (CO-PC) — granular mind map

**System:** APEX-2023 / client 100 / 1710 is the PTP-OTC company.  
**Standard:** `docs/ANALYSIS_GRANULARITY_STANDARD.md`  
**Live census:** `data/runs/analysis_copc/LIVE_COUNTS.json` — Number of Entries popups, not 500-row lists.  
Ranks: LIVE / INFERRED / CATALOG / ABSENT.

This is not “CK11N exists.” It is every leaf that makes a standard cost, an actual, a variance, and a P&L line.

## LIVE Number of Entries (verified popups)

| Table | Entries | Rank | Meaning |
|---|---:|---|---|
| TCK03 | **74** | LIVE | Costing variants — same F4-sprawl disease as TVAK 376 |
| TCK05 | **37** | LIVE | Valuation variants |
| TCK14 | **121** | LIVE | Partner / transfer-price cost components |
| TCK31 | **1** | LIVE | Costing sheet — almost unused |
| TCKH1 | **3,590** | LIVE | Cost component texts |
| KEKO | **3,472** | LIVE | Cost estimate headers |
| KEPH | **7,647** | LIVE | Cost component splits (COGS manufactured) |
| CKIS | **8,444** | LIVE | Itemization (BOM / activity / subcon) |
| CKHS | **3,241** | LIVE | Unit-costing headers |
| CKMLHD | **2,594** | LIVE | Material Ledger headers — **ML is on** |
| CKMLPP | **45,572** | LIVE | ML period quantities |
| CKMLCR | **85,131** | LIVE | ML period values / PUP |
| CKMLPR | **4,417** | LIVE | ML prices |
| T001K | **1,004** | LIVE | Valuation areas |
| MBEW | **3,071** | LIVE | Material valuation (S/V, STPRS, VERPR) |
| QBEW | **0** | LIVE | Project stock unused |
| EBEW | **89** | LIVE | Sales-order / MTO stock exists |
| AUFK | **2,950** | LIVE | Order master — factory is not sales-only |
| AFKO | **2,479** | LIVE | PP order headers |
| AFPO | **1,021** | LIVE | PP order items (popup 1,021; distinct from AFKO 2,479) |
| RESB | **10,666** | LIVE | Reservations / dependent requirements |
| AFRU | **1,838** | LIVE | Order confirmations |
| COSP | **26,953** | LIVE | CO object cost totals (external) |
| COEP | **38,507** | LIVE | CO line items — actuals are heavy |
| CSKB | **10,732** | LIVE | Cost elements — **not empty** (earlier CATALOG guess was wrong) |
| CSKS | **1,623** | LIVE | Cost center masters |
| TKKAA | **35** | LIVE | Results-analysis check table (WIP/RA config exists) |
| TKA01 | **591** | LIVE | Controlling areas — kitchen-sink landscape |
| TKA02 | **837** | LIVE | Company code ↔ CO area assignments |

**Thesis from the numbers (not from a catalog):** this is not a sandbox with a demo CK11N. There are **3,472 estimates**, **8,444 itemizations**, and **85,131 ML value periods**. Standard cost and actual costing both ran. 74 costing variants vs 1 costing sheet means **variant sprawl, almost no overhead sheet**. 2,594 ML headers vs 3,071 MBEW means **most valuated materials are in the ledger**. 45,572 / 2,594 ≈ **17.6 periods per material** — this system has been closing ML for years, not once.

**PP is live, not a cousin:** AUFK 2,950 / AFKO 2,479 / RESB 10,666 / AFRU 1,838. Confirmations exist, so variance and WIP tickets are real, not theoretical. **CO actuals are a factory:** COEP 38,507 / COSP 26,953 / CSKB 10,732 / CSKS 1,623. **Org sprawl matches TVAK:** TKA01 591 controlling areas, TKA02 837 assignments, T001K 1,004 valuation areas. 1710 is one plant in a kitchen-sink book. **QBEW=0 / EBEW=89:** no project stock; MTO exists. **TKKAA=35:** results-analysis / WIP config is present — KKAX is not shelfware.

```
PRODUCT COSTING
├── 0. ORG / LEDGER
│   ├── TKA01-KOKRS controlling area
│   ├── TKA02-BUKRS↔KOKRS (is 1710 assigned?)
│   ├── T001K-BWKEY / MLBWA / MLBWI  material ledger on/off
│   ├── T001W-WERKS plant → valuation area
│   ├── T001-BUKRS 1710 LIVE (PTP/OTC)
│   ├── T001-WAERS / TCURR FX for group cost
│   └── FISL / FINSC_LEDGER leading ledger (S/4)
│
├── 1. COSTING MASTER (what can be costed)
│   ├── MARA-MATNR / MTART / MEINS / SPART
│   ├── MARC-WERKS / LOSGR (costing lot) / SOBSL / FHORI
│   ├── MARC-NCOST (do not cost) / EKALR / HKMAT
│   ├── MBEW-BWKEY / BWTAR / VPRSV (S vs V) / STPRS / VERPR / PEINH
│   ├── MBEW-BKLAS valuation class → OBYC
│   ├── MBEW-HKMAT / MLAST / MLMAA ML indicators
│   ├── MBEWwait QBEW/EBEW (project / sales-order stock)
│   ├── MVKE-VKORG/VTWEG (OTC hop — 1,723 LIVE)
│   ├── STKO/STPO/MAST BOM
│   ├── PLKO/PLPO/MAPL routing / PLAS
│   ├── CRHD/CRCA work center + cost center + activity
│   ├── CSKS/CSKB/CSLA cost center / activity type / prices
│   ├── COST / COKL activity price
│   └── IF TG10 (PD third-party) — no in-house BOM → standard cost is purchase, not manufacture
│
├── 2. COST PLANNING CONFIG
│   ├── TCK03 costing variant (CK11N/CK40N)
│   │   ├── TCK03-KLVAR
│   │   ├── TCK03-BWVAR valuation variant → TCK05
│   │   ├── TCK03-KALKA costing type → TCK01
│   │   ├── TCK03-UEBER transfer control → TCK19
│   │   └── TCK03-BP_SCHEMA / date control TCK07
│   ├── TCK05 valuation variant
│   │   ├── strategy sequence: PO price / info record / planned price 1-3 / movement
│   │   ├── TCK05 + TCK06 (strategy)
│   │   └── TCK14 partner cost component
│   ├── TCKH1 / TCKH2 / TCKH3 cost component structure
│   ├── TCK31 / TCK32 costing sheet (overhead)
│   ├── KZZ2 / KZS2 overhead rates
│   ├── TCK40 / TCK41 quantity structure control
│   └── OKKN / OKK4 / OKTZ / OKKI  (SPRO views of the above)
│
├── 3. STANDARD COST ESTIMATE (transaction)
│   ├── CK11N single / CK40N costing run / CK13N display / CK24 mark / CK24 release
│   ├── KEKO header: MATNR WERKS KALNR KADKY BIDAT KALKA KLVAR
│   ├── KEPH cost component split (material, labor, OH, freight, …)
│   ├── CKIS itemization (BOM item, activity, subcontract, additive)
│   ├── CKHS / CKIT
│   ├── KANZ additive costs
│   ├── CK40N run: KALA / KALAMATCON1 / KALSTAT
│   ├── mark/release: MBEW-STPRS update + change doc
│   ├── BAPI_COSTESTIMATE_GETLIST / GETDETAIL / ITEMIZATION
│   ├── BAdI DATA_EXTENSION_CK / CK_KALAMATCON2_CI
│   └── user-exit COPCP* / SAPLCK10
│
├── 4. COST OBJECT (order / PP)
│   ├── T003O / T399X order type
│   ├── AUFK / AFKO / AFPO production order
│   ├── RESB components (hop from BOM + TG10 would not be here)
│   ├── AFRU confirmations (yield/scrap/activity)
│   ├── AUFM goods movements on order
│   ├── COBRB settlement rule
│   ├── TKO01 / TKO03 settlement profile
│   ├── KKS1 / KKS2 variance
│   ├── KKAX / KKAO WIP
│   ├── CO03 / COR3 display
│   ├── BAPI_PRODORD_GET_DETAIL / CREATE / RELEASE
│   └── BAdI WORKORDER_UPDATE / WORKORDER_GOODSMVT
│
├── 5. ACTUALS / MATERIAL LEDGER
│   ├── T001K-MLBWA ML active?
│   ├── CKMLHD header (KALNR, BWKEY, MATNR)
│   ├── CKMLPP period quantity
│   ├── CKMLCR period value / price
│   ├── CKMLPR / CKMLPRKEKO
│   ├── CKMLMV011 / CKMLMV003 process categories
│   ├── CKM3 / CKM3N material price analysis
│   ├── CKMLCP actual costing cockpit
│   ├── CKMH / CKMI close
│   ├── not-distributed / not-allocated (classic ticket)
│   ├── PUP vs S-price after close
│   └── BAdI CKML_UPDATE / CMFV
│
├── 6. FI / CO POSTING (the P&L)
│   ├── OBYC: BSX / GBB-VBR / PRD / AUM / KDM / PRY / PRV
│   ├── T030 / T030B
│   ├── COEP / COSP / COSS actual line / totals
│   ├── COBK document header
│   ├── CKMA / ML docs
│   ├── variance categories: input price, qty, resource-usage, remaining
│   ├── WIP to BS, variance to P&L
│   └── hop to R2R close calendar
│
├── 7. SPECIAL BUYS (hidden associations to PTP/OTC)
│   ├── Subcontract (T163-L) → CKIS subcontract item → 543/101
│   ├── Third-party TG10 → no production order → cost = purchase price only
│   ├── STO UB → transfer price / ML stock in transit
│   ├── Sales order stock (EBEW) / project (QBEW)
│   ├── Intercompany (TVAK IVA) → markup in TCK14
│   └── Freight / condition → cost component
│
├── 8. INTEGRATION
│   ├── IDoc LOIPRO / LOIROU / LOIBOM (PP master out)
│   ├── COPA / ACDOCA (S/4) value fields from KEPH
│   ├── inbound actuals from PP confirmations
│   └── CPI/BAPI for estimate get, not create, in analysis wing
│
└── 9. WHO / SUPPORT
    ├── KEKO-ERNAM / AUFK-ERNAM / CKMLCP user
    ├── BPINST vs SV3_* vs costing clerk
    └── tickets: see below
```

## T-code map (create / change / display / list / period)

| Leaf | Create | Change | Display | List / period |
|---|---|---|---|---|
| Costing variant | OKKN | OKKN | OKKN | TCK03 |
| Single estimate | CK11N | CK12N | CK13N | CK13N |
| Costing run | CK40N | CK40N | CK40N | CK40N |
| Mark / release | CK24 | CK24 | CK13N | |
| ML analysis | | | CKM3N | CKM3N |
| Actual costing | CKMLCP | CKMLCP | CKMLCP | CKMH |
| Prod order | CO01 | CO02 | CO03 | COOIS |
| Variance | KKS2 | | KKS1 | KKS1 |
| WIP | KKAX | | KKAY | KKAO |
| Material | MM01 | MM02 | MM03 | MBEW |

## BAPI / BAdI (do not execute create)

| Object | Role | Rank |
|---|---|---|
| BAPI_COSTESTIMATE_GETLIST | list estimates | CATALOG until SE37 |
| BAPI_COSTESTIMATE_ITEMIZATION | CKIS | CATALOG |
| BAPI_PRODORD_GET_DETAIL | order | CATALOG |
| BAPI_MATERIAL_GET_DETAIL | MBEW prices | CATALOG |
| BAPI_COSTCENTER_GETLIST | CSKS | CATALOG |
| DATA_EXTENSION_CK | estimate extend | CATALOG |
| WORKORDER_UPDATE | PP order | CATALOG |
| CKML_UPDATE | ML | CATALOG |

## Multi-hop (CO-PC × PTP × OTC)

1. **TG10 / PD** → no BOM/routing → CK11N purchase-only or error → MIGO 101 already failed → **do not cost as manufactured.**  
2. **MZ-RM-R200-*** → EKBE 101 LIVE → MBEW moving/standard exists → **this is the costing + GR material.**  
3. **VPRSV=S** without released KEKO → price 0 or old → PPV explosion at GR.  
4. **ML on (T001K)** + CKMLCP not closed → CKM3 not-distributed → period-end fire drill.  
5. **Activity price 0 (COST)** → labor component 0 → margin lie in VBRK F2.  
6. **OBYC PRD missing** → GR 101 dumps even if MIGO qty is right (second reason besides TG10).  
7. **1710 OTC F2** (5,982 bills) uses COGS from this stack — wrong STPRS = wrong margin.  
8. **KNKK=0** is credit (empty). **CSKB is not empty** — 10,732 cost elements LIVE. The empty-master ticket family is credit, not costing.

## Predicted support (CO-PC)

| Volume | Incident | First look |
|---|---|---|
| High | “Standard price is zero / old” | KEKO latest KADKY, CK24 release, MBEW-STPRS |
| High | “CK40N error log 10k materials” | MARC-NCOST, missing BOM, missing routing |
| High | “Not distributed in CKM3” | CKMLCP status, CKMLPP qty vs CKMLCR |
| Med | “Variance too high after confirm” | AFRU vs CKIS, activity price COST |
| Med | “Cannot settle order” | COBRB, TKO01, status AUFK |
| Med | GR dumps PRD/BSX | OBYC T030, MBEW-BKLAS |
| Low | Additive cost forgotten | KANZ |
| High if ML on | Period close blocked | CKMLCP cockpit |

## 6–60 month process (costing)

| Horizon | Change |
|---|---|
| 6 mo | Cost only MZ-RM- / in-house; never TG10 as manufactured. Release one 1710 standard via CK24. |
| 12 mo | Costing run CK40N for plant 1710; mark/release calendar with R2R close. |
| 18 mo | Activity prices (KSBnl / KP26) monthly. |
| 24 mo | If T001K ML=on: CKMLCP in close; if off: decide S vs V and stop mixing. |
| 36 mo | Cost component → COPA/ACDOCA mapped to F2 margin. |
| 48–60 mo | Freeze unused costing variants (TCK03 F4 sprawl, same disease as 376 TVAK). |

## What “done” means for this process

Number of Entries on the spine is LIVE (popups in `data/runs/analysis_copc/`). Variant *names* and the 1710 slice stay CATALOG until a filtered list is opened. The **counts** are no longer CATALOG.

**Corrected this session:** CSKB is not empty. QBEW is empty. EBEW is 89. AUFK is 2,950 — this is a manufacturing + costing system, not a sales-only book.
