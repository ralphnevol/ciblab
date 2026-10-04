from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.planner import TEST_COSTS
from app.evaluation.evaluator import evaluate_latest
from app.experiments.synthetic_generator import generate_dataset
from app.main import app
from app.orchestration.lab import execute_run, get_run, replay_run
from app.services.data_store import load_detections, load_labels_for_evaluation, sealed_hash

APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture(scope="module")
def run():
    return get_run(execute_run(seed=42))


def _events(run, detection_id, action=None):
    return [e for e in run.events if e.detection_id == detection_id and (action is None or e.action == action)]


def test_detections_count():
    assert len(load_detections()) == 18


def test_generator_is_deterministic():
    assert generate_dataset(42, "D03", "evasion", 0.5) == generate_dataset(42, "D03", "evasion", 0.5)


def test_datasets_differ_per_detection():
    assert generate_dataset(42, "D01")["events"] != generate_dataset(42, "D02")["events"]


def test_scorecards_differ_per_detection(run):
    scorecards = {d.scorecard.model_dump_json() for d in run.decisions.values()}
    assert len(scorecards) == 18


def test_all_decision_types_reachable(run):
    assert {d.decision.value for d in run.decisions.values()} == {"KEEP", "INVESTIGATE", "DECOMMISSION"}


def test_decommission_requires_pending_human_approval(run):
    decommissions = [d for d in run.decisions.values() if d.decision.value == "DECOMMISSION"]
    assert decommissions
    for d in decommissions:
        assert d.requires_human_approval
        assert d.approval_status.value == "PENDING"
        gate = _events(run, d.detection_id, "safety_gate")[-1]
        assert gate.output["status"] == "REQUIRES_HUMAN_APPROVAL"


def test_budget_respected(run):
    intake = TEST_COSTS["literature_check"] + TEST_COSTS["efficacy_test"]
    for det_id in run.decisions:
        planned = [e.output["selected_test"] for e in _events(run, det_id, "select_test") if e.output["selected_test"]]
        assert intake + sum(TEST_COSTS[t] for t in planned) <= run.budget, det_id


def test_d03_adapts_from_keep_to_investigate(run):
    provisional = [e.output["decision"] for e in _events(run, "D03", "provisional_decision")]
    assert provisional[0] == "KEEP"
    assert run.decisions["D03"].decision.value == "INVESTIGATE"
    assert run.decisions["D03"].recommended_next_test

    (adaptation,) = _events(run, "D03", "ADAPTATION_EVENT")
    plans = _events(run, "D03", "select_test")
    # The adaptation records a real change: the follow-up planned before the red-team result
    # differs from what the planner actually chose afterwards.
    assert adaptation.output["discarded_test"] == plans[0].output["planned_follow_up"]
    assert adaptation.output["scheduled_test"] == plans[1].output["selected_test"]
    assert adaptation.output["discarded_test"] != adaptation.output["scheduled_test"]
    assert adaptation.output["uncertainty_after"] > adaptation.output["uncertainty_before"]


def test_adaptation_only_follows_robustness_failure(run):
    for e in run.events:
        if e.action == "ADAPTATION_EVENT":
            robustness = _events(run, e.detection_id, "robustness_test")
            assert robustness and robustness[0].output["breaking_parameters"]["strength"] is not None


def test_evidence_ids_reference_recorded_events(run):
    event_ids = {e.event_id for e in run.events}
    for d in run.decisions.values():
        assert d.evidence_ids and set(d.evidence_ids) <= event_ids


@pytest.mark.parametrize("seed", [1, 7, 42, 1234])
def test_decisions_match_sealed_labels_across_seeds(seed):
    labels = load_labels_for_evaluation()
    replay = replay_run(seed=seed)
    correct = sum(replay.decisions[d].decision.value == label for d, label in labels.items())
    assert correct / len(labels) >= 0.9


def test_replay_is_reproducible(run):
    assert evaluate_latest(run.run_id).reproducibility_result


def test_agents_never_read_sealed_labels_or_world_profiles():
    for path in APP_DIR.rglob("*.py"):
        source = path.read_text()
        if path.name not in ("evaluator.py", "data_store.py"):
            assert "load_labels_for_evaluation" not in source, path
        if path.name != "synthetic_generator.py":
            assert "world_profiles" not in source, path


def test_api_run_evaluation_and_approval():
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    created = c.post("/runs").json()
    assert created["sealed_ground_truth_hash"] == sealed_hash()
    assert c.get("/evaluation").status_code == 200

    decisions = c.get(f"/runs/{created['run_id']}/decisions").json()
    decommission = next(d for d in decisions if d["decision"] == "DECOMMISSION")
    keep = next(d for d in decisions if d["decision"] == "KEEP")

    approved = c.post(f"/approvals/{decommission['decision_id']}", params={"reviewer": "tester"})
    assert approved.status_code == 200 and approved.json()["approval_status"] == "APPROVED"
    assert c.post(f"/approvals/{decommission['decision_id']}").status_code == 409
    assert c.post(f"/approvals/{keep['decision_id']}").status_code == 409
    assert c.post("/approvals/unknown").status_code == 404

    timeline = c.get(f"/detections/{decommission['detection_id']}/timeline").json()
    assert timeline[-1]["action"] == "approval"
