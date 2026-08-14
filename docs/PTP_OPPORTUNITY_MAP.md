# Buy and pay — technical appendix

**Consultant briefing (read first):** [CONSULTANT_BRIEFING.md](CONSULTANT_BRIEFING.md)

**In business language:** company 1710 already buys, receives, and invoices
vendors. Do not implement purchasing. Stop using TG10 as warehouse stock.
Use buyer group 002. Put the source list on plant 1710.

The rest of this file is the **object map** for an MM analyst. It is not the
document you take to a process owner.

---

# PTP opportunity map — APEX-2023 / client 100

**Analysis wing product cut.** Read-only. Evidence ranks: LIVE / INFERRED / CATALOG / ABSENT.

This is not “we opened three tables.” It is the **process × scenario × transaction × object × gap** map this client can grow from. New SE16N hits append here; they do not replace the graph.

---

## 1. Thesis

This sandbox is not an empty training client. It is a **fully built S/4 purchasing factory** that has already posted **goods receipts and invoices on company 1710**.

What we got wrong earlier: we treated “our TG10 PO would not GR” as “PTP is incomplete.” EKBE and RBKP say the opposite.

| Fact | LIVE |
|---|---|
| Configured order types | T161 **139** |
| Item categories | T163 **15** |
| Acct assignment cats | T163K **23** |
| Legal item×acct combos | T163A **94** (standard item 0 allows A C D E F H I J K M N P Q R T U X Z) |
| Release strategies | T16FS **98** (IT/Fuels, Infra, PR Release, Infra/GN02) |
| Release groups | T16FG **3** |
| Purchasing groups | T024 **462** |
| Info records | EINA **500** (hit cap) |
| Source lists | EORD **173** — plants MOH1, SAO1, LC01, T501, DPKO… **not 1710 on page 1** |
| Special procurement | T460A **500** (hit cap) |
| IV transaction control | T169 **47** (MIRO, MIR7, MR11, MR8M, …) |
| PO history | EKBE **500** — **mvt 101**, plant **1710**, material **MZ-RM-R200-***, PO 4500000767…, 2020 |
| Invoice headers | RBKP **500** — **MIRO**, CoCd **1710**, vendor **USSU-VSF0x**, PO 4500000001…, 2017 |

Thesis: **do not configure PTP. Re-enter the path that already posted.** The white space is unused T161 types, unused KNTTP, source list not on 1710, and TG10-as-stock (wrong).

---

## 2. How a McKinsey reader should use this

| Question | Answer lives in |
|---|---|
| What can this company buy? | T161 families × T163 item cats |
| What can they charge to? | T163K |
| What do they actually buy? | EKKO/EKPO/EBAN on 1710 |
| Which t-code opens that path? | Transaction map below |
| What is one field away? | Switchboard |
| What is revenue / cycle-time / control value? | Opportunity pack (section 7) |

---

## 3. Process spine (end to end)

```
PLAN          SOURCE              DEMAND           COMMIT              FULFILL            SETTLE              PAY
forecast      vendor+info rec     PR / RFQ         PO / contract / SA  GR / SES / inbound IR / ERS / credit   F110
T438*         LFA1 LFM1 EINA      EBAN ME51N       EKKO ME21N ME31K    MIGO ML81N         MIRO MR8M           FBZP
              EORD T16FS          ME41 ME59N       ME31L ME58          VL31N              RBKP BSIK           REGUH
```

Every box is a **scenario family**. Each family has: config table, master, transactional table, create t-code, display t-code, list t-code, BAPI, BAdI, SE38 report.

---

## 4. Configured scenario factory (LIVE)

Opened on this client:

| Layer | Table | Hits | What it means |
|---|---|---|---|
| Doc types | T161 | **139** | RFQ, PR, PO, central contract, contract, SA, confirmations |
| Item cats | T163 | **15** | Standard, limit, consignment, subcontract, 3rd-party, STO, service, … |
| Acct assgn | T163K | **23** | K cost center through asset, order, project, SO, network |
| Allowed combo | T163A | **94** | Item 0 (standard) allows A C D E F H I J K M N P Q R T U X Z |
| Release strat | T16FS | **98** | IT/Fuels, Infra, PR Release, Infra/GN02 multi-step |
| Release groups | T16FG | **3** | |
| Special proc. | T460A | **500** (cap) | Plant special procurement keys |
| IV control | T169 | **47** | MIRO MIR7 MR11 MR8M MR1G … |
| Purch. groups | T024 | **462** | Buyer groups |
| Info records | EINA | **500** (cap) | Price / GR-IV default exists at scale |
| Source list | EORD | **173** | MOH1 SAO1 LC01 T501 DPKO — **not 1710 on page 1** |

