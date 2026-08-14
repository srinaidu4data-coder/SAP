"""Cut a sitting that is not making progress. One stuck see/goto cannot own the glass."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, TypeVar

T = TypeVar("T")

STEP_SECONDS = 22
SITTING_SECONDS = 90


def run_cut(fn: Callable[[], T], seconds: float, *, on_cut: T) -> T:
    """Run fn. If it does not return in `seconds`, give up. Do not wait forever."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=max(3.0, float(seconds)))
        except FuturesTimeout:
            return on_cut
        except Exception as e:
            if isinstance(on_cut, dict):
                rec = dict(on_cut)
                rec["error"] = str(e)[:160]
                return rec  # type: ignore[return-value]
            raise


def probe_tcodes(codes: list[str], *, shot_dir: str, step_s: float = STEP_SECONDS) -> dict[str, Any]:
    """Open at most two display t-codes. Cut each if the glass does not answer."""
    from sapilot.autobot.operator import HumanEyesHands
    from sapilot.display.policy import DisplayPolicyError, assert_display_tcode
    from sapilot.learn.mind import say
    from sapilot.product.navigate import back_out, classify, goto_checked

    names = [(c or "").strip().upper() for c in codes if (c or "").strip()][:2]
    hh = HumanEyesHands(shot_dir=shot_dir)
    visits: list[dict[str, Any]] = []
    t0 = time.time()

    def _title() -> str:
        try:
            return hh._title() or ""
        except Exception as e:
            return f"(no title: {e})"

    def _cut_glass(why: str) -> None:
        say(why, action="cut")
        try:
            back_out(hh, steps=1)
        except Exception:
            pass

    title0 = run_cut(_title, 5, on_cut="")
    say(f"Probe start. Glass: {title0 or 'unknown'}. Two t-codes only.", action="probe")

    for code in names:
        if time.time() - t0 > SITTING_SECONDS:
            visits.append({"tcode": code, "ok": False, "cut": True, "note": "sitting budget gone"})
            say("Sitting budget gone. I stop. I will not start another t-code.", code, "cut")
            break
        try:
            assert_display_tcode(code)
        except DisplayPolicyError as e:
            visits.append({"tcode": code, "ok": False, "cut": False, "note": str(e)})
            continue

        say(f"Trying {code}. If the glass does not answer in {int(step_s)}s I cut.", code, "goto")
        nav = run_cut(
            lambda c=code: goto_checked(hh, c, retries=0),
            step_s,
            on_cut={"ok": False, "cut": True, "title": _title(), "detail": "goto timeout", "expect_ok": False},
        )
        title = (nav.get("title") if isinstance(nav, dict) else "") or _title()
        rec = classify(title, expect=code)
        ok = bool(isinstance(nav, dict) and nav.get("ok") and rec.get("expect_ok"))
        cut = bool(isinstance(nav, dict) and nav.get("cut"))
        if cut or not ok:
            _cut_glass(f"{code} stuck or wrong screen ({title or 'no title'}). Cut. Next path.")
        else:
            say(f"{code} opened: {title}. One look, then leave.", code, "ok")
        try:
            view = run_cut(lambda c=code: hh.see(f"probe_{c.lower()}"), min(step_s, 18), on_cut=None)
        except Exception:
            view = None
        visits.append(
            {
                "tcode": code,
                "ok": ok,
                "cut": cut or (view is None and not ok),
                "title": title,
                "kind": rec.get("kind"),
                "shot": str(view.path) if view and getattr(view, "path", None) else None,
                "note": (nav.get("detail") if isinstance(nav, dict) else "") or title,
            }
        )
        try:
            back_out(hh, steps=1)
        except Exception:
            pass

    return {
        "ok": any(v.get("ok") for v in visits),
        "visits": visits,
        "seconds": round(time.time() - t0, 1),
        "cut": any(v.get("cut") for v in visits),
    }
