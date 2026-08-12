# Vision Operator Playbook

`vision_operator.py` drives SAP GUI with real mouse/keyboard input only — **no
SAP GUI Scripting, ever.** `sapgui/user_scripting` is a server-side switch most
customers will never enable for a consultant's laptop; this bot has to work
the same way a person does: it opens what's on screen, clicks it, types into
it, and looks at the result. There is no OCR — screen state is read by an
agent (an LLM) looking at screenshots, the same way a person reads a monitor.

This document exists so the same mistakes aren't re-debugged from scratch
next time. Every rule below was a real, reproduced failure against a live
SAP system, not a guess.

## The rule that actually mattered most: focus before EVERY keystroke, not just clicks

`SendKeys` goes to whatever window Windows currently considers foreground —
full stop, no exceptions. A prior click having focused the right window does
**not** guarantee that's still true by the time the next `type()`/`key()`
call fires, especially across separate process invocations: a terminal or
chat app regaining foreground focus between two automation calls is a real,
observed failure mode, not a hypothetical one — it resulted in an entire
transaction code being typed into an unrelated application's own input box
instead of SAP. `Op.type()`, `Op.clear()`, and `Op.key()` all call
`self.focus()` internally now, every time, with no "already focused, skip
it" shortcut. That earlier shortcut (added to chase speed) was the direct
cause of several minutes of silently-failed navigation that looked, from the
screenshots taken *before* it, like it should have worked. Don't reintroduce
it.

## The five rules

1. **Popups are separate windows.** A SAP search-help dialog ("Cost Center
   (1)"), a message box, "Exit Document" — none of these are part of the main
   session window's canvas. They are their own top-level `HWND` with their
   own position and size. Computing a click as `main_window_rect * fraction`
   while a popup is open will hit whatever happens to be under that point in
   the *main* window, not the popup. Always `find_popup()` first, then click
   relative to `Op.for_popup(...)`'s own rect.

2. **Jump the cursor, don't animate it.** An eased mouse path that visibly
   glides toward a target *looks* nicer, but it also passes over whatever
   sits between the old and new position. On one live screen this triggered
   a "quick view" hover card on a Business Partner link that then ate the
   next several clicks. `Op.click()` jumps directly.

3. **Don't un-maximize the window you just maximized.** `ShowWindow(hwnd,
   SW_RESTORE)` called unconditionally on every focus will silently shrink an
   already-maximized window back to its last floating size — which
   invalidates every relative coordinate computed against the maximized
   rect. `sapilot.connect.mouse.focus_window()` only restores a window that's
   actually minimized; reuse it, don't reimplement it.

4. **Never assume focus.** Some screens auto-focus their first field on
   entry (SE16N's "Data base" field, ME51N's Supplier field); SAP Easy
   Access does *not* reliably re-focus the command field after `F3`
   back-navigation — focus can be left sitting on the navigation tree. Click
   the field before typing unless you've specifically verified auto-focus
   for that exact screen.

5. **On the first rejection, go to the table — don't guess twice.** If a
   field errors ("mandatory", "not found", "belongs to company code A, not
   B"), the fast path is never a second guess. Call `open_table_browse(op,
   TABLE)` — it's the full command-field → `/nSE16N` → table name → `F8` →
   "List Output" round trip in one call — and read a real value out of the
   resulting screenshot. Guessing plausible-looking values (`1000`,
   `400000`) burns exactly as many turns as looking the real one up, except
   half the guesses are wrong.

## Screenshots need focus too, not just clicks

A screenshot is just a capture of whatever pixels are on screen at a given
rect — if the SAP window isn't actually the topmost window at that screen
region (another app is covering it, or it lost focus since the last action),
the capture silently returns that *other* window's content instead, with no
error. `Op.screenshot()` therefore focuses the window before capturing by
default. Don't skip this to save time — a screenshot of the wrong window
looks completely valid and will send the agent confidently down the wrong
path.

## Also DPI-aware

The whole coordinate system silently breaks on any display scaled above
100% unless the process calls `SetProcessDpiAwareness` before any `win32gui`
call. This is handled once, at import time, in
`sapilot.connect.mouse._ensure_dpi_aware()` — `vision_operator` imports from
that module specifically so it inherits the fix. Don't add a second,
uncoordinated DPI-awareness call elsewhere; there's only one process-wide
setting and the first caller wins.

## Speed: batch, don't screenshot-per-keystroke

The single biggest cost in a vision-operator session is round trips, not the
clicks themselves. `Op.fill([FillStep(...), FillStep(...), ...])` executes an
entire row of a form (or several ALV grid cells) and returns **one**
screenshot at the end. Screenshot after every keystroke only when you
genuinely don't know where the next field landed — e.g. right after opening
an unfamiliar screen for the first time. Once a screen's field layout has
been confirmed once in a session, reuse those coordinates for the rest of
that session without re-verifying each one.

## Recovery pattern for a stuck field, end to end

```python
from sapilot.autobot.vision_operator import Op, open_table_browse, goto_transaction

op = Op.for_session(shot_dir=r"C:\path\to\scratch")

# ... field rejected with "CO object belongs to company code 1000, not 1010" ...

open_table_browse(op, "CSKS")          # cost center master, one call
# -> read the screenshot, filter for the company code actually needed,
#    pick a real Cost Center value, then continue the original transaction.
```

## Known screen quirks worth remembering

- **SE16N (modern theme):** the table-name field is labelled **"Data base:"**,
  not "Table Name" — same field, different theme. It is auto-focused on
  entry. `F8` doesn't run the query directly; it validates the table name and
  reveals a **"List Output"** button, which is what actually executes it.
- **ME51N item grid:** typing a Material and pressing Enter does *not*
  auto-populate Short Text / Unit / Material Group the way older classic
  ME51N does in some releases — those only appear after Delivery Date and
  Plant are also filled and the row is re-validated (Enter again).
- **Materials without stock/MRP data** (`ProcType` blank in `MARC`) demand an
  Account Assignment Category (e.g. `K` = cost center) before the PR can be
  saved — this is normal, not a bug, and the Account Assignment tab only
  appears on the item detail panel *after* the category is set.
- **A plant belongs to exactly one company code** (`T001W` / `T001K`), and
  every account-assignment object (cost center, WBS, etc.) used on a line
  must belong to *that* company code, not whatever company code your vendor
  or header defaults to. When SAP says "belongs to company code X, not Y",
  trust it over any earlier assumption.