Theoretical combination space: **139 × 15 × 23**. T163A is the prune. Used-on-1710 is a **single-digit** slice.

---

## 5. Transaction map (every family → glass)

This is the product’s t-code graph. **Open** = we launched it. **Catalog** = standard S/4, not launched this week.

### 5.1 Source

| Scenario | Create | Change | Display | List | Tables | BAPI |
|---|---|---|---|---|---|---|
| Vendor general | BP / XK01 | BP / XK02 | XK03 | MKVZ | LFA1 | BAPI_VENDOR_GETDETAIL |
| Vendor company | | | | | LFB1 | |
| Vendor purchasing | | | | | LFM1 | |
| Vendor bank | | | | | LFBK | |
| Info record | ME11 | ME12 | ME13 | ME1L / ME1M | EINA EINE | |
| Source list | ME01 | ME03 | ME03 | ME0M | EORD | |
| Quota | MEQ1 | MEQ3 | | | EQUK EQUP | |

### 5.2 Demand

| Scenario | Create | Change | Display | Convert / list | Tables | BAPI |
|---|---|---|---|---|---|---|
| Standard PR NB | **ME51N OPEN** | ME52N | **ME53N OPEN** | ME5A ME59N | EBAN EBKN | BAPI_PR_CREATE |
| Service / FO PR | ME51N item D | | | | EBAN | |
| Auto PO from PR | **ME59N ran, convert failed** | | | RM06BB30 | EBAN T161A | |
| RFQ | **ME41 OPEN** | ME42 | ME43 | ME4L ME4S | EKKO BSTYP=A | |

### 5.3 Commit (order)

| Scenario | Create | Change | Display | List | Tables | BAPI |
|---|---|---|---|---|---|---|
| Standard PO NB | **ME21N OPEN** | ME22N | **ME23N OPEN** | ME2N ME2L ME2M | EKKO F / EKPO | **BAPI_PO_CREATE1 EXISTS** |
| Custom PO ZNB | ME21N type ZNB | | | | T161-F-ZNB | same |
| STO UB | ME21N type UB | | **ME23N 100011 OPEN** | ME2K | EKKO RESWK | |
| 3rd-party S | ME21N item S | | TG10 used | | T163-5 EKPO | |
| Consumable K | ME21N KNTTP=K | | **4500002262 LIVE** | | EKKN CSKS | |
| Asset A | ME21N KNTTP=A | | | | ANLA EKKN | |
| Order F / Project P | ME21N | | | | AUFK PRPS | |
| Framework FO | ME21N type FO | | | | T161 FO SRV | |
| Subcontract L | ME21N item L | | | ME2O | EKPO RESB | |
| Consignment K(item) | ME21N item K | | | | T163-2 | |
| Service D | ME21N item D / ML81N | | | | ESLL | |
| Contract MK/WK | **ME31K OPEN** | ME32K | ME33K | ME3L | EKKO K | BAPI_CONTRACT_CREATEFROMDATA |
| SA LP | **ME31L OPEN** | ME32L | ME33L | ME3M | EKKO L EKET | |
| PO list | **ME2N OPEN** | | | | EKKO | |
| Held PO | ME21N Hold | | **3200000039 LIVE** | | EKKO 32… | |

### 5.4 Fulfill

| Scenario | T-code | Movement / object | Tables | BAPI |
|---|---|---|---|---|
| GR vs PO | **MIGO OPEN** | 101 | MKPF MSEG EKBE=1 | BAPI_GOODSMVT_CREATE |
| GR cancel | MIGO | 102 | | |
| Return to vendor | MIGO / ME21N ret | 122 | | |
| Inbound delivery | VL31N | | LIKP LIPS | |
| Service entry | ML81N | | ESSR | |
| Subcon issue | ME2O / MIGO 541 | | | |
| STO GI/GR | VL10B / MIGO | 351/101 | | |

