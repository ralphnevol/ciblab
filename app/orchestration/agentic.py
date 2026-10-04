"""Lab-side service for agentic runs, where Omnigent LLM agents drive triage through tool calls.

The LLM agents choose what to do; this module decides what is allowed. It enforces the
budget, the plan -> execute ordering, the DECOMMISSION approval gate, and keeps sealed
labels and simulator parameters out of reach. All numbers (experiments, scorecards,
uncertainty) are computed here, deterministically, never by the model.
"""

from __future__ import annotations

import time
from uuid import uuid4

from app.agents import portfolio
from app.agents.analysis import analyze, estimate_uncertainty
from app.agents.experiment_runner import run_experiment
from app.agents.planner import PLANNABLE_TESTS, TEST_COSTS
from app.agents.red_team import BREAK_THRESHOLD, REFERENCE_STRENGTH, STRENGTHS
from app.models.schemas import (
    ApprovalStatus,
    Confidence,
    Decision,
    ExperimentSpec,
    LiteratureEvidence,
    PortfolioDecision,
    RobustnessResult,
    SafetyDecision,
    SafetyOutcome,
)
from app.orchestration.lab import RUNS, DEFAULT_BUDGET, RunState, _Recorder
from app.orchestration.state import TriageState
from app.services.data_store import load_detections

AGENTIC_TESTS = ("efficacy_test", *PLANNABLE_TESTS)
DATASET_TESTS = ("efficacy_test", "redundancy_check", "alert_volume_test")
MAX_EVASION_VARIANTS = len(STRENGTHS)


class ToolError(ValueError):
    """A tool call the lab refuses; the message is returned to the calling agent."""


def create_run(seed: int = 42, budget: int = DEFAULT_BUDGET) -> RunState:
    run = RunState(run_id=str(uuid4()), seed=seed, budget=budget, started_at=time.time(), mode="agentic")
    for det in load_detections():
        run.states[det.detection_id] = TriageState(detection=det, remaining_budget=budget)
        run.recorders[det.detection_id] = _Recorder(run, det.detection_id)
    RUNS[run.run_id] = run
    return run


def _get(run_id: str, detection_id: str) -> tuple[RunState, TriageState, _Recorder]:
    run = RUNS.get(run_id)
    if run is None or run.mode != "agentic":
        raise ToolError(f"unknown agentic run {run_id}")
    if detection_id not in run.states:
        raise ToolError(f"unknown detection {detection_id}")
    return run, run.states[detection_id], run.recorders[detection_id]


def _charge(state: TriageState, test: str) -> None:
    cost = TEST_COSTS[test]
    if cost > state.remaining_budget:
        raise ToolError(f"{test} costs {cost} but only {state.remaining_budget} budget remains")
    state.remaining_budget -= cost


def _require_pending(state: TriageState, test: str) -> None:
    if state.pending_test != test:
        raise ToolError(f"{test} was not planned; the planner must select it with record_plan first (pending: {state.pending_test})")


def _require_open(state: TriageState) -> None:
    if state.decision is not None:
        raise ToolError("a decision has already been submitted for this detection")


def _complete_test(state: TriageState, test: str, record: _Recorder) -> None:
    state.tests_run.append(test)
    state.pending_test = None
    if state.scorecard is not None:
        state.uncertainty = estimate_uncertainty(state)
        record(
            "analysis",
            "scorecard_update",
            {"after_test": test, "scorecard": state.scorecard.model_dump(), "uncertainty": state.uncertainty.model_dump()},
        )


