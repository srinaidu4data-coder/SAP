# Analysis wing

The human operator has two jobs. Hands create. **This wing only looks.**

It walks the same glass (SE16N, SE37, SE18, SE38, SM35, SM30, SPRO-backed tables)
and answers: **which business scenarios exist here, which objects make each one
possible, and what is one hop away.**

A t-code used in a test (ME21N, FB50) is an example. The product is a
**process → scenario → object graph** for any module the user names.

## What it produces

For a named process (first cut: PTP):

1. **Process map** — phases in order (source → demand → order → receive → invoice → pay).
2. **Scenario inventory** — every variant that is *configured*, *used*, *executable*, or *blocked*.
3. **Enablement pack** — every table, field, BAPI, BAdI, program, and t-code that
   must be present for that scenario to be available.
4. **Association** — if scenario A exists, which adjacent scenarios become cheap
   to unlock (same org, same vendor view, same plant).

## Evidence ranks (never mix them)

| Rank | Meaning |
|---|---|
| **LIVE** | We opened the table or t-code on APEX-2023 / client 100 and saw the row or screen. |
| **INFERRED** | Transactional residue implies config (e.g. EKKO `ZNB` ⇒ T161 has ZNB). |
| **CATALOG** | SAP standard object that *would* be read next; not yet opened here. |
| **ABSENT** | We looked and did not find it, or the path failed. |

CREATED documents are not this wing. A 500-hit SE16N dump is a **count**, not a
scenario proof. A 1-hit filter is a **key proof**.

## How the operator is used

Same loop as the navigator, read-only:

```
see → goto SE16N|SE37|SE18|SE38|SM35
    → fill table / object
    → List Output or Display
    → see
    → classify (LIVE / INFERRED / CATALOG / ABSENT)
```

Never Post. Never Save. Never Hold. If a write screen opens, leave it.

## Granularity (mandatory)

See `docs/ANALYSIS_GRANULARITY_STANDARD.md`. Stop at **table-FIELD + hop**, not table name.
Collections and disputes are first-class processes (`docs/COLLECTIONS_DISPUTES_MINDMAP.md`), not OTC footnotes.

## Processes in this wing

| Process | Doc |
|---|---|
| PTP | `PTP_OPPORTUNITY_MAP.md` |
| OTC | `OTC_EXHAUSTIVE_ANALYSIS.md` |
| Collections / disputes | `COLLECTIONS_DISPUTES_MINDMAP.md` |
| Product costing | `PRODUCT_COSTING_MINDMAP.md` |
| Future modules | `ANALYSIS_FUTURE_MODULES.md` |
| Mega encyclopedia | `ANALYSIS_MEGA_INDEX.md` |

## Product rule

Do not shrink this wing to “10 YAML scenarios” in `sapilot/copilot/scenarios/`.
Those are **our** test scripts. The wing reports **the system’s** scenarios.
