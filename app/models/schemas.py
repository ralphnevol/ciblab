from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Decision(str, Enum):
    KEEP = "KEEP"
    DECOMMISSION = "DECOMMISSION"
    INVESTIGATE = "INVESTIGATE"


class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Detection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str
    name: str
    description: str
    source: str = "synthetic"
    logic: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_behaviour: str


class LiteratureEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str
    sources: list[str]
    evidence_summary: str
    supporting_claims: list[str]
    contradicting_claims: list[str]
    confidence: Confidence
    evidence_quality: float
    timestamp: datetime = Field(default_factory=utcnow)


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str
    experiment_type: Literal[
        "literature_check",
        "efficacy_test",
        "alert_volume_test",
        "redundancy_check",
        "robustness_test",
        "evidence_quality_review",
    ]
    random_seed: int
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    detection_id: str
    experiment_type: str
    random_seed: int
    parameters: dict[str, Any]
    metrics: dict[str, float]
    raw_results: dict[str, Any]
    execution_time: float
    timestamp: datetime = Field(default_factory=utcnow)


class DetectionScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    alert_volume: float
    alerts_per_user_day: float
    redundancy_overlap: float
    robustness_degradation: float


class RobustnessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline_score: float
    adapted_scores: list[float]
    degradation_curve: list[float]
    breaking_parameters: dict[str, Any]
    explanation: str
    confidence: Confidence


class PlannerDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_test: str
    remaining_budget: int
    rejected_alternatives: list[dict[str, Any]]
    estimated_value: float
    rationale: str


class PortfolioDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str
    decision: Decision
    rationale: str
    confidence: Confidence
    evidence_ids: list[str]
    scorecard: DetectionScorecard
    uncertainty: float
    recommended_next_test: str | None
    requires_human_approval: bool


class SafetyOutcome(str, Enum):
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"
    BLOCKED = "BLOCKED"


class SafetyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str
    status: SafetyOutcome
    reasons: list[str]


class ResearchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    detection_id: str
    agent: str
    action: str
    input_reference: str
    output: dict[str, Any]
    confidence: str
    citations: list[str]
    parent_event_id: str | None = None
    run_id: str


class ManualBaselineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str
    decision: Decision
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    rationale: str


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accuracy: float
    confusion_matrix: dict[str, dict[str, int]]
    time_per_detection: float
    decisions_per_hour: float
    speedup: float
    justification_quality: float
    adaptation_count: int
    reproducibility_result: bool
