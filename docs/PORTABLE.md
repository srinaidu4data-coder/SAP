# Portable pack — try SAPILOT on another Windows PC

SAPILOT is a **general SAP GUI operator**. Any module, any t-code, any process.
The pack is not a purchase-order tool, not a payment-run tool, not a costing
tool. Named spines in the catalog are **examples**.

Profile A: **we ship Python + the app. The other PC supplies SAP GUI.**

## What to copy

| Item | Where |
|---|---|
| Zip | `dist/SAPILOT-portable.zip` (also on the Desktop) |
| Folder | `dist/SAPILOT-portable/` |

About **55 MB**. No admin install. No system Python required.

## On the other PC

1. Unzip. Keep the folder together.
2. Double-click **`CHECK.bat`**.
3. **PASS** means the operator pack works there **without SAP**.
4. **`START.bat`** — help, example spines, co-pilot UI, or `operator see`.

## What PASS proves

- Embedded Python starts
- Policy loads
- Display wing lists **example** spines and refuses create/change/post
  across modules (not one t-code)
- Unit tests that travel with the pack pass

## What PASS does not prove

Live SAP. That needs SAP Logon on that PC. Then, on whatever screen you are on:

```
SAPILOT.bat operator see
SAPILOT.bat operator goto <TCODE>
SAPILOT.bat display goto <DISPLAY_TCODE>
SAPILOT.bat display plan
```

Use a display t-code from **any** module. The display wing refuses create /
change / post.

## Rebuild

```
python scripts\pack_portable.py
```
