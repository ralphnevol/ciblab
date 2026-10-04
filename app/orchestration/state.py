from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import (
    Detection,
    DetectionScorecard,
    ExperimentResult,
    LiteratureEvidence,
    PortfolioDecision,
    RobustnessResult,
    UncertaintyEstimate,
)


@dataclass
class TriageState:
    """Evidence accumulated for one detection; the shared input every agent reasons over."""

    detection: Detection
    remaining_budget: int
    literature: LiteratureEvidence | None = None
    evidence_reviewed: bool = False
    scorecard: DetectionScorecard | None = None
    sample_size: int = 0
    robustness: RobustnessResult | None = None
    uncertainty: UncertaintyEstimate | None = None
    tests_run: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    # Used by agentic runs, where LLM agents drive the loop through tool calls.
    pending_test: str | None = None
    has_plan: bool = False
    planned_follow_up: str | None = None
    reference_provisional: str | None = None
    evasion_variants: list[ExperimentResult] = field(default_factory=list)
    decision: PortfolioDecision | None = None
