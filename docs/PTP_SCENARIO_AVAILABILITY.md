# PTP scenario availability — APEX-2023 / client 100

**System:** S/4HANA 2023 FP500, APEX-2023, client 100  
**User that looked:** SV3_000349  
**Mode:** Analysis wing (read). SAP GUI is **logged off** for this write-up.
Evidence is from live SE16N / SE37 / SE38 / ME2xN / MIGO sessions already run
on this box (`docs/PTP_E2E_WALKTHROUGH.md`, `data/runs/live_ptp_e2e/`,
`data/runs/live_ptp_create/`, EKKO 1-hit on `3200000039`).

This is not the 10 Co-pilot YAML files. Those are *our* scripts. This is
**what the client can actually run**, and **which objects turn each path on**.

---

## How to read this

A PTP **scenario** is a complete path a buyer can take, not a single t-code.

```
SOURCE          DEMAND           ORDER              FULFILL           SETTLE
vendor+material → PR / source   → PO / contract    → GR / service    → IR → AP → pay
info record       list / ME59N    STO / 3rd party    MIGO / SES        MIRO / F110
```

Each scenario below lists **every object class** that must line up:

| Class | Where we look |
|---|---|
| Org | T001, T001K, T001W, T024E, T024, T161W |
| Master | LFA1, LFB1, LFM1, LFBK, MARA, MARC, MARD, MBEW, CSKS |
| Config | T161 (doc types), T163 (item cat), T163K (acct assgn), T163A (allowed combo), T160, T169*, T16F* (release), T460A (special procurement) |
| Conditions | EINA/EINE, EORD, KONP, T683 |
| Transaction | EBAN, EKKO, EKPO, EKET, EKBE, MKPF/MSEG, RBKP/RSEG, BSIK, REGUH |
| Interface | BAPI_PR_CREATE, BAPI_PO_CREATE1, BAPI_GOODSMVT_CREATE, BAPI_INCOMINGINVOICE_CREATE |
| Extensibility | SE18 BAdI `ME_PROCESS_PO_CUST`, `MB_DOCUMENT_BADI`, `MRM_HEADER_CHECK` |
| Program | SE38 RM06ELLB (subcon stock), RM06BB30 (ME59N), RM08MMAT |
| Batch | SM35 / SM37 for RFCs and payment proposals |

---

## What is LIVE on this client (counts are SE16N “Number of Hits”)

| Object | Table / t-code | Hits / result | Rank |
|---|---|---|---|
| Company codes | T001 | 500. PTP uses **1710** | LIVE |
| Plants | T001W | 500. **1710**, 0001, 1000, 1010, 1100, 1200 | LIVE |
| Purchasing orgs | T024E | 500. **1710** on real POs | LIVE |
| Purchasing group | T024 / EKKO.EKGRP | **002** on posted POs; **001** on failed ME59N | LIVE |
| Vendors | LFA1 | 500. **USSU-VSF01**, C6-100, USSU-VSF06, 17300001 | LIVE |
| Plant materials | MARC | 500. TG11–TG21 on **0001**; TG10 used on **1710** via EBAN | LIVE |
| PRs | EBAN | 500. Type **NB**, plant 1710, TG10/TG11/TG13, tracking 001 | LIVE |
| POs | EKKO | 500. CoCd 1710, types **NB** and **ZNB**, POrg 1710, PGrp 002, USD | LIVE |
| STO | ME23N | **100011** Stock Transp. Order (Pranali) | LIVE |
| Held PO | EKKO | **3200000039** NB, USSU-VSF01, 1710/002, created SV3_000349 | LIVE |
| Posted PO | ME21N / EKKO | **4500002260**, **4500002262** (K / 1710-10 / G/L 610000) | LIVE |
| PR created | ME53N / EBAN | **10014063** K / TG10 / 1710 / 171B | LIVE |
| Cost center | CSKS | **1710-10** (used on K items) | LIVE |
| BAPI PO | SE37 BAPI_PO_CREATE1 | Module **exists** (not executed) | LIVE |
| SE38 | RM06ELLB | Subcontracting-stock monitor **ran** | LIVE |
| Roles | AGR_USERS | 500. Z:COMP_* / Z:SING_* | LIVE |
| Create screens | ME51N, ME21N, MIGO | **Open** | LIVE |
| Display screens | ME23N, ME53N | **Open** | LIVE |
| GR post | MIGO 101 on TG10/1710/171B | **Blocked** — deficit PU GR qty (PD third-party) | ABSENT (this material path) |
| IR / pay | MIRO, F110, BSIK, RBKP | **Not opened to a posted result** | CATALOG |

