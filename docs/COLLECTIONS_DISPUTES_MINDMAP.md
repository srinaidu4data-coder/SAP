# Collections & Disputes — granular mind map (the missing OTC leaves)

These were treated as “BSID exists.” That is not a process. This is the leaf-level map
to attach to OTC next full run. Evidence: BSID **3,014**, BSAD **5,174**, KNKK **0**,
VBRK **5,982**, NAST **928** (LIVE Number of Entries). Rest CATALOG until counted.

```
COLLECT CASH
├── OPEN AR
│   ├── BSID-BUKRS (1710 LIVE on PTP/OTC book)
│   ├── BSID-KUNNR → KNA1 / KNVV (1,283 / 795)
│   ├── BSID-UMSKZ special G/L (down payment, bill of exch.)
│   ├── BSID-ZFBDT baseline date
│   ├── BSID-ZBD1T/ZBD2T/ZBD3T cash discount days
│   ├── BSID-ZTERM payment terms → T052
│   ├── BSID-ZLSPR payment block → T008
│   ├── BSID-MANSP dunning block
│   ├── BSID-MANST dunning level
│   ├── BSID-DMBTR / WRBTR / WAERS
│   ├── BSID-REBZG residual / invoice ref
│   └── hop → FBL5N, F-32, F-28, F150, UDM_GENIL
├── DUNNING
│   ├── T047 / T047A / T047B / T047E / T047I / T047R
│   ├── KNB5 dunning data (company + dunning area + procedure + level)
│   ├── MHNK / MHND dunning history
│   ├── F150 proposal + print
│   ├── NAST / SOST output of dunning letter
│   └── ticket: “customer never got dunning” = KNB5 empty OR NAST 928 vs 3014 open items
├── COLLECTIONS (FSCM)
│   ├── UDM_COLL_ITEM worklist
│   ├── UDM_STRATEGY / collection strategy
│   ├── UDM_GROUP collection group
│   ├── contact / promise-to-pay (UDM_P2P)
│   ├── specialist (collection clerk) vs BPINST/SERV_MAN who billed
│   └── hop: no KNKK + no UKMBP = unsecured book
├── DISPUTES (FSCM)
│   ├── UDM_DISPUTE case
│   ├── SCMG_T_* case types / reasons
│   ├── disputed amount vs BSID-DMBTR
│   ├── reason → SD (pricing, qty, tax) or MM (short ship) or FI (dup pay)
│   ├── status: new / in process / confirmed / closed / written off
│   ├── linked objects: VBRK-VBELN, VBAK, LIKP
│   └── BAPI_DISPUTE_* / UDM APIs
├── DEDUCTIONS
│   ├── T053R / T053S reason codes
│   ├── residual item (BSID-REBZG)
│   ├── automatic write-off tolerance (OBA3 / T043)
│   └── hop: cash app FEBAN → reason → dispute or write-off
├── CASH APPLICATION
│   ├── FEBKO / FEBEP bank statement
│   ├── FEBA / FEBAN
│   ├── lockbox FLB* 
│   ├── interpretation algorithm (OT83)
│   ├── F-28 / FBZ1 / FEBAN post
│   └── BSAD when cleared (5,174 LIVE)
├── CREDIT (blocker for new sales, not just collect)
│   ├── KNKK = 0 LIVE — classic credit empty
│   ├── UKMBP_CMS / UKM_ITEM FSCM
│   ├── FD32 / UKM_BP / VKM1 / VKM3 / VKM4
│   └── hop: VA01 check → blocked SO → no delivery → no bill → no cash
└── WRITE-OFF / AGENCY
    ├── FB05 / F-32 residual
    ├── T041C / account determination
    ├── collection agency transfer
    └── P&L hop: bad-debt expense
```

## Support influx from LIVE numbers

| Signal | Prediction |
|---|---|
| BSID 3,014 vs NAST 928 | Most open items have no correspondence → “we never got a statement” |
| KNKK 0 + VBAK 12,255 | New orders not credit-checked in classic CM → unsecured AR |
| BSAD 5,174 vs BSID 3,014 | Cash app works historically; residual/dispute not mapped |
| VBRK 5,982 vs BSID 3,014 | Part of the book is still open — DSO is real |

## 6–60 month process (collections)

- **6 mo:** SOP FBL5N 1710 weekly; dunning procedure on KNB5 for 1710 customers.  
- **12 mo:** FSCM dispute case types tied to SD reason; stop email-only disputes.  
- **24 mo:** lockbox/FEBAN interpretation; residual reason codes mandatory.  
- **36–60 mo:** UKM credit (because KNKK is empty); collection worklist; agency.

Do not “implement collections” as a new module install until KNB5/T047 and UKM vs KNKK are counted.
