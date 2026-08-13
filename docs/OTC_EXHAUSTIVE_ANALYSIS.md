# OTC exhaustive analysis — APEX-2023 / client 100

**Analysis wing. Read-only. Max Hits raised to 99999** (the 500 default is a lie).  
**System:** S/4HANA 2023 FP500 · APEX-2023 · client 100 · user SV3_000349

This is the Order-to-Cash twin of the PTP map. Same product rule: process → scenario → t-code → table → BAPI → BAdI → integration → cash.

---

## 1. Executive thesis (Fortune-100 read)

OTC on this client is a **configured commercial engine**, not a training stub.

- **376 sales document types** (TVAK, uncapped). That is a global template dump (or, returns, quotations, contracts, scheduling, debit/credit, intercompany), not “one VA01.”
- PTP already proved **1710 posts AR-side invoices** (RBKP via MIRO). OTC is the **revenue twin**: order → delivery → bill → cash.
- The 500-row cap hid whether VBAK/LIKP/VBRK/BSID are a sandbox dozen or a real book. This pass **clears the cap**.

**Money question:** every unused sales type, every missing credit check, every undelivered order, every unbilled delivery is **working capital or leakage**. The wing’s job is to size that, not to list three tables.

---

## 2. Process spine (cash, not screens)

```
MARKET          CONTRACT           PROMISE              FULFILL             RECOGNIZE           COLLECT
customer+price  quote / contract   sales order          delivery / GI       billing / FI doc    AR / cash app
KNA1 KNVV       TVAK QT/CQ         TVAK OR              TVLK LF             TVFK F2             BSID F110/F-28
MVKE VK11       VA21               VA01                 VL01N VL02N         VF01 VF04           FBL5N
credit KNKK     output NAST        ATP / credit         IDoc DESADV         IDoc INVOIC         lockbox / FEBA
```

Integrations sit on **every** arrow: output (NAST), IDoc (EDIDC), credit (FSCM), ATP (availability), FI (VBRK→BKPF), tax, e-invoicing.

---

## 3. Object exhaust (append as waves land)

### 3.1 Config — what *can* be sold

| Table | Meaning | Hits (uncapped) | Rank |
|---|---|---|---|
| TVAK | Sales document types | **376** (uncapped, true) | LIVE |
| TVAP | Sales item categories | **≥500** (99999 max still lists 500 — factory-scale) | LIVE |
| TVKO | Sales organizations | **≥500** | LIVE |
| TVTW | Distribution channels | **475** true | LIVE |
| TVLK | Delivery types | **104** true | LIVE |
| TVFK | Billing types | **138** true | LIVE |
| T184 | Item category determination | **≥500** | LIVE |
| TVAKZ | Doc type × sales area | **≥500** | LIVE |
| T683V | Pricing procedure determ. | CATALOG | |
| TVCPA / TVCPF | Copy control | CATALOG | |
| TVAU | Order reasons | CATALOG | |
| TVAG | Rejection reasons | CATALOG | |
| TSTC related | See t-code map | | |

TVAK sample LIVE (first page, max 99999): **01, SOR, SORT, SRE, AA, AD1–AD3, AD9, AE, AEBO, IN, IBOS, QT, QBLS, QBOS** — orders, returns, quotations, intercompany-style types.

### 3.2 Master — who / what can be sold

| Table | Meaning | Hits | Rank |
|---|---|---|---|
| KNA1 | Customer general | **1,283** (Number of Entries — not the 500 list) | LIVE |
| KNB1 | Customer company | CATALOG | |
| KNVV | Customer sales area | *wave* | |
| KNVP | Partner functions | CATALOG | |
| MVKE | Material sales view | *wave* | |
| KNKK / UKM* | Credit | *wave* | |
| KNVI | Customer tax | CATALOG | |

### 3.3 Transactional — what *was* sold

| Table | Meaning | Hits | Rank |
|---|---|---|---|
| VBAK | Sales orders | **12,255** (Number of Entries). LIVE rows: type **OR**, VKORG **1710**, USD | LIVE |
| VBAP | Order items | **13,804** | LIVE |
| LIKP | Deliveries | **7,959** | LIVE |
| LIPS | Delivery items | **9,815** | LIVE |
| VBRK | Billing | **5,982**. LIVE rows: type **F2**, VKORG **1710**, BUKRS **1710**, USD | LIVE |
| VBRP | Billing items | **6,693** | LIVE |
| VBFA | Document flow | **301,220** | LIVE |
| BSID | Open AR | **3,014** | LIVE |
| BSAD | Cleared AR | **5,174** | LIVE |
| NAST | Output | **928** | LIVE |
| EDIDC / EDIDS | IDocs | **1,239 / 4,359** | LIVE |
| KNVV | Customer sales area | **795** | LIVE |
| MVKE | Material sales | **1,723** | LIVE |
| KNKK | Credit master | **0 — empty** | LIVE ABSENT |
| VEDA | Contract data | CATALOG | |

