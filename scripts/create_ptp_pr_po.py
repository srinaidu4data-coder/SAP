"""
One-pass PTP create on APEX-2023: ME51N PR, then ME21N PO from that PR.

No GR / IR. Run only after Easy Access is visible.

  python scripts/create_ptp_pr_po.py          # wait until SAP is up, then stop
  python scripts/create_ptp_pr_po.py --go     # create PR then PO
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Keys proven on this client (SE16N + posted POs). Do not invent others.
KEYS = {
    "material": "TG10",
    "qty": "10",
    "uom": "PC",
    "plant": "1710",
    "sloc": "171B",
    "deliv": "08/31/2026",
    "price": "10",
    "curr": "USD",
    "vendor": "USSU-VSF01",
    "ekorg": "1710",
    "ekgrp": "002",
    "bukrs": "1710",
    "knttp": "K",
    "kostl": "1710-10",
}

SHOT = os.path.join("data", "runs", "live_ptp_pr_po")


def _bind():
    import win32con
    import win32gui

    from sapilot.connect.hwnd_input import bind_session

    sess = bind_session()
    win32gui.ShowWindow(sess.hwnd, win32con.SW_MAXIMIZE)
    time.sleep(0.3)
    return sess


def wait_for_session(timeout: float = 180.0) -> None:
    from sapilot.connect.hwnd_input import SessionNotFound, list_sessions

    deadline = time.time() + timeout
    while time.time() < deadline:
        if list_sessions():
            sess = _bind()
            print(f"READY  hwnd={sess.hwnd} pid={sess.pid}  {sess.title}")
            return
        time.sleep(2)
    raise SystemExit("No SAP_FRONTEND_SESSION. Log on to APEX-2023 first.")


def goto(op, tcode: str, shot: str) -> str:
    from sapilot.autobot.vision_operator import goto_transaction

    path = goto_transaction(op, tcode, shot_name=shot)
    time.sleep(0.4)
    return path


def create_pr(op) -> None:
    """ME51N: K / TG10 / 10 PC / plant 1710 / vendor USSU-VSF01 / PGrp 002."""
    goto(op, "ME51N", "me51n_open")
    # Item Overview chevron (header collapsed on a fresh create)
    op.double_click(0.035, 0.22, settle=0.45)
    op.screenshot("me51n_grid")
    # Account assignment K, then material (same first-row layout as ME21N)
    op.click(0.10, 0.32, settle=0.3)
    op.type(KEYS["knttp"])
    op.key("TAB", settle=0.2)
    op.type(KEYS["material"])
    op.key("TAB", settle=0.2)
    op.key("TAB", settle=0.2)
    op.type(KEYS["qty"])
    op.key("TAB", settle=0.2)
    op.type(KEYS["uom"])
    op.key("TAB", settle=0.2)
    op.type(KEYS["deliv"])
    op.key("TAB", settle=0.2)
    op.key("TAB", settle=0.2)
    op.type(KEYS["plant"])
    op.key("ENTER", settle=1.0)
    op.screenshot("me51n_line")
    # Cost center on Account Assignment tab (appears after K)
    op.click(0.20, 0.75, settle=0.3)
    op.clear()
    op.type(KEYS["kostl"])
    op.screenshot("me51n_cc")
    op.save()
    op.screenshot("me51n_saved")


def create_po(op) -> None:
    """ME21N: vendor + org 1710/002/1710, adopt the PR just created."""
    goto(op, "ME21N", "me21n_open")
    op.click(0.16, 0.165, settle=0.3)
    op.clear()
    op.type(KEYS["vendor"])
    op.key("ENTER", settle=1.2)
    op.double_click(0.06, 0.198, settle=0.4)
    op.click(0.095, 0.238, settle=0.3)
    op.click(0.195, 0.275, settle=0.3)
    op.clear()
    op.type(KEYS["ekorg"])
    op.key("TAB", settle=0.2)
    op.type(KEYS["ekgrp"])
    op.key("TAB", settle=0.2)
    op.type(KEYS["bukrs"])
    op.key("ENTER", settle=0.8)
    op.screenshot("me21n_hdr")
    op.double_click(0.035, 0.48, settle=0.45)
    op.screenshot("me21n_grid")
    op.save()
    op.screenshot("me21n_saved")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", action="store_true", help="Create PR then PO")
    args = parser.parse_args()
    os.makedirs(SHOT, exist_ok=True)

    print("PTP create = ME51N PR then ME21N PO. No GR/IR.")
    print("Keys:", KEYS)
    wait_for_session()
    if not args.go:
        print("Session is up. Re-run with --go when Easy Access is showing.")
        return 0

    from sapilot.autobot.vision_operator import Op

    sess = _bind()
    op = Op.for_session(SHOT, hwnd=sess.hwnd)
    create_pr(op)
    create_po(op)
    print("Shots:", SHOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
