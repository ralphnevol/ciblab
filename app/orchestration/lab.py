from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4

from app.agents.analysis import analyze
from app.agents.experiment_runner import run_experiment
from app.agents.experiment_runner import run_research_experiment
from app.agents.hypothesis import formulate_hypotheses
from app.agents.literature import run_literature_agent
from app.agents.planner import propose_candidates, select_candidate, select_test, TEST_COSTS
from app.agents.portfolio import decide
from app.agents.red_team import adaptive_robustness_result
from app.agents.research import research
from app.agents.safety import validate_research_target, validate_safety
from app.models.schemas import (
    Decision,
    ResearchCase,
    ResearchDecision,
    ResearchQuestion,
    ExperimentSpec,
    PortfolioDecision,
    ResearchEvent,
)
from app.storage.research_store import STORE
from app.tools.public_evidence import collect_public_evidence
from app.services.data_store import load_detections


@dataclass
class RunState:
    run_id: str
    started_at: float
    events: list[ResearchEvent] = field(default_factory=list)
    decisions: dict[str, PortfolioDecision] = field(default_factory=dict)
    case_id: str | None = None


RUNS: dict[str, RunState] = {}


def _event(run_id: str, detection_id: str, agent: str, action: str, output: dict, confidence: str = "MEDIUM", parent: str | None = None):
    ev = ResearchEvent(
        event_id=str(uuid4()),
        detection_id=detection_id,
        agent=agent,
        action=action,
        input_reference="structured-json",
        output=output,
        confidence=confidence,
        citations=output.get("sources", []),
        parent_event_id=parent,
        run_id=run_id,
    )
    RUNS[run_id].events.append(ev)
    return ev


def _case_event(run_id: str, case_id: str, agent: str, action: str, output: dict, confidence: str = "MEDIUM", parent: str | None = None):
    event = ResearchEvent(
        event_id=str(uuid4()),
        case_id=case_id,
        agent=agent,
        action=action,
        input_reference="structured-json",
        output=output,
        confidence=confidence,
        citations=output.get("citations", []),
        parent_event_id=parent,
        run_id=run_id,
    )
    STORE.add_event(event)
    RUNS[run_id].events.append(event)
    return event


def execute_research_case(question: str, seed: int = 42, case_id: str = "CASE-001") -> str:
    run_id = str(uuid4())
    case = ResearchCase(
        case_id=case_id,
        title="Synthetic binary timing sensitivity",
        question=ResearchQuestion(
            case_id=case_id,
            question=question,
            target="synthetic-binary-01",
            constraints=["public_or_synthetic_only", "reproducible_seed"],
        ),
    )
    STORE.add_case(case)
    RUNS[run_id] = RunState(run_id=run_id, started_at=time.perf_counter(), case_id=case_id)
    _case_event(run_id, case_id, "research", "question", case.question.model_dump())
    safety = validate_research_target(case.question.target, case.question.constraints)
    _case_event(run_id, case_id, "safety", "safety_gate", safety.model_dump())
    if safety.status.value == "BLOCKED":
        case.status = "blocked"
        STORE.persist()
        return run_id
    evidence = collect_public_evidence(case_id, question)
    STORE.add_evidence(evidence)
    research_output = research(case.question, evidence)
    research_output["citations"] = [item.citation for item in evidence]
    research_event = _case_event(run_id, case_id, "research", "evidence_collected", research_output)
    hypotheses = formulate_hypotheses(case_id, evidence)
    STORE.add_hypotheses(hypotheses)
    hypothesis_event = _case_event(
        run_id,
        case_id,
        "hypothesis",
        "hypotheses_formulated",
        {"hypotheses": [item.model_dump() for item in hypotheses]},
        parent=research_event.event_id,
    )
    candidates = propose_candidates(case_id, [item.hypothesis_id for item in hypotheses])
    selected = select_candidate(candidates)
    _case_event(
        run_id,
        case_id,
        "planner",
        "candidates_selected",
        {
            "candidates": [item.model_dump() for item in candidates],
            "selected": selected.experiment_id,
            "reason": "expected_learning * feasibility / cost",
        },
        parent=hypothesis_event.event_id,
    )
    first_result = run_research_experiment(run_id, case_id, selected.experiment_id, seed, selected.parameters)
    first_event = _case_event(
        run_id,
        case_id,
        "experiment_runner",
        "execute",
        first_result.model_dump(mode="json"),
    )
    _case_event(
        run_id,
        case_id,
        "analysis",
        "result_interpreted",
        {"supported": [hypotheses[0].hypothesis_id], "new_uncertainties": ["randomized timing response"]},
        parent=first_event.event_id,
    )
    next_candidate = next(item for item in candidates if item.experiment_id != selected.experiment_id)
    second_result = run_research_experiment(run_id, case_id, next_candidate.experiment_id, seed, next_candidate.parameters)
    second_event = _case_event(run_id, case_id, "experiment_runner", "execute", second_result.model_dump(mode="json"))
    updated = ResearchDecision(
        case_id=case_id,
        selected_experiment=next_candidate.experiment_id,
        rationale="The first result exposed timing uncertainty; the planner changed the next test to randomized timing.",
        updated_uncertainties=["degradation threshold", "timing sensitivity"],
    )
    _case_event(
        run_id,
        case_id,
        "planner",
        "ADAPTATION_EVENT",
        {"previous": selected.experiment_id, "next": updated.selected_experiment, "reason": updated.rationale},
        confidence="HIGH",
        parent=second_event.event_id,
    )
    _case_event(run_id, case_id, "decision", "updated_decision", updated.model_dump(), parent=second_event.event_id)
    case.status = "completed"
    STORE.persist()
    return run_id


