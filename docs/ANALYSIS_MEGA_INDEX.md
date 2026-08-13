# Analysis mega pack — how to read this

This is the product the 50-page memos were not.

| Artifact | What it is | Size |
|---|---|---|
| [ANALYSIS_MEGA_REPORT.html](ANALYSIS_MEGA_REPORT.html) | Encyclopedic: one page per type, t-code, BAPI, BAdI, month, incident, actor | **1,227 pages** · ~2.8 MB |
| [../data/runs/analysis_mega/PROGRAM_6_TO_60.md](../data/runs/analysis_mega/PROGRAM_6_TO_60.md) | 6–60 month process change (not SPRO) | companion |
| [../data/runs/analysis_mega/SUPPORT_PREDICTION.md](../data/runs/analysis_mega/SUPPORT_PREDICTION.md) | 60 predicted tickets, hops, teams | companion |
| [../data/runs/analysis_mega/ASSOCIATIONS_AND_ACTORS.md](../data/runs/analysis_mega/ASSOCIATIONS_AND_ACTORS.md) | Who did what; multi-hop graphs | companion (agent) |
| [../data/runs/analysis_mega/LIVE_COUNTS.json](../data/runs/analysis_mega/LIVE_COUNTS.json) | Number of Entries (not 500) | companion (live agent) |
| [ANALYSIS_GRANULARITY_STANDARD.md](ANALYSIS_GRANULARITY_STANDARD.md) | How every future process must be mapped | |
| [COLLECTIONS_DISPUTES_MINDMAP.md](COLLECTIONS_DISPUTES_MINDMAP.md) | The OTC leaves that were skipped | |
| [PRODUCT_COSTING_MINDMAP.md](PRODUCT_COSTING_MINDMAP.md) | CO-PC field-level mind map | |
| [ANALYSIS_FUTURE_MODULES.md](ANALYSIS_FUTURE_MODULES.md) | Next 16 analyses | |
| [PTP_OPPORTUNITY_MAP.md](PTP_OPPORTUNITY_MAP.md) | PTP switchboard | |
| [OTC_EXHAUSTIVE_ANALYSIS.md](OTC_EXHAUSTIVE_ANALYSIS.md) | OTC cash thesis | |

Regenerate the 1,227-page file after new counts:

```
python scripts/generate_mega_report.py
```

**Rule:** if a table listed 500, it is a **cap**, not a census.

### LIVE census (Number of Entries, verified popups)

| Table | Entries | Meaning |
|---|---:|---|
| VBAK | **12,255** | Sales orders |
| VBAP | **13,804** | Order items |
| LIKP | **7,959** | Deliveries |
| LIPS | **9,815** | Delivery items |
| VBRK | **5,982** | Billing headers |
| VBRP | **6,693** | Billing items |
| VBFA | **301,220** | Document flow |
| BSID | **3,014** | Open AR |
| BSAD | **5,174** | Cleared AR |
| NAST | **928** | Output |
| EDIDC | **1,239** | IDoc control |
| EDIDS | **4,359** | IDoc status |
| KNA1 | **1,283** | Customers |
| KNVV | **795** | Customer sales views |
| MVKE | **1,723** | Material sales views |
| KNKK | **0** | Credit master **empty** — 12k orders, 3k open AR, no KNKK |
