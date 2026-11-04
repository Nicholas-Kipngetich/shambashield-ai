"""Deterministic selection of curated actions for one farm situation.

Rules (docs/PHASE1_ARCHITECTURE.md §6.5):
- Every returned `action_id` exists in data/actions.yaml — the catalog bounds
  what can ever be recommended.
- Matching is explicit: an action must cover at least one reported hazard,
  the farmer's crop (or "any") and the farmer's stage (or "any").
- Ranking is deterministic: urgency (now > this_week > monitor), then cost
  (free > low > medium), then catalog order. No LLM is involved at this stage;
  the planner agent later only ranks/phrases within these boundaries.
"""

from __future__ import annotations

from ..action_catalog import catalog_version, load_catalog
from ..contracts import (
    ActionPlan,
    CropRiskAssessment,
    RecommendedAction,
    WeatherFindings,
)
from .hazard_rules import hazard_kind_label

_URGENCY_RANK = {"now": 0, "this_week": 1, "monitor": 2}
_COST_RANK = {"free": 0, "low": 1, "medium": 2}
_SEVERITY_RANK = {"low": 0, "moderate": 1, "high": 2}


def plan_actions(
    findings: WeatherFindings,
    assessment: CropRiskAssessment,
    max_actions: int = 5,
) -> ActionPlan:
    """Pick the best curated actions for this finding/crop/stage combination."""
    catalog = load_catalog()
    hazard_kinds = {h.kind for h in findings.hazards}
    hazard_severities = {h.kind: h.severity for h in findings.hazards}
    worst_severity = max((_SEVERITY_RANK.get(s, 0) for s in hazard_severities.values()), default=0)

    def _rank(entry: dict) -> tuple[int, int, int, str]:
        urgency = str(entry.get("urgency"))
        cost = str(entry.get("cost_tier"))
        return (
            _URGENCY_RANK[urgency],
            _COST_RANK[cost],
            -worst_severity,
            str(entry.get("id")),
        )

    matched: list[tuple[dict, tuple[int, int, int, str]]] = []
    for entry in catalog.values():
        if not (hazard_kinds & set(entry.get("hazards", []))):
            continue
        crops = list(entry.get("crops", []))
        if "any" not in crops and assessment.crop not in crops:
            continue
        stages = list(entry.get("stages", []))
        if "any" not in stages and assessment.stage not in stages:
            continue
        matched.append((entry, _rank(entry)))

    matched.sort(key=lambda pair: pair[1])
    selected = matched[:max_actions]
    deferred = [str(entry["title_en"]) for entry, _ in matched[max_actions:]]

    # If there were outstanding hazards that no curated action covers, say so.
    covered = set()
    for entry, _rank in matched:
        covered |= set(entry.get("hazards", []))
    uncovered = hazard_kinds - covered
    assumptions = [
        f"Catalog version {catalog_version()}; crops and stages matched "
        f"explicitly against curated entries."
    ]
    if uncovered:
        assumptions.append(
            "No curated action covers: "
            + ", ".join(sorted(hazard_kind_label(k) for k in uncovered))
        )

    actions = [
        RecommendedAction(
            action_id=str(entry["id"]),
            title=str(entry["title_en"]),
            why=str(entry["why"]),
            when=str(entry["when"]),
            cost_tier=str(entry["cost_tier"]),  # type: ignore[arg-type]
            urgency=str(entry["urgency"]),  # type: ignore[arg-type]
        )
        for entry, _rank in selected
    ]
    return ActionPlan(actions=actions, deferred=deferred, assumptions=assumptions)


__all__ = ["plan_actions"]