### 5.5 Settle and pay

| Scenario | T-code | Tables | BAPI |
|---|---|---|---|
| IR | **MIRO OPEN** (CoCd popup; 500 RBKP already posted via MIRO) | RBKP RSEG EKBE=2 | BAPI_INCOMINGINVOICE_CREATE |
| Credit / subsequent | MIRO / MR8M | | |
| ERS | MRRL | T169 LFM1 XERSY | |
| GR/IR clearing | F.13 / MR11 | WRX | |
| Vendor line | FBL1N | BSIK | |
| Payment proposal | F110 | REGUH T042* | |
| House bank | FI12 | T012 T012K | |

### 5.6 Control / analytics / batch

| Need | T-code / program | Table |
|---|---|---|
| PO list | ME2N ME80FN | EKKO |
| Release | ME28 ME29N | T16FS EKKO FRGKE |
| Messages | NAST / ME9F | |
| IDoc / BI | SM35 SM37 WE02 | EDIDC |
| BAdI catalog | SE18 | SXS_ATTR / BADI_SPOT |
| Pricing | M/08 T683 | KONV KONP |
| Output | MN04 | TNAPR |

---

## 5b. BAdI / program / BAPI spine (grow this)

| Extensibility | Object | When it matters |
|---|---|---|
| BAPI | BAPI_PO_CREATE1 | LIVE exists |
| BAPI | BAPI_PR_CREATE | CATALOG |
| BAPI | BAPI_GOODSMVT_CREATE | CATALOG |
| BAPI | BAPI_INCOMINGINVOICE_CREATE | CATALOG |
| BAPI | BAPI_PO_GETDETAIL1 | CATALOG |
| BAdI | ME_PROCESS_PO_CUST | PO check / default WEBRE |
| BAdI | ME_PROCESS_REQ_CUST | PR |
| BAdI | MB_DOCUMENT_BADI | GR |
| BAdI | MRM_HEADER_CHECK | IR |
| SE38 | RM06ELLB | LIVE subcontracting stock |
| SE38 | RM06BB30 | ME59N |
| SM35 | batch input | CATALOG |

---

## 6. Used vs configured (the real gap)

| Family | Configured | Used on 1710 (LIVE) | Gap |
|---|---|---|---|
| Standard NB PO | T161-F-NB | 4500002260/2262, 500 EKKO | Thin — one vendor, one group |
| ZNB | T161 | EKKO had ZNB | Custom type unused by us |
| STO | T161-UB + T163-U | **100011** | Exists; not our create path |
| Third-party | T163-S | **TG10 every time** | Over-used; blocks GR |
| K consumable | T163K-K | 4500002262 | Only cost center; 22 other KNTTP idle |
| Held | 32… | 3200000039 | Park, not post |
| PR NB | T161-B-NB | 500 EBAN, 10014063 | ME59N convert dead |
| RFQ | T161-A × 12 types | **ME41 opens**; EKKO-A not counted | Config + t-code ready |
| Contract | T161-K MK/WK | **ME31K opens** | Config + t-code ready |
| SA | T161-L LP/LU | **ME31L opens** | Config + t-code ready |
| Consignment | T163-2 | **not read** | White space |
| Subcontract | T163-3 + RM06ELLB | **no EKPO-L proven** | Config+report, no docs |
| Service | T163-9 + FO SRV | **not walked** | White space |
| Asset / order / project | T163K A F P | **not walked** | White space |
| GR 101 | MIGO | **blocked on TG10**; **EKBE 500 × mvt 101 on MZ-RM-* / 1710** | Stock cycle already exists — wrong material |
| IR / pay | MIRO F110 | **MIRO opens**; **RBKP 500 RE / 1710 / USSU-VSF0x / 2017** | Settle already exists historically |

---

## 7. Opportunity packs (why this is a product)

Each pack is something a buyer, controller, or consultant can **sell or enable** because config is already there.

