"""Display-wing choke-point: only display t-codes. Fail closed."""

from __future__ import annotations

import re

from sapilot.exceptions import PolicyViolation


class DisplayPolicyError(PolicyViolation):
    """Create / change / post t-code used in the display wing."""


# Explicit create / change / post / customizing — never open from this wing.
DENY_TCODES = frozenset(
    {
        # Purchasing create/change
        "ME21N",
        "ME22N",
        "ME51N",
        "ME52N",
        "ME31K",
        "ME32K",
        "ME31L",
        "ME32L",
        "ME41",
        "ME47",
        "ME11",
        "ME12",
        "ME01",
        "ME28",
        "ME29N",
        "ME54N",
        "ME59N",
        "ML81N",
        "MIGO",  # defaults to Goods Receipt create
        "MIRO",  # incoming invoice create
        "MIR7",
        # Sales create/change
        "VA01",
        "VA02",
        "VA11",
        "VA12",
        "VA21",
        "VA22",
        "VA31",
        "VA32",
        "VA41",
        "VA42",
        "VL01N",
        "VL02N",
        "VF01",
        "VF02",
        "VF04",
        "VF11",
        "VK11",
        "VK12",
        # Master create/change
        "MM01",
        "MM02",
        "XK01",
        "XK02",
        "MK01",
        "MK02",
        "FK01",
        "FK02",
        "XD01",
        "XD02",
        "VD01",
        "VD02",
        "FD01",
        "FD02",
        "FD32",  # credit change
        "BP",  # can create; use XK03/XD03
        "XKN1",
        # FI / CO post
        "FB01",
        "FB50",
        "FB60",
        "FB70",
        "F-02",
        "F-28",
        "F-53",
        "F-32",
        "F110",
        "F150",
        "F-44",
        "KB11N",
        "KB21N",
        "KB31N",
        "KS01",
        "KS02",
        "KA01",
        "KA02",
        "CO01",
        "CO02",
        "COR1",
        "COR2",
        "CK11N",
        "CK12N",
        "CK24",
        "CK40N",
        "CKMLCP",
        "KKS1",
        "KKS2",
        "KKAX",
        "KKAO",
        # Customizing / maintain
        "SM30",
        "SM31",
        "SM34",
        "SPRO",
        "SE38",  # execute can write
        "SE80",
        "SE37",  # test/execute BAPI
        "OKKN",
        "OKK4",
        "OKTZ",
        "OX02",
        "OX10",
        "OX08",
        "OX09",
        "OBY6",
        "EC01",
        "BD87",
        "WE19",
        "SM35",
        "FTR_CREATE",
    }
)

# Create → display twin. Asking for ME21N in this wing is a refuse, not a remap
# at the glass (we never open the create t-code). Callers may *suggest* the twin.
REMAP = {
    "ME21N": "ME23N",
    "ME22N": "ME23N",
    "ME51N": "ME53N",
    "ME52N": "ME53N",
    "ME31K": "ME33K",
    "ME32K": "ME33K",
    "ME31L": "ME33L",
    "ME32L": "ME33L",
    "VA01": "VA03",
    "VA02": "VA03",
    "VL01N": "VL03N",
    "VL02N": "VL03N",
    "VF01": "VF03",
    "VF02": "VF03",
    "MM01": "MM03",
    "MM02": "MM03",
    "XK01": "XK03",
    "XK02": "XK03",
    "XD01": "XD03",
    "XD02": "XD03",
    "MIGO": "MB03",
    "MIRO": "MIR4",
    "FB01": "FB03",
    "FB50": "FB03",
    "CO01": "CO03",
    "CO02": "CO03",
    "CK11N": "CK13N",
    "CK12N": "CK13N",
    "KS01": "KS03",
    "KS02": "KS03",
    "KA01": "KA03",
    "KA02": "KA03",
    "FD32": "FD33",
    "FTR_CREATE": "FTR_DISPLAY",
}