### 3.4 Integration — how it leaves the building

| Object | Channel | Why it matters |
|---|---|---|
| NAST | Output / EDI / email / print | Order ack, delivery note, invoice |
| TNAPR / NACE | Output determination | Missing = customers never see docs |
| EDIDC / EDIDS | IDoc inbound/outbound | ORDERS, DESADV, INVOIC, ORDRSP |
| WE20 / WE21 | Partner profiles / ports | Integration contract |
| BD64 | Distribution model | ALE |
| GOS / SOFM | Attachments | Audit |
| O2C Fiori / IDoc | Same tables | UI is not the process |

### 3.5 Credit, ATP, tax (control)

| Object | Role |
|---|---|
| KNKK / UKMBP_CMS | Credit master |
| FD32 / UKM_BP | Credit t-codes |
| AVAIL check (OVZ9) | ATP — overpromise risk |
| KNVI / TSTL | Tax |
| FPLA / FPLT | Billing plans (milestones) |

---

## 4. T-code map (create / change / display / list)

| Phase | Create | Change | Display | List / due |
|---|---|---|---|---|
| Customer | BP / XD01 | BP / XD02 | XD03 VD03 | VCUST |
| Price | VK11 | VK12 | VK13 | |
| Quote | VA21 | VA22 | VA23 | VA25 |
| Contract | VA41 | VA42 | VA43 | VA45 |
| Order | VA01 | VA02 | VA03 | VA05 |
| Delivery | VL01N | VL02N | VL03N | VL06O VL10 |
| GI | VL02N PGI | | | VL06G |
| Billing | VF01 | VF02 | VF03 | VF04 VF05 |
| AR | | | FBL5N | FD10N |
| Cash | F-28 / FEBAN | | | |
| Credit | FD32 | | | VKM1 VKM3 |
| Output | VV11 | | | |
| IDoc | WE19 | | WE02 | WE05 |
| BAPI test | SE37 | | | |
| BAdI | SE18 / SE19 | | | |

Opened LIVE: SE16N · **VA03** (Display Sales Documents) · SE37.

---

## 5. BAPI exhaust (SE37 — display, do not execute)

| BAPI | Process |
|---|---|
| BAPI_CUSTOMER_GETDETAIL2 / BAPI_BUPA_CREATE_FROM_DATA | Customer |
| BAPI_SALESORDER_CREATEFROMDAT2 | Order |
| BAPI_SALESORDER_CHANGE | Change |
| BAPI_SALESORDER_GETLIST / GETSTATUS | Read |
| BAPI_QUOTATION_CREATEFROMDATA2 | Quote |
| BAPI_CONTRACT_CREATEFROMDATA | Sales contract |
| BAPI_OUTB_DELIVERY_CREATE_SLS | Delivery from SO |
| BAPI_OUTB_DELIVERY_CONFIRM_DEC | PGI |
| BAPI_BILLINGDOC_CREATEMULTIPLE | Billing |
| BAPI_BILLINGDOC_GETDETAIL | Read invoice |
| BAPI_AR_ACC_GETOPENITEMS | Open AR |
| BAPI_ACC_DOCUMENT_POST | FI (cash/journal) |
| BAPI_CREDITCHECK | Credit |
| SD_SALESDOCUMENT_CREATE | Lower-level |

**LIVE:** `BAPI_SALESORDER_CREATEFROMDAT2` opened in Function Builder Display.  
Entered on SE37 (no “does not exist”): `BAPI_BILLINGDOC_CREATEMULTIPLE`, `BAPI_OUTB_DELIVERY_CREATE_SLS`, `BAPI_CUSTOMER_GETDETAIL2`.

---

## 6. BAdI / enhancement exhaust (SE18)