### P1 — Re-enter the stock PTP cycle that already posted (hours)
**Unlock:** material **MZ-RM-R200-*** (EKBE 101 on plant 1710, PO 4500000767…) not TG10. Then MIGO / MIRO.  
**Value:** do not “implement GR.” Copy a working document. F110 becomes the only unproven step.  
**Blocker we created:** TG10 is third-party.

### P2 — ME59N auto-PO (buyer productivity)
**Unlock:** EORD is **173 rows but on MOH1/SAO1/LC01/T501/DPKO**, not 1710. Plus EKGRP **002**.  
**Value:** 500 PRs already in EBAN. Source list is the missing plant assignment, not a missing program.

### P3 — Consignment & subcontract (inventory models already in T163)
**Unlock:** item cat K or L + vendor info record + (subcon) BOM/RESB.  
**Value:** two industry-standard models; SE38 already has the stock monitor.

### P4 — Contracts and SAs (leverage 139 types)
**Unlock:** ME31K / ME31L on MK/WK/LP; release against them (ME58).  
**Value:** this is how a real purchasing org stops raising one-off NBs.

### P5 — The other 22 account assignments
**Unlock:** T163K A/F/P/N/C + matching CO objects (ANLA, AUFK, PRPS).  
**Value:** capex, production, PS — currently the client looks like “cost center only.”

### P6 — Third-party done properly
**Unlock:** item cat S + SD sales order (KNTTP X/C) + IR without GR.  
**Value:** stop treating TG10 as a stock PO. Make drop-ship a first-class scenario.

### P7 — Payment close
**Unlock:** LFBK + T042* + BSIK after a real IR.  
**Value:** the only thing that makes PTP a *pay* process. Today it stops at PO.

### P8 — Control (release + GR-based IV + audit)
**Unlock:** T16FS if hits>0; WEBRE defaults; ME28.  
**Value:** held 32… and “Enter GR-Based IV” were operator pain because control is on and undocumented.

---

## 8. Switchboard (one field = another process)

| Switch | From → to | Process that appears |
|---|---|---|
| EKORG | 1000 → 1710 | Vendor purchasable |
| EKGRP | 001 → 002 | ME59N / PO |
| MARA/TG10 PD | 3rd-party → stock material | GR 101 |
| PSTYP | 0 → 3/2/5/7/9 | Subcon / consignment / 3rd / STO / service |
| KNTTP | blank → K/A/F/P | Consumable / asset / order / project |
| SAKTO | 610000 → 51600000 | Extra CO object |
| WEBRE | empty → X | IR waits for GR |
| BSART | NB → UB / FO / ZNB | STO / framework / custom |
| BSTYP | F → K/L/A | Contract / SA / RFQ |
| Hold | 45… → 32… | Parked, not posted |

---

## 9. Product: analysis wing that grows

Do not treat this file as a one-off memo. The product is:

1. **Operator loop** — `see → SE16N/SE37/SE18/SE38/SM35 → classify → append`.
2. **Evidence ranks** — LIVE never mixed with CATALOG.
3. **Graph** — process → scenario → t-code → table → BAPI → gap → opportunity.
4. **Append-only inventory** — every new table hit updates the heatmap, not a new essay.
5. **Same shape for OTC, R2R, Treasury** — swap the spine, keep the ranks.

Implementation seed: `docs/ANALYSIS_WING.md` + this map + `data/runs/analysis_ptp/`.

Next automated wave (when glass is free): T163A, T16FS, EINA, EORD, EKKO by BSTYP, EKPO by PSTYP, EKBE, RBKP, then open ME41/ME31K/ME31L/MIRO/ME80FN/SE18.

---

## 10. Live wave log

Wave 0 (prior): T001 T001W T024E LFA1 MARC EBAN EKKO AGR_USERS SE37 SE38 ME51N ME21N ME23N ME53N MIGO.  
Wave 1 (this session start): T161=139, T163=15, T163K=23.  
Wave 2 LIVE: T163A=94, T16FS=98, T16FG=3, T024=462, EINA=500, EORD=173, T460A=500, T169=47, EKBE=500 (101/1710/MZ-RM-*), RBKP=500 (MIRO/1710/USSU).  
Wave 3 t-codes OPEN: ME41, ME31K, ME31L, ME2N, MIRO (CoCd popup). SE18 not landed (title SAP / shell). Shots: `data/runs/analysis_ptp/`.
