from __future__ import annotations

import pytest

from sapilot.brain.governor import Governor
from sapilot.exceptions import BudgetExceeded, LoopDetected
from sapilot.schemas import BudgetState


def test_budget_steps():
    g = Governor(BudgetState(max_steps=2))
    g.tick_step()
    g.tick_step()
    with pytest.raises(BudgetExceeded):
        g.tick_step()


def test_novelty_loop():
    g = Governor(BudgetState(max_steps=50), novelty_window=3)
    with pytest.raises(LoopDetected):
        for _ in range(3):
            g.observe_state({"x": 1})
