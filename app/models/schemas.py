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


class ResearchQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    question: str
    target: str
    constraints: list[str] = Field(default_factory=list)


class ResearchCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    title: str
    question: ResearchQuestion
    scenario: str = "synthetic-binary-01"
    status: Literal["created", "running", "completed", "blocked"] = "created"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    case_id: str
    kind: Literal["cti", "literature", "binary_finding", "local"]
    claim: str
    source: str
    citation: str
    confidence: float = Field(ge=0, le=1)
    tool: str


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_id: str
    case_id: str
    statement: str
    evidence_refs: list[str]
    confidence: float = Field(ge=0, le=1)
    unknowns: list[str]


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


class ExperimentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str
    case_id: str
    hypothesis_refs: list[str]
    expected_learning: float
    cost: int
    feasibility: float = Field(ge=0, le=1)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @property
    def priority(self) -> float:
        return self.expected_learning * self.feasibility / max(1, self.cost)


class ResearchDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    selected_experiment: str | None
    rationale: str
    updated_uncertainties: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False


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
    detection_id: str = ""
    case_id: str | None = None
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


# ── Fuzzing Lab Schemas ──────────────────────────────────────────────


class FuzzTarget(BaseModel):
    """Description of the binary or program under test."""
    model_config = ConfigDict(extra="forbid")
    target_id: str
    name: str
    description: str
    input_format: str = "stdin"
    known_constraints: list[str] = Field(default_factory=list)
    source: Literal["synthetic", "public"] = "synthetic"


class SeedEntry(BaseModel):
    """A single seed file in the corpus."""
    model_config = ConfigDict(extra="forbid")
    filename: str
    content_b64: str
    mutation_strategy: str
    rationale: str


class SeedCorpus(BaseModel):
    """Hypothesis + generated seeds from the Seed Agent."""
    model_config = ConfigDict(extra="forbid")
    case_id: str
    target_id: str
    hypothesis: str
    seeds: list[SeedEntry]
    confidence: float = Field(ge=0, le=1)
    timestamp: datetime = Field(default_factory=utcnow)


class FuzzExperimentSpec(BaseModel):
    """Specification for a fuzzing experiment."""
    model_config = ConfigDict(extra="forbid")
    experiment_id: str
    case_id: str
    target_id: str
    corpus_strategy: str
    duration_seconds: int = 30
    random_seed: int = 42
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_learning: float = Field(ge=0, le=1)
    cost: int = 1
    feasibility: float = Field(ge=0, le=1, default=0.9)

    @property
    def priority(self) -> float:
        return self.expected_learning * self.feasibility / max(1, self.cost)


class CrashReport(BaseModel):
    """A single crash found during fuzzing."""
    model_config = ConfigDict(extra="forbid")
    crash_id: str
    input_filename: str
    input_hex: str
    signal: int
    exit_code: int
    stderr_snippet: str
    reproduced: bool = False
    timestamp: datetime = Field(default_factory=utcnow)


class TriageReport(BaseModel):
    """Triage analysis of a reproduced crash."""
    model_config = ConfigDict(extra="forbid")
    crash_id: str
    cwe_id: str
    cwe_name: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    root_cause: str
    input_hex: str
    hypothesis_confirmed: bool
    requires_human_approval: bool = True


class FuzzDiscovery(BaseModel):
    """Final consolidated scientific discovery from the fuzzing lab."""
    model_config = ConfigDict(extra="forbid")
    case_id: str
    question: str
    hypothesis: str
    hypothesis_confirmed: bool
    experiments_proposed: int
    experiment_selected: str
    crashes_found: int
    triage_results: list[TriageReport]
    adaptation_event: str
    scientific_conclusion: str
    speedup_vs_manual: float
    reproducibility_seed: int
    timestamp: datetime = Field(default_factory=utcnow)
