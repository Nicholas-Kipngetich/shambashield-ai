"""Agents package: specialists + orchestrator (agents-as-tools pattern)."""

from __future__ import annotations

from .orchestrator import DISCLAIMER, PipelineResult, run_shambashield
from .scaffolding import Narration, build_model, run_agent

__all__ = [
    "DISCLAIMER",
    "Narration",
    "PipelineResult",
    "build_model",
    "run_agent",
    "run_shambashield",
]