T161 / T163 / T163K were opened live on 2026-08-13 (this session).
EINA / EORD / T16FS / T169 still **CATALOG**.

---

## LIVE config opened this session (SE16N)

### T161 — Purchasing document types — **139 hits**

BSTYP (Cat) is the process family. Types we paged through:

| Cat | Process family | Types seen (not exhaustive of 139) |
|---|---|---|
| **A** | RFQ / quotation | AB, AN, AR, CPL, MO, RAC, RAN, SA, VN, ZKMA, ZNB, ZRFQ |
| **B** | Purchase requisition | NB, NBS, FO, VO (SRV), RV, PNB, RNB, YNB, ZNB, ZSTO, ZSUB, ZSER, DEMO, … |
| **C** | Central / hierarchy contract | MK, WK, HRMK, HRWK, HSMK, HSWK |
| **F** | Purchase order | **NB**, **UB** (STO), **FO** (framework/service), SUB/EUB (transport), NB2, VB, VO, VU, **ZNB**, YNB, ZSRV, ZP01, … |
| **K** | Contract (outline) | MK, WK, CMK, CWK, TS, ZMK, ZWK, ZTMK, ZTWK |
| **L** | Scheduling agreement | LP, LPA, LPXE, LPXI, **LU** (stock-transport SA), ZLP, ZLPA |
| **N / O / R** | Confirmations / related | RE, RQ, RSI, ZRQ |

Screenshots: `data/runs/analysis_ptp/t161_sel.png` … `t161_p8.png`.

This is the official “how many PTP order scenarios are configured”: **139 document types**, not 10 YAML files.

### T163 — Item categories — **15 hits** (complete on one screen)

| I | External | Scenario it turns on |
|---|---|---|
| 0 | (blank) | **Standard** stock/consumable line |
| 1 | B | **Limit** |
| 2 | K | **Consignment** |
| 3 | L | **Subcontracting** |
| 4 | M | Material unknown |
| 5 | S | **Third-party** (TG10 path) |
| 6 | T | Text |
| 7 | U | **Stock transfer** |
| 8 | W | Material group |
| 9 | D | **Service** |
| A | E | Enhanced limits |
| C | C | Stock provided by customer |
| P | P | Returnable transport packaging |
| R | R | Rental text |
| V | V | Supplier-owned |

Screenshot: `data/runs/analysis_ptp/t163_sel.png`.

### T163K — Account assignment categories — **23 hits**

Visible on first page (A–T): **A** Asset, **B** MTS/sales ord, **C** Sales order, **D** Indiv.cust/project, **E** Ind.cust+KD-CO, **F** Order, **G** MTS/project, **H** Nonstock sales, **I** Returns, **J** TM cost dist., **K** Cost center (used), **M** Ind.cust w/o KD-CO, **N** Network, **P** Project, **Q** Project MTO, **R** Service order, **S** Third-party project, **T** All new aux.

Screenshot: `data/runs/analysis_ptp/t163k_grid.png`.

**Configured scenario space** ≈ 139 doc types × 15 item cats × 23 acct cats, constrained by T163A (not opened). Used-on-1710 is a thin slice (NB + K + TG10/S).

## Process map — scenarios available on this system

### Phase 1 — Source (can we buy from someone, something, somewhere)

#### S1. Vendor is purchasable in org 1710
**Status: AVAILABLE (LIVE)**

Process: vendor general data → company code → purchasing org.

| Parameter | Object | This client |
|---|---|---|
| Vendor | LFA1-LIFNR | USSU-VSF01 (and 499 others) |
| Company view | LFB1-BUKRS | Inferred present — ME21N auto-fills 1710 |
| Purchasing view | LFM1-EKORG | Inferred present — 1710 accepted; **1000 rejected** for USSU-VSF01 |
| Purch. group | T024 / EKKO-EKGRP | **002** works. **001** + vendor 17300001 failed ME59N |
| Currency | LFM1 / EKKO-WAERS | USD |
| Payment method / bank | LFB1-ZWELS, LFBK | Not read — blocks S10, not S1 |

