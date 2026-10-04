from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4

from app.agents.analysis import analyze, estimate_uncertainty
from app.agents.experiment_runner import run_experiment
from app.agents.literature import review_evidence_quality, run_literature_agent
from app.agents.planner import TEST_COSTS, recommend_next, select_test
from app.agents.portfolio import classify, decide
from app.agents.red_team import run_red_team
from app.agents.safety import validate_safety
from app.models.schemas import (
    ApprovalStatus,
    Decision,
    Detection,
    ExperimentSpec,
    PortfolioDecision,
    ResearchEvent,
)
from app.orchestration.state import TriageState
from app.services.data_store import load_detections

DEFAULT_BUDGET = 10


class _Recorder:
    """Appends events to the run's research record, chaining each to the previous event for the detection."""

    def __init__(self, run: "RunState", detection_id: str):
        self.run = run
        self.detection_id = detection_id
        self.last_event_id: str | None = None

    def __call__(self, agent: str, action: str, output: dict, confidence: str = "MEDIUM") -> ResearchEvent:
        ev = ResearchEvent(
            event_id=str(uuid4()),
            detection_id=self.detection_id,
            agent=agent,
            action=action,
            input_reference=self.last_event_id or "detection",
            output=output,
            confidence=confidence,
            citations=output.get("sources", []),
            parent_event_id=self.last_event_id,
            run_id=self.run.run_id,
        )
        self.run.events.append(ev)
        self.last_event_id = ev.event_id
        return ev


@dataclass
class RunState:
    run_id: str
    seed: int
    budget: int
    started_at: float
    mode: str = "deterministic"
    events: list[ResearchEvent] = field(default_factory=list)
    decisions: dict[str, PortfolioDecision] = field(default_factory=dict)
    # Agentic runs keep per-detection state between tool calls.
    states: dict[str, TriageState] = field(default_factory=dict)
    recorders: dict[str, _Recorder] = field(default_factory=dict)


RUNS: dict[str, RunState] = {}


def _refresh(state: TriageState) -> None:
    state.uncertainty = estimate_uncertainty(state)


def _run_planned_test(run: RunState, state: TriageState, test: str, record: _Recorder) -> None:
    det = state.detection
    if test == "robustness_test":
        robustness, experiments = run_red_team(run.run_id, det, run.seed, state.scorecard.recall)
        for exp in experiments:
            ev = record("experiment_runner", "robustness_variant", exp.model_dump(mode="json"))
            state.evidence_ids.append(ev.event_id)
        ev = record("red_team", "robustness_test", robustness.model_dump(), robustness.confidence.value)
        state.evidence_ids.append(ev.event_id)
        state.robustness = robustness
        state.scorecard = state.scorecard.model_copy(update={"robustness_degradation": robustness.reference_degradation})
    elif test in ("redundancy_check", "alert_volume_test"):
        spec = ExperimentSpec(detection_id=det.detection_id, experiment_type=test, random_seed=run.seed)
        result = run_experiment(run.run_id, spec, det)
        ev = record("experiment_runner", test, result.model_dump(mode="json"))
        state.evidence_ids.append(ev.event_id)
        if test == "redundancy_check":
            update = {"redundancy_overlap": result.metrics["sibling_overlap"]}
        else:
            update = {"alerts_per_user_day": result.metrics["alerts_per_user_day"]}
        state.scorecard = state.scorecard.model_copy(update=update)
    elif test == "evidence_quality_review":
        degradation = state.robustness.reference_degradation if state.robustness else None
        review = review_evidence_quality(state.literature, degradation)
        ev = record("literature", "evidence_quality_review", review)
        state.evidence_ids.append(ev.event_id)
        state.evidence_reviewed = True
    else:
        raise ValueError(f"unplannable test {test}")


