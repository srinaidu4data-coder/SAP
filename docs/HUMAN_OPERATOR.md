# Human operator (vision only)

**This product is a general SAP GUI operator.** It must work on any
transaction, module, or process the user names. A t-code used in a test
(ME21N, SE16N, VA01, FB01, …) is an **example only**. Never treat the
example as the product requirement.

No SAP GUI Scripting. No RZ11. No `FindById`. Same loop on every screen:

look → move (closed loop) → check focus → type → read the status strip
→ prove in a table if the user asked for a create.

## Core commands (process-agnostic)

```
sapilot operator see
sapilot operator goto <TCODE>
sapilot operator fill --label <visible label> --value <text> [--enter] [--side right|left|below|on]
sapilot operator click --label <visible label> [--side on|left|right|below]
sapilot operator key <NAME>
sapilot operator dialog --title <dialog> --click <button>
sapilot operator save-doc
sapilot operator prove --table <TAB> --field <label> --value <key> [--user <ERNAM>]
```

`sapilot operator me21n` is a **sample script** that happens to create a
purchase order. It is not the product.

## Eyes

Tesseract on this machine:
`C:\Program Files\Tesseract-OCR\tesseract.exe`
Override: `SAPILOT_TESSERACT`.

## Hard rules

1. The operator is **not** a PTP bot, OTC bot, or FI bot. It is a person
   at the glass for the whole SAP GUI.
2. Never claim a create from a status bar or a screenshot.
3. CREATED means SE16N (or the table the user names) shows the key, hit
   count is 1 (or a small filtered set), and is **not** a 500-row dump.
   `No values found` is not a create. A status-bar number is not proof.
4. Click is closed-loop. After type, OCR must see the value.
5. Existing documents on the system are **looked at**, not created by us.