**Association:** same vendor + wrong POrg (1000) = scenario disappears. Org
assignment is the switch, not the vendor number alone.

#### S2. Material is purchasable at plant 1710
**Status: PARTIAL (LIVE + BLOCK)**

| Parameter | Object | This client |
|---|---|---|
| Material | MARA-MATNR | TG10, TG11, TG13 |
| Plant view | MARC | TG10 used on 1710 PRs; sample MARC dump was plant 0001 |
| Valuation | MBEW | Price 10 USD used successfully |
| Material type / item | MARA-MTART, TG10 text | **PD, Third Party** |
| Special procurement | MARC-SOBSL / T460A | INFERRED third-party (PD) |
| Storage loc | MARD / 171B | Exists enough to type; **not GR-stock** for TG10 |

**Association:** TG10 unlocks **third-party PO**, locks **standard 101 GR**.
A stock PTP cycle needs a different material (or SOBSL blank + MARD unrestricted).

#### S3. Info record / source list
**Status: UNKNOWN (EINA/EORD still CATALOG)**

| Parameter | Object | Why it matters |
|---|---|---|
| Info record | EINA + EINE | Price default, planned delivery, GR-based IV default |
| Source list | EORD | ME59N / automatic source |
| Quota | EQUK/EQUP | Split source |

We never opened EINA/EORD. ME21N still created a PO — info record is **not**
mandatory for manual NB. It **is** mandatory for a clean ME59N auto-PO.

---

### Phase 2 — Demand

#### S4. Standard purchase requisition (NB)
**Status: AVAILABLE (LIVE)**

| Parameter | Object | This client |
|---|---|---|
| PR type | T161 (BSTYP=B) / EBAN-BSART | **NB** (500 PRs) |
| Plant / qty / UoM | EBAN-WERKS/MENGE/MEINS | 1710 / 10 / PC |
| Material | EBAN-MATNR | TG10, TG11, TG13 |
| Acct assignment | EBAN-KNTTP | **K** on 10014063 |
| Cost center | EBAN-KOSTL / CSKS | 1710-10 |
| Tracking | EBAN-BEDNR | 001 |
| T-code | ME51N / ME53N | Open |
| BAPI | BAPI_PR_CREATE | CATALOG (not opened) |

#### S5. Auto-convert PR → PO (ME59N)
**Status: BLOCKED (LIVE fail)**

Tried vendor **17300001** / POrg 1710 / PGrp **001** → “Requisition could not
be converted”.

Missing / mismatched parameters (any one kills it):

- EBAN-FLIEF / LIFNR assigned vendor
- EBAN-EKGRP must match a group that vendor+org allow (**002**, not 001)
- EORD fixed source (not read)
- T160 / T161A link PR type → PO type
- Release (EBAN-FRGKZ) if T16FS is active

**Association:** S4 can exist while S5 is dead. Same PR table, extra keys.

---

### Phase 3 — Order

#### S6. Standard PO (NB, stock-like item)
**Status: AVAILABLE to create, GR later blocked for TG10 (LIVE)**

| Parameter | Object | This client |
|---|---|---|
| PO type | T161 / EKKO-BSART | **NB** (majority), also **ZNB** |
| Vendor | EKKO-LIFNR | USSU-VSF01 |
| POrg / PGrp / CoCd | EKKO EKORG/EKGRP/BUKRS | **1710 / 002 / 1710** |
| Currency / date | EKKO-WAERS / BEDAT | USD / 08/13/2026 |
| Item category | EKPO-PSTYP / T163 | Blank on our NB (standard) |
| Plant | EKPO-WERKS | 1710 |
| T-code | ME21N / ME23N | Open |
| BAPI | BAPI_PO_CREATE1 | LIVE exists |
| Custom type | EKKO-BSART=ZNB | INFERRED T161-ZNB configured |

Posted examples: 4500000002 (seed), 4500002260, 4500002262.

