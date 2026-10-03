from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4

from app.agents.analysis import analyze
from app.agents.experiment_runner import run_experiment
from app.agents.literature import run_literature_agent
from app.agents.planner import select_test, TEST_COSTS
from app.agents.portfolio import decide
from app.agents.red_team import adaptive_robustness_result
from app.agents.safety import validate_safety
from app.models.schemas import (
    Decision,
    ExperimentSpec,
    PortfolioDecision,
    ResearchEvent,
)
from app.services.data_store import load_detections


@dataclass
class RunState:
    run_id: str
    started_at: float
    events: list[ResearchEvent] = field(default_factory=list)
    decisions: dict[str, PortfolioDecision] = field(default_factory=dict)


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
