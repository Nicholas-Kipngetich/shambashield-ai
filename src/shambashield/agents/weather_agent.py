"""Weather Intelligence Agent — explains the deterministic weather findings.

The hazard tier is already decided by rules; this agent ONLY explains it.
When Bedrock is unavailable the baseline rule text is returned, flagged
degraded, so the UI can show the "rule-based advisory" banner.
"""

from __future__ import annotations

from ..contracts import WeatherFindings
from .scaffolding import NEVER_INVENT, Narration, run_agent

SYSTEM = (
    "You are ShambaShield's Weather Intelligence Agent for Kenyan smallholder "
    "farmers. Explain the given forecast hazards plainly in 2-3 sentences. " + NEVER_INVENT
)


def baseline(findings: WeatherFindings) -> str:
    """Rule-based summary used when the LLM is unavailable."""
    if not findings.hazards:
        return (
            f"No weather hazards were detected for {findings.snapshot.county} "
            "with the current thresholds."
        )
    parts = [f"{h.severity} {h.kind.replace('_', ' ')}" for h in findings.hazards]
    return (
        f"Weather outlook for {findings.snapshot.county}: "
        + ", ".join(parts)
        + ". See the listed evidence for measured values."
    )


def run(findings: WeatherFindings, model=None) -> Narration:
    """Narrate the findings; degrade to the baseline text on any problem."""
    if model is None:
        return Narration(text=baseline(findings), degraded=True, error="Bedrock not configured")
    prompt = (
        f"County: {findings.snapshot.county}\n"
        f"Days of forecast: {len(findings.snapshot.days)}\n"
        f"Hazards (kind, severity, evidence):\n{_payload(findings)}\n\n"
        "Explain what this means for the farm in 2-3 plain sentences."
    )
    narration = run_agent(model, SYSTEM, prompt)
    if narration.degraded or not narration.text:
        return Narration(text=baseline(findings), degraded=True, error=narration.error)
    return narration


def _payload(findings: WeatherFindings) -> str:
    import json

    from .scaffolding import hazards_payload

    return (
        json.dumps(json.loads(hazards_payload(findings.hazards)), indent=1)
        if findings.hazards
        else "none"
    )