#### S7. Account-assigned PO (K — cost center)
**Status: AVAILABLE (LIVE)**

| Parameter | Object | This client |
|---|---|---|
| KNTTP | T163K / EKPO-KNTTP | **K** |
| Allowed combo | T163A (PSTYP + KNTTP) | INFERRED allowed (item posted) |
| Cost center | EKKN-KOSTL / CSKS | **1710-10** |
| G/L | EKKN-SAKTO / SKB1 | **610000** worked; **51600000** demanded extra cost object |
| GR-Based IV | EKPO-WEBRE | Required on some items (held 3200000039) |

**Association:** G/L 51600000 is a **cost-relevant** account (needs CO object
on every assignment line). Wrong G/L turns S7 into a hard error even when
K and CSKS are right.

#### S8. Third-party / PD (drop-ship)
**Status: CONFIGURED (T163-5/S) + USED (TG10) — LIVE**

TG10 short text: `Trad.Good 10,PD,Third Party`.

| Parameter | Object | Effect |
|---|---|---|
| Item / material | EKPO / MARA | PD third-party |
| Item category | T163 typically **S** (third-party) | Not confirmed in T163 yet |
| GR | MIGO 101 | **Fails** — no PU GR stock |
| Settlement | Often IR w/o GR, or SD billing | Not walked |

Do not treat TG10 as the happy-path stock PTP material.

#### S9. Stock transport order
**Status: AVAILABLE (LIVE display)**

ME23N showed **STO 100011**. That means:

| Parameter | Object | Rank |
|---|---|---|
| Doc type | T161 UB / NB+STO | INFERRED (number 100011 ≠ 45…) |
| Supplying + receiving plant | EKKO-RESWK, EKPO-WERKS / T001W | Both plants exist (500 plants) |
| Stock in transit | MARC, T161W | CATALOG |

#### S10. Subcontracting
**Status: CONFIGURED (T163-3/L LIVE) + SE38 RM06ELLB. Docs not proven**

SE38 **RM06ELLB** (subcontracting stock) executed. That report exists only
if the subcontracting component is in the system. We have **not** opened
EKPO-PSTYP=3 or T163-L.

| Parameter | Object |
|---|---|
| Item category L | T163, EKPO-PSTYP=3 |
| BOM / components | RESB, EKPO |
| Movement 541/101 | MSEG, T156 |

#### S11. Outline agreement / scheduling / RFQ
**Status: CONFIGURED (T161 LIVE) — transactional use not proven**

T161 has **A** RFQ (AN, AB, ZRFQ…), **K** contract (MK, WK, ZWK…), **L** SA
(LP, LPA, LU stock-transport SA). Next: EKKO filtered BSTYP=A/K/L (1-hit
per type), t-codes ME41 / ME31K / ME31L.

#### S12. Held / parked PO
**Status: AVAILABLE (LIVE)**

EKKO **3200000039**, category F, type NB, MEMORY-style 32… number.
This is a **park**, not a 45… post. Same enablement as S6 plus Hold.

---

### Phase 4 — Fulfill

#### S13. Goods receipt 101 against PO
**Status: SCREEN OPEN, POST BLOCKED for TG10 (LIVE)**

| Parameter | Object | This client |
|---|---|---|
| T-code | MIGO | Opens (GR Purchase Order) |
| Movement | T156 / 101 | Loaded |
| PO history | EKBE VGABE=1 | Not created for 4500002260 |
| SLoc stock | MARD | 171B not valid for PU GR on TG10 |
| BAPI | BAPI_GOODSMVT_CREATE | CATALOG |

To make S13 available for a **stock** cycle: material with inventory
management + unrestricted MARD + item category blank + (usually) WEBRE.

---

### Phase 5 — Settle

#### S14. Invoice verification (MIRO)
**Status: NOT COMPLETED (CATALOG)**

Depends on: T169*, EKPO-WEBRE, RBKP/RSEG, tax, company 1710.
For GR-based IV, **S13 must exist**. For non-GR-based, WEBRE blank.

BAPI: `BAPI_INCOMINGINVOICE_CREATE`.

#### S15. Vendor open item + F110 payment
**Status: NOT READ (CATALOG)**

