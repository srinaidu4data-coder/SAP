# Product rule: ONLINE GUI is the tool

This product is **not** an offline twin demo. The purpose is to drive **live SAP GUI**
(with visible mouse where enabled).

## What counts as SUCCESS

| Requirement | Offline twin only | Live GUI |
|-------------|-------------------|----------|
| Multi-table extract / fingerprints | support only | required + GUI |
| Mouse / StartTransaction / fields | **not enough** | **required** |
| Scoreboard `all_success` | only if `SAPILOT_OFFLINE=1` (CI) | product default |
| `true_online` | false | true when session bound + all GUI steps ok |

## Defaults (product)

```bat
set SAPILOT_LIVE_GUI=1
set SAPILOT_FORCE_COM_BIND=1
set SAPILOT_SHOW_MOUSE=1
```

`SAPILOT_OFFLINE=1` is **CI/tests only**. Do not use it to claim product success.

## Run (what you should use)

```bat
start_online_bot.bat
```

or:

```bat
cd C:\Projects\SAP
set SAPILOT_LIVE_GUI=1
set SAPILOT_FORCE_COM_BIND=1
set SAPILOT_SHOW_MOUSE=1
set SAPILOT_LAB=1
set PYTHONPATH=C:\Projects\SAP
python -m sapilot online-health
python -m sapilot online-20 --no-fallback
python -m sapilot super-bot --live-gui
```

## Prerequisites (or GUI will fail loudly — not skip)

1. SAP Logon running  
2. Options → Accessibility & Scripting → **Enable scripting**  
3. RZ11: `sapgui/user_scripting = TRUE`  
4. Logged into **Vista** (or vault `vista` credentials)  

If scripting is off, the bot **fails online** with a clear error. It will not mark GUI-skipped as SUCCESS.