# Fail-closed allow. Unknown t-code is refused.
ALLOW_TCODES = frozenset(
    {
        "SESSION_MANAGER",
        # Table / dictionary display
        "SE16N",
        "SE16",
        "SE11",
        "SE12",
        "SE17",
        # Purchasing display / lists
        "ME23N",
        "ME53N",
        "ME2N",
        "ME2L",
        "ME2M",
        "ME2K",
        "ME33K",
        "ME33L",
        "ME43",
        "ME3N",
        "ME5A",
        "ML84",
        "MB03",
        "MB51",
        "MB52",
        "MIR4",
        "MIR5",
        "MIR6",
        "FBL1N",
        # Master display
        "MM03",
        "XK03",
        "MK03",
        "FK03",
        "XD03",
        "VD03",
        "FD03",
        "FD33",
        # Sales display / lists
        "VA03",
        "VA05",
        "VA13",
        "VA23",
        "VA33",
        "VA43",
        "VL03N",
        "VL06O",
        "VF03",
        "VF05",
        "FBL5N",
        "VB03",
        # FI / CO display
        "FB03",
        "FBL3N",
        "FAGLB03",
        "FS03",
        "KS03",
        "KA03",
        "KL03",
        "KB13N",
        "KSB1",
        "KOB1",
        "CO03",
        "COR3",
        "CK13N",
        "CKM3",
        "CKM3N",
        "CK13",
        "CK80",
        "KKBC_ORD",
        # Integration / output display
        "WE02",
        "WE05",
        "NACE",  # display config; do not save
        # Treasury display (auth may still deny on glass)
        "TPM13",
        "FTR_DISPLAY",
        "TM_53",
        # Other-module display (examples — any process)
        "QA03",
        "QA13",
        "QE03",
        "IE03",
        "IL03",
        "IW23",
        "IW33",
        "IW13",
        "LS03N",
        "LT21",
        "LT27",
        "LX03",
        "CJ03",
        "CJ13",
        "CN43N",
        "CJI3",
        "PA20",
        "PPOSE",
        "FARR_RAI_MON",
    }
)

_CREATE_TITLE = re.compile(
    r"\b(create|ändern|change|post|park|hold|goods receipt|enter incoming invoice|"
    r"incoming invoice|maintain|customizing)\b",
    re.I,
)
_DISPLAY_TITLE = re.compile(
    r"\b(display|anzeigen|list|general table display|document overview)\b",
    re.I,
)


def _norm(tcode: str) -> str:
    raw = (tcode or "").strip().lstrip("/").upper()
    if raw.startswith("N") and len(raw) > 1 and not raw[1:].isdigit():
        # /nME23N already stripped to NME23N — don't strip ME23N
        if raw.startswith("NME") or raw.startswith("NVA") or raw.startswith("NCK"):
            raw = raw[1:]
    if raw.startswith("N") and len(raw) > 4:
        raw = raw[1:]
    return raw


def remap_to_display(tcode: str) -> str:
    """What the display twin would be. Does not authorize opening either."""
    return REMAP.get(_norm(tcode), _norm(tcode))


def assert_display_tcode(tcode: str) -> str:
    """Return the normalized t-code or raise. Never remaps a create into a silent open."""
    code = _norm(tcode)
    if not code:
        raise DisplayPolicyError("empty t-code")
    if code in DENY_TCODES:
        twin = REMAP.get(code)
        hint = f" Use display twin {twin}." if twin else ""
        raise DisplayPolicyError(
            f"Display wing refuses {code} (create/change/post/customizing).{hint}"
        )
    if code not in ALLOW_TCODES:
        twin = REMAP.get(code)
        hint = f" Closest display twin: {twin}." if twin else ""
        raise DisplayPolicyError(
            f"Display wing fail-closed: {code} is not on the display allow-list.{hint}"
        )
    return code


def is_create_screen(title: str, status: str = "") -> bool:
    """True if the glass looks like a write screen. Leave immediately."""
    blob = f"{title or ''} {status or ''}"
    # "Stock Transp. Order 100011 Created by pranali" is a display of an
    # existing document, not a create screen.
    blob_cmp = re.sub(r"\bcreated by\b", "", blob, flags=re.I)
    if _CREATE_TITLE.search(blob_cmp) and not _DISPLAY_TITLE.search(title or ""):
        return True
    # Enjoy create titles often start with Create
    t = (title or "").strip().lower()
    return t.startswith("create ") or t.startswith("enter ") or t.startswith("post ")


def is_display_screen(title: str) -> bool:
    return bool(_DISPLAY_TITLE.search(title or ""))