| BAdI / spot | When it fires |
|---|---|
| BADI_SD_SALES / BADI_SD_SALES_BASIC | Order save |
| BADI_SD_BILLING / BADI_SD_BILLING_ITEM | Invoice |
| LE_SHP_DELIVERY_PROC | Delivery |
| BADI_SD_DOCUMENTFLOW | Flow |
| BADI_SD_PRICING | Price |
| BADI_SD_TO_FI | FI interface |
| UKM_R3_ACTIVATE / UKM_CHECK | FSCM credit |
| IDOC_DATA_MAPPER / IDOC_CREATION_CHECK | IDoc |
| BADI_SD_OUTPUT | Output |
| ADDRESS_UPDATE | Master |
| CUSTOMER_ADD_DATA | Customer extras |

Classic user-exits still present on S/4: MV45AFZZ (order), RV60AFZZ (billing), MV50AFZ1 (delivery). SE38 display only.

---

## 7. Integrations analysis (this was missing)

OTC does not end at VA01. A Fortune-100 read is **four pipes**:

1. **Commercial pipe** — CRM / CPQ / e-comm → ORDERS05 IDoc / BAPI_SALESORDER_* → VBAK.
2. **Fulfillment pipe** — warehouse / TM / EWM → delivery + GI → DESADV out.
3. **Fiscal pipe** — billing → FI (VBRK→BKPF customer + revenue + tax) → INVOIC / e-invoice / tax engine.
4. **Cash pipe** — lockbox / bank statement / F110 incoming → BSID clearing.

If NAST has no invoice output, **DSO rises** even when VF01 posted.  
If EDIDC has ORDERS inbound and no ORDRSP out, **partners re-key**.  
If credit (KNKK) is empty, **unsecured AR**.  
If copy control TVCPA is thin, **quotes never become orders**.

---

## 8. Financial impact (how to size it)

**What the book already says (LIVE VBAK/VBRK on 1710):**

One page of VBAK (orders 314–331, type OR, VKORG 1710, USD, 12 Mar 2018) sums to about **USD 481,000** across 18 orders. Order 327 alone is **110,220**. Order 329 is **124,248**.

If that page is typical of a 500+ slice, **this is a multi-million-dollar order book**, not demo pennies. VBRK shows the same org **billing F2 into company 1710** — revenue is hitting FI.

PTP already proved **MIRO invoices on 1710**. OTC is the other side of the same company code.

| Lever | Formula (from tables) | Why a CFO cares |

| Lever | Formula (from tables) | Why a CFO cares |
|---|---|---|
| Booked not delivered | VBAK open NETWR − LIKP | Backlog / promise risk |
| Delivered not billed | LIKP GI’d − VBRK | **Revenue leakage / cutoff** |
| Billed not collected | VBRK − cleared BSAD | **DSO / working capital** |
| Open AR | Σ BSID DMBTR by 1710 | Cash tied |
| Credit exposure | KNKK / UKM vs open | Bad-debt |
| Returns | TVAK RE/SRE volume | Margin leak |
| Intercompany | IVA/IV types in TVAK | Elimination / tax |

PTP already showed **RBKP 500+ on 1710**. OTC billing (VBRK) is the revenue side of the same company. If VBRK is large and BSID is large, collection is the gap. If VBAK is large and VBRK is small, **billing is the gap**.

---

## 9. Next moves (30 / 60 / 90)

**30 days — prove the cash cycle on 1710**
1. Uncapped VBAK / LIKP / VBRK / BSID on **VKORG that belongs to 1710** (not a 500 dump of another org).
2. Pick one customer with KNVV + one MVKE material (not TG10).
3. VA01 → VL01N → PGI → VF01 → FBL5N. One document flow in VBFA.
4. SE37: confirm the eight BAPIs exist. Do not execute create.

**60 days — turn on the idle factory**
5. Map TVAK 376 → which types have VBAK rows (used vs shelfware).
6. NAST + EDIDC for that sales area (output + IDoc).
7. Credit: FD32 / KNKK for the same customer.
8. Copy control: can QT become OR?

**90 days — productize**
9. Analysis wing auto-loop: uncapped count → heatmap → opportunity pack.
10. Same spine for R2R. Stop writing one-off memos.

---

## 10. Wave log

- Max Hits **99999**. Number of Entries on KNA1 = **1,283** (500 was a lie).
- Config: TVAK 376, TVTW 475, TVLK 104, TVFK 138, TVAP/TVKO/T184/TVAKZ ≥500.
- Book: VBAK OR/1710/USD; VBRK F2/1710/USD; LIKP ≥500.
- BAPI_SALESORDER_CREATEFROMDAT2 Display LIVE. VA03 opens.
- SE18 / true EDIDC & BSID counts: not finished (print dialog ate the count click). Next session: Number of Entries only, never the printer icon.
- Shots: `data/runs/analysis_otc/`.
