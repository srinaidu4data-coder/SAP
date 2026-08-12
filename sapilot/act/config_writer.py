"""T1-only config writer — transport-scoped, diff + reversal script."""

from __future__ import annotations

from sapilot.exceptions import PolicyViolation
from sapilot.policy.tier import TierContext
from sapilot.schemas import ConfigDiff, Tier


class ConfigWriter:
    TRANSPORT = "SAPILOT_AUTOCFG"

    def __init__(self, tier_ctx: TierContext):
        self.tier_ctx = tier_ctx
        self.diffs: list[ConfigDiff] = []

    def propose(
        self,
        table: str,
        key: dict[str, str],
        field: str,
        before: str | None,
        after: str | None,
        justification: str,
    ) -> ConfigDiff:
        reversal = (
            f"-- reversal for {table} {key} {field}\n"
            f"-- set {field} = {before!r} (was proposed {after!r})\n"
        )
        diff = ConfigDiff(
            table=table,
            key=key,
            field=field,
            before=before,
            after=after,
            business_justification=justification,
            transport=self.TRANSPORT,
            reversal_script=reversal,
        )
        self.diffs.append(diff)
        return diff

    def apply(self, diff: ConfigDiff) -> ConfigDiff:
        if self.tier_ctx.tier != Tier.T1_SANDBOX:
            raise PolicyViolation(
                "Config apply only in T1_SANDBOX; use propose in T2",
                tier=self.tier_ctx.tier.value,
                action="applyConfig",
            )
        self.tier_ctx.require("apply_config", action="applyConfig")
        # Actual table update is system-specific (BAPI / custom Z / controlled GUI).
        # We record intent; live systems wire a sanctioned writer here.
        return diff