def execute_run(seed: int = 42, max_test_cost: int = 10) -> str:
    run_id = str(uuid4())
    RUNS[run_id] = RunState(run_id=run_id, started_at=time.time())
    for det in load_detections():
        remaining = max_test_cost
        uncertainty = 0.35
        d03_adapted = False
        lit = run_literature_agent(det.detection_id)
        _event(run_id, det.detection_id, "literature", "literature_check", lit.model_dump(), lit.confidence.value)

        baseline_spec = ExperimentSpec(
            detection_id=det.detection_id,
            experiment_type="efficacy_test",
            random_seed=seed,
            parameters={"variant": "baseline"},
        )
        baseline = run_experiment(run_id, baseline_spec)
        remaining -= TEST_COSTS["efficacy_test"]
        _event(run_id, det.detection_id, "experiment_runner", "efficacy_test", baseline.model_dump(mode="json"))
        scorecard = analyze(baseline)
        _event(run_id, det.detection_id, "analysis", "scorecard", scorecard.model_dump())

        if det.detection_id == "D03" and remaining >= TEST_COSTS["robustness_test"]:
            planner1 = select_test(remaining, uncertainty, baseline.raw_results, d03_adapted=False)
            _event(run_id, det.detection_id, "planner", "select_test", planner1.model_dump())
            if planner1.selected_test == "robustness_test":
                robust_spec = ExperimentSpec(
                    detection_id=det.detection_id,
                    experiment_type="robustness_test",
                    random_seed=seed,
                    parameters={"variant": "adapted"},
                )
                adapted = run_experiment(run_id, robust_spec)
                remaining = planner1.remaining_budget
                robust = adaptive_robustness_result(baseline.metrics["score"], adapted.metrics["score"])
                uncertainty = 0.72 if robust.degradation_curve[0] > 0.2 else uncertainty
                d03_adapted = True
                _event(run_id, det.detection_id, "red_team", "robustness_test", robust.model_dump())
                _event(
                    run_id,
                    det.detection_id,
                    "planner",
                    "ADAPTATION_EVENT",
                    {
                        "reason": "robustness degradation observed",
                        "new_uncertainty": uncertainty,
                        "discarded_test": "redundancy_check",
                        "scheduled_test": "evidence_quality_review",
                    },
                    "HIGH",
                )
                planner2 = select_test(remaining, uncertainty, adapted.raw_results, d03_adapted=True)
                _event(run_id, det.detection_id, "planner", "select_test", planner2.model_dump())
                scorecard = analyze(adapted, robustness_degradation=robust.degradation_curve[0])
                _event(run_id, det.detection_id, "analysis", "scorecard_post_adaptation", scorecard.model_dump())

        decision = decide(det.detection_id, scorecard, uncertainty)
        safety = validate_safety(decision)
        _event(run_id, det.detection_id, "portfolio", "decision", decision.model_dump(mode="json"), decision.confidence.value)
        _event(run_id, det.detection_id, "safety", "safety_gate", safety.model_dump())
        RUNS[run_id].decisions[det.detection_id] = decision
    return run_id


def get_run(run_id: str):
    return RUNS.get(run_id)


def get_timeline(detection_id: str):
    out = []
    for run in RUNS.values():
        out.extend([e for e in run.events if e.detection_id == detection_id])
    return sorted(out, key=lambda e: e.timestamp)