def _triage(run: RunState, det: Detection) -> PortfolioDecision:
    record = _Recorder(run, det.detection_id)
    state = TriageState(detection=det, remaining_budget=run.budget)

    lit = run_literature_agent(det.detection_id)
    state.literature = lit
    state.remaining_budget -= TEST_COSTS["literature_check"]
    state.tests_run.append("literature_check")
    state.evidence_ids.append(record("literature", "literature_check", lit.model_dump(mode="json"), lit.confidence.value).event_id)

    spec = ExperimentSpec(detection_id=det.detection_id, experiment_type="efficacy_test", random_seed=run.seed)
    baseline = run_experiment(run.run_id, spec, det)
    state.remaining_budget -= TEST_COSTS["efficacy_test"]
    state.tests_run.append("efficacy_test")
    state.evidence_ids.append(record("experiment_runner", "efficacy_test", baseline.model_dump(mode="json")).event_id)
    state.scorecard = analyze(baseline)
    state.sample_size = baseline.raw_results["tp"] + baseline.raw_results["fn"]
    _refresh(state)
    record("analysis", "scorecard", {"scorecard": state.scorecard.model_dump(), "uncertainty": state.uncertainty.model_dump()})

    provisional: Decision | None = None
    expected_next: str | None = None
    previous_uncertainty = state.uncertainty.value
    while True:
        current, rationale = classify(state)
        if current != provisional:
            record("portfolio", "provisional_decision", {"decision": current.value, "rationale": rationale, "uncertainty": state.uncertainty.value})
        plan = select_test(state, current)
        plan_event = record("planner", "select_test", plan.model_dump(mode="json"))
        if provisional is not None and plan.selected_test != expected_next:
            record(
                "planner",
                "ADAPTATION_EVENT",
                {
                    "reason": f"evidence from {state.tests_run[-1]} changed the plan",
                    "provisional_decision_before": provisional.value,
                    "provisional_decision_after": current.value,
                    "uncertainty_before": previous_uncertainty,
                    "uncertainty_after": state.uncertainty.value,
                    "discarded_test": expected_next,
                    "scheduled_test": plan.selected_test,
                    "planner_event_id": plan_event.event_id,
                },
                "HIGH",
            )
        if plan.selected_test is None:
            break
        provisional, expected_next, previous_uncertainty = current, plan.planned_follow_up, state.uncertainty.value
        state.remaining_budget = plan.remaining_budget
        _run_planned_test(run, state, plan.selected_test, record)
        state.tests_run.append(plan.selected_test)
        _refresh(state)
        record("analysis", "scorecard_update", {"after_test": plan.selected_test, "scorecard": state.scorecard.model_dump(), "uncertainty": state.uncertainty.model_dump()})

    final, _ = classify(state)
    decision = decide(run.run_id, state, recommend_next(state, final))
    record("portfolio", "decision", decision.model_dump(mode="json"), decision.confidence.value)
    safety = validate_safety(decision)
    record("safety", "safety_gate", safety.model_dump(mode="json"))
    return decision


def replay_run(seed: int = 42, budget: int = DEFAULT_BUDGET) -> RunState:
    """Execute a full triage run without registering it."""
    run = RunState(run_id=str(uuid4()), seed=seed, budget=budget, started_at=time.time())
    for det in load_detections():
        run.decisions[det.detection_id] = _triage(run, det)
    return run


def execute_run(seed: int = 42, max_test_cost: int = DEFAULT_BUDGET) -> str:
    run = replay_run(seed, max_test_cost)
    RUNS[run.run_id] = run
    return run.run_id


def get_run(run_id: str):
    return RUNS.get(run_id)


def latest_run() -> RunState | None:
    return next(reversed(RUNS.values()), None)


def get_timeline(detection_id: str, run_id: str | None = None) -> list[ResearchEvent]:
    run = get_run(run_id) if run_id else latest_run()
    if run is None:
        return []
    return [e for e in run.events if e.detection_id == detection_id]


def record_approval(decision_id: str, approved: bool, reviewer: str) -> PortfolioDecision:
    for run in RUNS.values():
        for det_id, decision in run.decisions.items():
            if decision.decision_id != decision_id:
                continue
            if not decision.requires_human_approval:
                raise ValueError("decision does not require human approval")
            if decision.approval_status != ApprovalStatus.PENDING:
                raise ValueError(f"decision already {decision.approval_status.value}")
            status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            updated = decision.model_copy(update={"approval_status": status})
            run.decisions[det_id] = updated
            parent = next((e.event_id for e in reversed(run.events) if e.detection_id == det_id), None)
            run.events.append(
                ResearchEvent(
                    event_id=str(uuid4()),
                    detection_id=det_id,
                    agent="human_reviewer",
                    action="approval",
                    input_reference=decision_id,
                    output={"decision_id": decision_id, "reviewer": reviewer, "status": status.value},
                    confidence="HIGH",
                    citations=[],
                    parent_event_id=parent,
                    run_id=run.run_id,
                )
            )
            return updated
    raise LookupError(decision_id)
