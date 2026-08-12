# Online + Fleet Exhaust Checklist

## Fleet (must be 22/22 before stop)
- 10 PTP (S1–S10)
- 10 OTC (O1–O10)
- 2 ABAP debug (A1 ST22, A2 SE38) — **read-only**, never debugger field replace

## Live online
1. SAP Logon → Enable Scripting
2. RZ11 `sapgui/user_scripting=TRUE`
3. Login Vista client 100
4. `set SAPILOT_LIVE_GUI=1` && `python -m sapilot online-20`

Tick template: 2/100
