"""Pack smoke: refuse create/change/post in several modules; allow display twins."""
from sapilot.display.policy import DisplayPolicyError, assert_display_tcode

# Examples from different modules — not a product list.
CREATE = "ME21N VA01 VL01N VF01 MIGO MIRO FB50 CK11N CO01 MM01 XK01 XD01".split()
DISPLAY = "ME23N VA03 VL03N VF03 MB03 MIR4 FB03 CK13N CO03 MM03 XK03 XD03 SE16N".split()

for t in CREATE:
    try:
        assert_display_tcode(t)
    except DisplayPolicyError:
        print("  refused", t)
        continue
    raise SystemExit(f"display wing allowed create/change {t}")

for t in DISPLAY:
    assert_display_tcode(t)
    print("  display-ok", t)
