"""Independent critic reviews each plan pre-execution. BLOCK is binding."""

from __future__ import annotations

import json

from sapilot.brain.router import ModelRouter, Role
from sapilot.schemas import CriticResult, CriticVerdict, PlannedStep, ScreenSnapshot, Tier


class Critic:
    def __init__(self, router: ModelRouter):
        self.router = router

    def review(
        self,
        step: PlannedStep,
        tier: Tier,
        screen: ScreenSnapshot | None,
        goal: str,
    ) -> CriticResult:
        element_ids = sorted(screen.element_ids()) if screen else []
        user = json.dumps(
            {
                "goal": goal,
                "tier": tier.value,
                "plan": step.model_dump(mode="json"),
                "screen_element_ids_sample": element_ids[:200],
                "instruction": (
                    "Return JSON {verdict: APPROVE|REVISE|BLOCK, reasons: string[]}. "
                    "BLOCK if action targets missing ids, violates tier, or is unjustified."
                ),
            },
            default=str,
        )
        raw = self.router.complete(
            Role.CRITIC,
            system="You are an adversarial safety critic for an SAP execution agent.",
            user=user,
        )
        try:
            data = json.loads(raw)
            return CriticResult(
                verdict=CriticVerdict(data.get("verdict", "REVISE")),
                reasons=list(data.get("reasons") or []),
            )
        except Exception:
            return CriticResult(verdict=CriticVerdict.REVISE, reasons=[f"Unparseable critic: {raw[:200]}"])