def lab_brief(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if run is None or run.mode != "agentic":
        raise ToolError(f"unknown agentic run {run_id}")
    return {
        "run_id": run.run_id,
        "seed": run.seed,
        "budget_per_detection": run.budget,
        "test_costs": TEST_COSTS,
        "decision_criteria": {
            "KEEP": f"F1 >= {portfolio.KEEP_MIN_F1}, FPR <= {portfolio.KEEP_MAX_FPR}, robustness degradation < "
            f"{portfolio.KEEP_MAX_DEGRADATION}, uncertainty < {portfolio.KEEP_MAX_UNCERTAINTY}",
            "DECOMMISSION": f"(precision < {portfolio.DECOMMISSION_MAX_PRECISION} or alerts/user-day > "
            f"{portfolio.DECOMMISSION_MIN_ALERTS_PER_USER_DAY}), F1 < {portfolio.DECOMMISSION_MAX_F1}, uncertainty < "
            f"{portfolio.DECOMMISSION_MAX_UNCERTAINTY}; always requires human approval",
            "INVESTIGATE": "otherwise; must name the next experiment",
        },
        "detections": [
            {
                "detection_id": s.detection.detection_id,
                "name": s.detection.name,
                "description": s.detection.description,
                "logic": s.detection.logic,
                "status": "decided" if s.decision else ("in_progress" if s.tests_run else "not_started"),
            }
            for s in run.states.values()
        ],
    }


def detection_state(run_id: str, detection_id: str) -> dict:
    _, state, _ = _get(run_id, detection_id)
    provisional = portfolio.classify(state)[0].value if state.scorecard is not None else None
    return {
        "detection": state.detection.model_dump(),
        "remaining_budget": state.remaining_budget,
        "tests_run": state.tests_run,
        "tests_available": [t for t in AGENTIC_TESTS if t not in state.tests_run],
        "pending_test": state.pending_test,
        "planned_follow_up": state.planned_follow_up,
        "literature": state.literature.model_dump(mode="json") if state.literature else None,
        "evidence_reviewed": state.evidence_reviewed,
        "scorecard": state.scorecard.model_dump() if state.scorecard else None,
        "uncertainty": state.uncertainty.model_dump() if state.uncertainty else None,
        "robustness": state.robustness.model_dump() if state.robustness else None,
        "evasion_variants_run": [
            {"strength": v.parameters["strength"], "recall": v.metrics["recall"]} for v in state.evasion_variants
        ],
        "rule_based_provisional_decision": provisional,
        "decision": state.decision.model_dump(mode="json") if state.decision else None,
    }


def research_record(run_id: str, detection_id: str) -> list[dict]:
    run, _, _ = _get(run_id, detection_id)
    return [e.model_dump(mode="json") for e in run.events if e.detection_id == detection_id]


def record_literature(
    run_id: str,
    detection_id: str,
    sources: list[str],
    evidence_summary: str,
    supporting_claims: list[str],
    contradicting_claims: list[str],
    evidence_quality: float,
    confidence: str,
) -> dict:
    _, state, record = _get(run_id, detection_id)
    _require_open(state)
    if state.literature is not None:
        raise ToolError("literature evidence already recorded; use record_evidence_review to revise it")
    if not sources or not all(s.startswith(("https://", "http://")) for s in sources):
        raise ToolError("cite at least one public source, as http(s) URLs")
    if not 0.0 <= evidence_quality <= 1.0:
        raise ToolError("evidence_quality must be between 0 and 1")
    _charge(state, "literature_check")
    state.literature = LiteratureEvidence(
        detection_id=detection_id,
        sources=sources,
        evidence_summary=evidence_summary,
        supporting_claims=supporting_claims,
        contradicting_claims=contradicting_claims,
        confidence=Confidence(confidence.upper()),
        evidence_quality=evidence_quality,
    )
    ev = record("literature", "literature_check", state.literature.model_dump(mode="json"), state.literature.confidence.value)
    state.evidence_ids.append(ev.event_id)
    state.tests_run.append("literature_check")
    return {"event_id": ev.event_id, "remaining_budget": state.remaining_budget}


def record_plan(
    run_id: str,
    detection_id: str,
    selected_test: str | None,
    rationale: str,
    options: list[dict],
    planned_follow_up: str | None,
) -> dict:
    _, state, record = _get(run_id, detection_id)
    _require_open(state)
    if state.literature is None:
        raise ToolError("record literature evidence before planning experiments")
    if state.pending_test is not None:
        raise ToolError(f"{state.pending_test} is planned but not yet executed")
    if selected_test is not None:
        if selected_test not in AGENTIC_TESTS:
            raise ToolError(f"selected_test must be one of {AGENTIC_TESTS} or null to stop")
        if selected_test in state.tests_run:
            raise ToolError(f"{selected_test} has already been run")
        if selected_test != "efficacy_test" and "efficacy_test" not in state.tests_run:
            raise ToolError("efficacy_test must run before any other experiment")
        if TEST_COSTS[selected_test] > state.remaining_budget:
            raise ToolError(f"{selected_test} costs {TEST_COSTS[selected_test]}; remaining budget is {state.remaining_budget}")

    ranked = []
    for opt in options:
        test, gain = opt.get("test"), opt.get("expected_information_gain")
        if test not in TEST_COSTS or not isinstance(gain, (int, float)):
            raise ToolError("each option needs a known 'test' and a numeric 'expected_information_gain'")
        ranked.append({"test": test, "expected_information_gain": gain, "cost": TEST_COSTS[test], "priority": round(gain / TEST_COSTS[test], 4)})
    ranked.sort(key=lambda r: -r["priority"])

    if state.scorecard is not None:
        current = portfolio.classify(state)[0].value
        if current != state.reference_provisional:
            record("portfolio", "provisional_decision", {"decision": current, "uncertainty": state.uncertainty.value, "source": "rule_based_reference"})
        state.reference_provisional = current

    plan_event = record(
        "planner",
        "select_test",
        {
            "selected_test": selected_test,
            "planned_follow_up": planned_follow_up,
            "remaining_budget": state.remaining_budget,
            "ranked_options": ranked,
            "rationale": rationale,
            "uncertainty": state.uncertainty.value if state.uncertainty else None,
        },
    )
    adapted = state.has_plan and selected_test != state.planned_follow_up
    if adapted:
        record(
            "planner",
            "ADAPTATION_EVENT",
            {
                "reason": f"evidence from {state.tests_run[-1]} changed the plan",
                "discarded_test": state.planned_follow_up,
                "scheduled_test": selected_test,
                "uncertainty_after": state.uncertainty.value if state.uncertainty else None,
                "planner_event_id": plan_event.event_id,
            },
            "HIGH",
        )
    state.has_plan = True
    state.pending_test = selected_test
    state.planned_follow_up = planned_follow_up
    return {"event_id": plan_event.event_id, "adaptation_event": adapted, "pending_test": selected_test}


def run_test(run_id: str, detection_id: str, test: str) -> dict:
    run, state, record = _get(run_id, detection_id)
    _require_open(state)
    if test not in DATASET_TESTS:
        raise ToolError(f"run_test executes {DATASET_TESTS}; robustness goes to the red team, evidence review to literature")
    _require_pending(state, test)
    _charge(state, test)
    result = run_experiment(run.run_id, ExperimentSpec(detection_id=detection_id, experiment_type=test, random_seed=run.seed), state.detection)
    ev = record("experiment_runner", test, result.model_dump(mode="json"))
    state.evidence_ids.append(ev.event_id)
    if test == "efficacy_test":
        state.scorecard = analyze(result)
        state.sample_size = result.raw_results["tp"] + result.raw_results["fn"]
    elif test == "redundancy_check":
        state.scorecard = state.scorecard.model_copy(update={"redundancy_overlap": result.metrics["sibling_overlap"]})
    else:
        state.scorecard = state.scorecard.model_copy(update={"alerts_per_user_day": result.metrics["alerts_per_user_day"]})
    _complete_test(state, test, record)
    return {"event_id": ev.event_id, "metrics": result.metrics, "scorecard": state.scorecard.model_dump(), "uncertainty": state.uncertainty.model_dump(), "remaining_budget": state.remaining_budget}


def run_evasion_variant(run_id: str, detection_id: str, strength: float) -> dict:
    run, state, record = _get(run_id, detection_id)
    _require_open(state)
    _require_pending(state, "robustness_test")
    if not 0.0 < strength <= 1.0:
        raise ToolError("strength must be in (0, 1]")
    if len(state.evasion_variants) >= MAX_EVASION_VARIANTS:
        raise ToolError(f"at most {MAX_EVASION_VARIANTS} variants per robustness test; call finish_robustness")
    if not state.evasion_variants:
        _charge(state, "robustness_test")
    spec = ExperimentSpec(
        detection_id=detection_id,
        experiment_type="robustness_test",
        random_seed=run.seed,
        parameters={"variant": "evasion", "strength": strength},
    )
    result = run_experiment(run.run_id, spec, state.detection)
    state.evasion_variants.append(result)
    ev = record("experiment_runner", "robustness_variant", result.model_dump(mode="json"))
    state.evidence_ids.append(ev.event_id)
    degradation = round(max(0.0, state.scorecard.recall - result.metrics["recall"]), 4)
    return {
        "event_id": ev.event_id,
        "strength": strength,
        "evasion_technique": result.raw_results["evasion_technique"],
        "baseline_recall": state.scorecard.recall,
        "adapted_recall": result.metrics["recall"],
        "degradation": degradation,
        "broken": degradation > BREAK_THRESHOLD,
        "variants_remaining": MAX_EVASION_VARIANTS - len(state.evasion_variants),
    }


def finish_robustness(run_id: str, detection_id: str, explanation: str) -> dict:
    _, state, record = _get(run_id, detection_id)
    _require_pending(state, "robustness_test")
    variants = sorted(state.evasion_variants, key=lambda v: v.parameters["strength"])
    if not any(v.parameters["strength"] <= REFERENCE_STRENGTH for v in variants):
        raise ToolError(f"run at least one variant with strength <= {REFERENCE_STRENGTH} so degradation can be scored")
    baseline = state.scorecard.recall
    strengths = [v.parameters["strength"] for v in variants]
    degradations = [round(max(0.0, baseline - v.metrics["recall"]), 4) for v in variants]
    broken = [s for s, d in zip(strengths, degradations) if d > BREAK_THRESHOLD]
    technique = variants[0].raw_results["evasion_technique"]
    state.robustness = RobustnessResult(
        baseline_score=baseline,
        evasion_technique=technique,
        strengths_tested=strengths,
        adapted_scores=[v.metrics["recall"] for v in variants],
        degradation_curve=degradations,
        reference_degradation=max(d for s, d in zip(strengths, degradations) if s <= REFERENCE_STRENGTH),
        breaking_parameters={"technique": technique, "strength": broken[0] if broken else None},
        explanation=explanation,
        confidence=Confidence.HIGH if broken else Confidence.MEDIUM,
    )
    ev = record("red_team", "robustness_test", state.robustness.model_dump(), state.robustness.confidence.value)
    state.evidence_ids.append(ev.event_id)
    state.scorecard = state.scorecard.model_copy(update={"robustness_degradation": state.robustness.reference_degradation})
    _complete_test(state, "robustness_test", record)
    return {"event_id": ev.event_id, "robustness": state.robustness.model_dump(), "uncertainty": state.uncertainty.model_dump()}


def record_evidence_review(run_id: str, detection_id: str, notes: list[str], revised_evidence_quality: float) -> dict:
    _, state, record = _get(run_id, detection_id)
    _require_open(state)
    _require_pending(state, "evidence_quality_review")
    before = state.literature.evidence_quality
    if abs(revised_evidence_quality - before) > 0.2 or not 0.0 <= revised_evidence_quality <= 1.0:
        raise ToolError(f"revised_evidence_quality must be within 0.2 of {before} and in [0, 1]")
    _charge(state, "evidence_quality_review")
    state.literature = state.literature.model_copy(update={"evidence_quality": revised_evidence_quality})
    state.evidence_reviewed = True
    ev = record(
        "literature",
        "evidence_quality_review",
        {"evidence_quality_before": before, "evidence_quality_after": revised_evidence_quality, "notes": notes, "sources": state.literature.sources},
    )
    state.evidence_ids.append(ev.event_id)
    _complete_test(state, "evidence_quality_review", record)
    return {"event_id": ev.event_id, "uncertainty": state.uncertainty.model_dump() if state.uncertainty else None}


def record_analysis(run_id: str, detection_id: str, interpretation: str, concerns: list[str]) -> dict:
    _, state, record = _get(run_id, detection_id)
    if state.scorecard is None:
        raise ToolError("nothing to analyse until efficacy_test has run")
    ev = record(
        "analyst",
        "interpretation",
        {"interpretation": interpretation, "concerns": concerns, "scorecard": state.scorecard.model_dump(), "uncertainty": state.uncertainty.model_dump()},
    )
    return {"event_id": ev.event_id}


def submit_decision(
    run_id: str,
    detection_id: str,
    decision: str,
    rationale: str,
    confidence: str,
    recommended_next_test: str | None,
) -> dict:
    run, state, record = _get(run_id, detection_id)
    _require_open(state)
    if state.scorecard is None:
        raise ToolError("efficacy_test must run before a decision")
    if state.pending_test is not None:
        raise ToolError(f"{state.pending_test} is planned but not executed; finish it or have the planner stop first")
    verdict = Decision(decision.upper())
    if verdict == Decision.INVESTIGATE and not recommended_next_test:
        raise ToolError("INVESTIGATE must name the recommended next experiment")
    if len(rationale.strip()) < 40:
        raise ToolError("rationale must cite the evidence behind the decision")
    reference, reference_rationale = portfolio.classify(state)
    needs_approval = verdict == Decision.DECOMMISSION
    state.decision = PortfolioDecision(
        decision_id=f"{run.run_id}:{detection_id}",
        detection_id=detection_id,
        decision=verdict,
        rationale=rationale,
        confidence=Confidence(confidence.upper()),
        evidence_ids=list(state.evidence_ids),
        scorecard=state.scorecard,
        uncertainty=state.uncertainty.value,
        recommended_next_test=recommended_next_test if verdict == Decision.INVESTIGATE else None,
        requires_human_approval=needs_approval,
        approval_status=ApprovalStatus.PENDING if needs_approval else ApprovalStatus.NOT_REQUIRED,
    )
    run.decisions[detection_id] = state.decision
    ev = record(
        "portfolio",
        "decision",
        {
            **state.decision.model_dump(mode="json"),
            "rule_based_reference": {"decision": reference.value, "rationale": reference_rationale},
            "agrees_with_reference": reference == verdict,
        },
        state.decision.confidence.value,
    )
    return {"event_id": ev.event_id, "decision_id": state.decision.decision_id, "approval_status": state.decision.approval_status.value}


def record_safety_review(run_id: str, detection_id: str, status: str, reasons: list[str]) -> dict:
    _, state, record = _get(run_id, detection_id)
    if state.decision is None:
        raise ToolError("no decision to review yet")
    requested = SafetyOutcome(status.upper())
    # The approval gate is not the model's call: DECOMMISSION always waits for a human.
    enforced = SafetyOutcome.REQUIRES_HUMAN_APPROVAL if state.decision.requires_human_approval else requested
    if requested == SafetyOutcome.BLOCKED:
        enforced = SafetyOutcome.BLOCKED
    review = SafetyDecision(detection_id=detection_id, status=enforced, reasons=reasons)
    ev = record("safety", "safety_gate", {**review.model_dump(mode="json"), "requested_status": requested.value})
    return {"event_id": ev.event_id, "status": enforced.value}
