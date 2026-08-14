"""Display wing — walk SAP GUI cycles in display mode only.

Sibling of the analysis wing. Analysis counts tables. This wing opens the
Enjoy display transactions and drills an existing cycle on the glass.

Never creates. Never changes. Never posts. Create t-codes are a hard refuse.
"""

from sapilot.display.policy import (
    DisplayPolicyError,
    assert_display_tcode,
    is_create_screen,
    remap_to_display,
)
from sapilot.display.catalog import CYCLES, cycle_names, get_cycle

__all__ = [
    "DisplayPolicyError",
    "assert_display_tcode",
    "is_create_screen",
    "remap_to_display",
    "CYCLES",
    "cycle_names",
    "get_cycle",
]
