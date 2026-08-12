# SAP Navigation Playbook (encoded from industry practice)

We did **not** watch 10,000 YouTube videos. We encoded the **same rules** those tutorials teach.

## Golden rules (every serious SAP GUI Scripting guide)

1. **Command field only for tcodes**
   ```
   session.findById("wnd[0]/tbar[0]/okcd").text = "/nF110"
   session.findById("wnd[0]").sendVKey(0)
   ```
   Or: `session.StartTransaction("F110")`

2. **Never type tcodes into dynpro fields**  
   On S/4, **XK03 → Display Supplier (BP)**.  
   The **Supplier** box is for vendor/BP number — **not** `/nF110`.

3. **Discover field IDs the pro way**
   - SAP GUI: *Script Recording & Playback*
   - Or F1 → Technical Information on a field
   - Or community “findById” catalogs

4. **Keys**
   - Enter = `sendVKey 0`
   - Execute F8 = `sendVKey 8`
   - Back = `sendVKey 3`

## What the bot does now

| Step | Action |
|------|--------|
| 1 | `StartTransaction(tcode)` or **okcd** only |
| 2 | Fill fields from `nav_catalog.py` (LIFNR, EBELN, …) |
| 3 | Enter / F8 |
| 4 | Multi-table extract already done before GUI |

Catalog file: `sapilot/autobot/nav_catalog.py`  
Engine: `sapilot/autobot/navigator.py`

## Your bug (fixed)

| Wrong | Right |
|-------|--------|
| Click body → type `/nF110` into **Supplier** | `StartTransaction("XK03")` then Supplier=`0000100001` |

## S/4 note

Display Vendor **XK03/FK03** often opens **BP / Display Supplier**.  
Bot tries both classic `RF02K-LIFNR` and BP partner number field IDs.
