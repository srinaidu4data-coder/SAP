# SAPILOT — Security & Data Flows

## What leaves the machine

| Destination | Data | Controls |
|---|---|---|
| SAP application server | RFC / GUI / optional OData / ADT | Existing SAP auth; technical user per tier |
| SpaceXAI (`api.x.ai`) | Redacted prompts: plans, error text, non-sensitive table summaries | `RedactionGate` mandatory; no screenshots unless `--allow-vision` |
| Anthropic (optional critic) | Same as above | Only if `ANTHROPIC_API_KEY` set |
| Local disk (`data/runs`, `data/kb`, `data/vault`) | Journals, reports, episodic memory, encrypted credentials | Vault DPAPI or passphrase; vault gitignored |

**No telemetry. No analytics. No automatic cloud logging.**

## Redaction gate (fail closed)

Before any model call:

- Field IDs: `BANKN`, `BANKL`, `IBAN`, tax IDs, passwords, etc.
- Regex: IBAN, SSN, EIN, long digit runs (accounts), 9-digit routing
- Replacement: stable tokens `«KIND_xxxx»` so the model can reason relationally

Screenshots: disabled by default. `--allow-vision` only; still subject to policy that pixels are last resort.

## Credentials

- Stored via `sapilot vault set` → `data/vault/credentials.vault`
- Windows: DPAPI machine-bound when pywin32 present
- Else: Fernet with `SAPILOT_VAULT_PASSPHRASE` (PBKDF2)
- Never plaintext on the stick; never in `.env` committed to git

## Execution policy

- Tier from `T000-CCCATEGORY` + signed `local_policy.yaml` — **not** from the LLM
- `PolicyViolation` terminates the run
- Destructive denylist in `policy/denylist.yaml`
- T2 writes require human approval token (`sapilot approve`)
- Debugger value replace: not implemented (permanent)

## Journal / audit

- Per-run JSONL under `data/runs/<run_id>/journal.jsonl`
- HTML report for human review
- Escalation is a first-class outcome (not a silent failure)

## Lost media

If a USB stick with SAPILOT is lost:

1. Vault ciphertext without DPAPI machine context or passphrase is not usable as SAP login.
2. Rotate SAP technical user passwords anyway.
3. Revoke any long-lived model API keys that were only on that media.

## Recommended deployment controls

- Dedicated technical users per tier (never a named consultant)
- T3-only roles for production diagnostics
- Written control-owner sign-off before T2
- Network egress allowlist: SAP hosts + configured model endpoints only
