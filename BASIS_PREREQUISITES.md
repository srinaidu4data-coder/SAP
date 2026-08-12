# SAPILOT — Basis Prerequisites Checklist

Hand this page to the Basis team before live GUI/RFC runs.

```
□ RZ11: sapgui/user_scripting = TRUE                (runtime)
□ RZ10: same, in the instance profile                (persists across restart)
□ RZ11: sapgui/user_scripting_disable_recording = FALSE
□ RZ11: sapgui/user_scripting_force_notification = FALSE   (sandbox only)
□ SAP GUI client: Options → Accessibility & Scripting → Scripting → Enabled
□ SAP GUI client: both "Notify when..." checkboxes UNCHECKED
□ User role: S_RFC for RFC_READ_TABLE function group (or Z-wrapper provided)
□ User role: S_TABU_DIS / S_TABU_NAM display access to the config table groups
□ User role: S_TCODE for SE16N, SU53, ST22, SLG1, F110, FBZP
□ T1 sandbox user only: S_DEVELOP with DEBUG, ACTVT 03
□ T1 sandbox user only: S_TRANSPRT for the dedicated SAPILOT_AUTOCFG transport
□ ADT services active in SICF (/sap/bc/adt) if debugger integration is in scope
□ /IWFND OData services activated for the CDS views in scope
□ Dedicated technical user per tier — never reuse a named consultant's account
□ Client role in T000 correctly set so tier derivation works
□ Written sign-off from the control owner before any T2 deployment
```

## Tables the knowledge layer reads (display)

FBZP chain: `T042`, `T042B`, `T042Z`, `T042E`, `T042I`, `T042A`, `T042Y`, `T012`, `T012K`  
Vendor: `LFA1`, `LFB1`, `LFBK`, `BNKA`, `TIBAN`  
Open items: `BSIK` (classic)  
Run results: `REGUV`, `REGUH`, `REGUP`, `REGUA`  
Messages: `T100`  
Client: `T000`

## Preflight

```bat
run.bat preflight
```

Hard failures refuse start. Soft checks (GUI not running, pyrfc missing) warn until you enable live channels.
