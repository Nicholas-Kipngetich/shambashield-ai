"""Action Planner Agent — explains the curated plan choice.

The plan itself is already selected deterministically from the catalog
(tools/action_planner.py); this agent explains WHY this order makes sense.
It may not add, drop or reorder actions.
"""

from __future__ import annotations

from ..contracts import ActionPlan
from .scaffolding import NEVER_INVENT, Narration, run_agent

SYSTEM = (
    "You are ShambaShield's Action Planner Agent. Explain briefly why the "
    "given prioritised actions suit the farm situation right now, in 2-3 "
    "plain sentences. " + NEVER_INVENT
)


def baseline(plan: ActionPlan) -> str:
    if not plan.actions:
        return "No curated actions matched this situation; keep monitoring."
    return (
        "Follow the prioritised actions in order: "
        + "; ".join(a.title for a in plan.actions[:3])
        + "."
    )


def run(plan: ActionPlan, model=None) -> Narration:
    if model is None:
        return Narration(text=baseline(plan), degraded=True, error="Bedrock not configured")
    items = "\n".join(
        f"- {a.action_id}: {a.title} (urgency {a.urgency}, cost {a.cost_tier})"
        for a in plan.actions
    )
    prompt = (
        f"Crop risk tier: {plan.assumptions[0] if plan.assumptions else ''}\n"
        f"Trial actions:\n{items}\n\n"
        "Explain why this order of actions makes sense for the farmer now."
    )
    narration = run_agent(model, SYSTEM, prompt)
    if narration.degraded or not narration.text:
        return Narration(text=baseline(plan), degraded=True, error=narration.error)
    return narration


__all__ = ["baseline", "run"]  # _plant_baseline unused intentionally