Objects: BSIK, LFB1-ZWELS/ZAHLS, LFBK, T042/T042E/T042I/T042Z, PAYR.
Our 10 YAML “ptp_10” is this pack — **not live on 1710**.

---

## Cross-scenario switchboard (the product insight)

These are the **parameters that turn scenarios on or off**. Same operator,
different field.

| Switch | Field | If set this way | Scenario that appears | Scenario that dies |
|---|---|---|---|---|
| Purchasing org | LFM1 / EKKO-EKORG | 1710 | S1, S6 | 1000 + USSU-VSF01 |
| Purch. group | EKGRP | 002 | S6, S5 | 001 + 17300001 ME59N |
| Material nature | MARA / TG10 PD | Third-party | S8 | S13 stock GR |
| Acct assignment | KNTTP | blank | stock PO | needs MARD |
| Acct assignment | KNTTP=K | + CSKS + G/L | S7 consumable | stock GR optional |
| G/L | EKKN-SAKTO | 610000 | posts | 51600000 needs extra CO |
| GR-based IV | EKPO-WEBRE | X | S14 after GR | save blocked if empty when required |
| Doc type | BSART | NB | standard PO | ZNB = custom (same path) |
| Doc type / number | 100011 | STO | S9 | not a 45… NB |
| Hold | MEMORY / 32… | held | S12 | not a posted 45… |
| Vendor | LIFNR | USSU-VSF01 | works | 17300001 failed convert |

---

## Interfaces that exist vs not proven

| Object | Rank | Notes |
|---|---|---|
| BAPI_PO_CREATE1 | LIVE | SE37 display |
| BAPI_PR_CREATE | CATALOG | Same builder, not opened |
| BAPI_GOODSMVT_CREATE | CATALOG | |
| BAPI_INCOMINGINVOICE_CREATE | CATALOG | |
| BAPI_PO_GETDETAIL1 | CATALOG | |
| SE18 ME_PROCESS_PO_CUST | CATALOG | next look |
| SM35 | CATALOG | batch input / IDoc monitors |
| SE38 RM06ELLB | LIVE | subcontracting monitor |
| SE38 RM06BB30 | CATALOG | ME59N program |

---

## What to open next (when SAP is back)

Analysis wing first session, in this order — display / SE16N only:

1. **T161** — all BSART (NB, ZNB, UB, WK, MK, FO, …) → official type list  
2. **T163** + **T163K** + **T163A** — item cat × acct assgn matrix  
3. **EKKO** group by BSART, BSTYP (1-hit per type, not 500-dump)  
4. **EKPO** group by PSTYP, KNTTP, WEBRE  
5. **EINA/EINE**, **EORD** — source determination  
6. **T16FS / T16FG** — release strategies  
7. **EKBE** VGABE=1 vs 2 — real GR/IR volume  
8. **RBKP** — any MIRO at all  
9. **SE18** implementation list for MM BAdIs  
10. **SM35 / SM37** — whether PTP is also run by batch

That list is the **analysis product loop**, not a one-off.

---

## Co-pilot YAML vs system reality

| Our script | System |
|---|---|
| ptp_01…10 (vendor 100001 / CoCd 1000 / Vista mock) | **Different landscape** |
| APEX live org | **1710 / 002 / USSU-VSF01 / TG10** |
| Mock “complete P2P chain” | Live chain **stops at GR** for TG10 |

Do not report “10 PTP scenarios configured” because we have 10 YAML files.
On this client the **configured-and-used** set is:

1. Vendor + org 1710 purchasing  
2. Material TG1x at 1710 (third-party flavor)  
3. Standard NB PR  
4. Standard NB PO  
5. Custom ZNB PO (type exists)  
6. Account-assigned K PO  
7. Held PO (32…)  
8. STO 100011  
9. Subcontracting **program** present  
10. ME59N **configured enough to run, conversion failed**  
11. MIGO **configured, 101 blocked for TG10**  
12. MIRO / F110 **not proven**

That is the inventory. Adjacent unlocks: a **stock material + MARD** turns on
GR→IR; **EORD + EKGRP 002** turns on ME59N; **LFBK + T042** turns on pay.
