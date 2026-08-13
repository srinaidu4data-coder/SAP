# Product Costing — field dictionary (granular leaves)

Every row is a leaf the next SE16N pass must be able to filter.  
**Do not stop at table name.**

## Org

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| TKA01-KOKRS | Controlling area | TKA02 |
| TKA02-BUKRS | Company in CO | 1710? |
| T001K-BWKEY | Valuation area | = plant usually |
| T001K-MLBWA | ML active | CKMLHD |
| T001W-WERKS | Plant | MARC, MBEW |
| T001-WAERS | CoCd currency | KEKO-HWAER |

## Material / price

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| MARA-MATNR | Material | KEKO, MBEW |
| MARA-MTART | Type | costing relevancy |
| MARC-LOSGR | Costing lot size | CK11N qty |
| MARC-NCOST | Do not cost | CK40N skip |
| MARC-SOBSL | Special procurement | TG10 PD → no mfg |
| MARC-HKMAT | Origin group | cost component |
| MBEW-VPRSV | S or V | CK24 vs moving |
| MBEW-STPRS | Standard | released estimate |
| MBEW-VERPR | Moving average | V materials |
| MBEW-PEINH | Price unit | /1000 errors |
| MBEW-BKLAS | Valuation class | OBYC BSX/GBB/PRD |
| MBEW-LBKUM / SALK3 | Stock qty / value | CKMLPP |
| QBEW-* | Project stock | PS |
| EBEW-* | Sales-order stock | MTO |

## Quantity structure

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| MAST-STLAN | BOM usage | STPO |
| STPO-IDNRK / MENGE / MEINS | Component | CKIS |
| MAPL-PLNTY | Routing | PLPO |
| PLPO-ARBID / VGW01–06 | Work center / times | CRHD, CSLA |
| CRHD-ARBPL | Work center | CRCA |
| CRCA-KOSTL / LSTAR | CC + activity | CSKB, COST |
| COST-TKF / TKS | Activity price | labor component |

## Costing variant

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| TCK03-KLVAR | Variant | CK11N |
| TCK03-BWVAR | Valuation variant | TCK05 |
| TCK03-KALKA | Costing type | legal vs group |
| TCK05 strategy seq | Price source | EINE / MBEW / PO |
| TCKH1-ELEHK | Cost component | KEPH |
| TCK31 sheet | Overhead | KZS2 |

## Estimate

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| KEKO-KALNR | Estimate number | CKIS, ML |
| KEKO-KADKY | Costing date | which is released |
| KEKO-FREIG | Released? | MBEW-STPRS |
| KEKO-FEH_ANZ | Error count | CK40N log |
| KEPH-KST0xx | Component values | COPA / margin |
| CKIS-TYPPS | Item category (M/E/L/…) | BOM vs activity vs subcon |

## ML / actual

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| CKMLHD-KALNR | ML header | CKMLPP |
| CKMLPP-LBKUM | Period qty | not-distributed |
| CKMLCR-SALK3 / PVPRS | Period value / PUP | CKM3 |
| CKMLCP run status | Close | period-end |

## Order / variance

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| AUFK-AUART / AUART | Order type | T003O |
| AUFK-PHAS0–3 | Created/released/completed | settlement |
| AFPO-MATNR / PWERK | Output material | MBEW |
| AFRU-LMNGA / XMNGA | Yield / scrap | variance |
| COSP-WKG* | Value by cost element | KKS1 |
| COBRB-KONTY / BETRR | Settlement receiver | FI/CO |

## FI

| Table-FIELD | Meaning | Next hop |
|---|---|---|
| T030-KTOSL | BSX GBB PRD AUM KDM | GR dump |
| COEP-KSTAR / WOGBTR | Actual CE / amount | P&L |
| ACDOCA-RLDNR / RACCT | S/4 journal | R2R |
