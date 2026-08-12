# SAPILOT — Architecture Decisions

## D1 — Ship diagnostic engine first (panel Part 5)
**Decision:** Full package scaffold exists, but the first *complete* product path is `sapilot diagnose` (RFC/mock knowledge channel + FBZP/vendor/open-item analysis + HTML report).  
**Why:** Highest client value, near-zero audit risk, no GUI scripting dependency.

## D2 — Primary LLM is SpaceXAI / xAI (Grok), not Claude
**Decision:** `brain/router.py` defaults PLANNING and ERROR_DIAGNOSIS to `grok-4.5` via `XAI_API_KEY` + `https://api.x.ai/v1` (OpenAI-compatible). Critic may use Anthropic if `ANTHROPIC_API_KEY` + Claude model is configured; otherwise same vendor, second call.  
**Why:** Runtime environment is Grok/xAI; skill policy defaults to SpaceXAI. Multi-vendor critic remains supported.

## D3 — Unsigned local policy allowed in lab
**Decision:** `SAPILOT_ALLOW_UNSIGNED_POLICY` defaults to `1` in CLI. Production deployments must sign `local_policy.yaml` with `SAPILOT_POLICY_HMAC_KEY` and set allow-flag to `0`.  
**Why:** Developers need zero-friction bootstrap; signature verification path is implemented.

## D4 — Tier never from CLI “tier=” flag
**Decision:** CLI accepts `mandt` + `cccategory` only for *mock* runs; live mode must read `T000` via RFC. User cannot pass `T1_SANDBOX` directly.  
**Why:** Finding 1 — model/user cannot escalate tier.

## D5 — Real SAP GUI / Logon Pad is the default for Co-pilot
**Decision:** Co-pilot connects to **real SAP GUI** via SAP Logon Pad using system description + client + user + password. Mock is **opt-in only** (`--mock`) for CI/unit tests.  
**Why:** Product intent is a live consultant co-pilot; user supplies username/password (or vault / `--attach`).  
**Safety:** Tier policy + denylist still block destructive actions; password is prompted hidden or stored in DPAPI vault — never logged.

## D6 — Profile A portability only
**Decision:** No portable SAP GUI. Stick/runtime carries Python + wheels + optional NW RFC DLLs; host supplies SAP GUI.  
**Why:** Finding 10 — honest portability.

## D7 — Debugger field replace permanently absent
**Decision:** No code path sets debugger field values. ADT client exposes set-breakpoint + read-variables only.  
**Why:** Finding 5 / RT-AUDIT tripwire.

## D8 — Knowledge ladder order
**Decision:** Interfaces exist for OData → RFC_READ_TABLE → HANA → SE16N(GUI). Current default path is RFC (and mock RFC).  
**Why:** Finding 4; OData/HANA optional when environment provides them.

## D9 — Redaction on model egress, not on local journal raw
**Decision:** Journal may store operational detail locally; all model router payloads pass `RedactionGate`. HTML reports for external sharing should use redacted diagnosis payloads (CLI redacts journal diagnosis event).  
**Why:** Finding 6 — regulated data must not leave process to cloud models.

## D10 — F110 “Start Immediately” denylist outside T1
**Decision:** Encoded in `policy/denylist.yaml` patterns for T2/T3; T1 allows payment run capability via tier matrix.  
**Why:** Finding 1 SOD.

## D11 — Config transport name
**Decision:** Hard-coded `SAPILOT_AUTOCFG` for all config diffs.  
**Why:** Finding 9 — avoid polluting random CTS requests.

## D12 — Dependencies
**Decision:** Core install has no pyrfc/pywin32 required so `pytest` and `diagnose --mock` work on any machine. SAP extras optional.  
**Why:** Knowledge layer must be sellable without Basis day-0.
