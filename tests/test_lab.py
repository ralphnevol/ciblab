from fastapi.testclient import TestClient

from app.agents.planner import select_test
from app.agents.portfolio import decide
from app.agents.safety import validate_safety
from app.experiments.synthetic_generator import generate_dataset
from app.main import app
from app.models.schemas import DetectionScorecard
from app.orchestration.lab import execute_run, get_run
from app.services.data_store import load_detections, sealed_hash


def test_detections_count():
    assert len(load_detections()) == 18


def test_generator_is_deterministic():
    d1 = generate_dataset(42, "D03", "adapted")
    d2 = generate_dataset(42, "D03", "adapted")
    assert d1 == d2


def test_planner_budget_respected():
    p = select_test(remaining_budget=4, uncertainty=0.2, last_result=None, d03_adapted=False)
    assert p.remaining_budget >= 0


def test_safety_requires_human_for_decommission():
    score = DetectionScorecard(
        precision=0.2,
        recall=0.2,
        f1=0.2,
        false_positive_rate=0.5,
        alert_volume=100,
        alerts_per_user_day=20,
        redundancy_overlap=0.9,
        robustness_degradation=0.0,
    )
    decision = decide("D99", score, uncertainty=0.1)
    safety = validate_safety(decision)
    assert safety.status.value == "REQUIRES_HUMAN_APPROVAL"


def test_d03_adaptation_event_present():
    run_id = execute_run(seed=42)
    run = get_run(run_id)
    events = [e for e in run.events if e.detection_id == "D03" and e.action == "ADAPTATION_EVENT"]
    assert events
    assert run.decisions["D03"].decision.value == "INVESTIGATE"


def test_api_health_and_run_and_hash():
    c = TestClient(app)
    h = c.get("/health").json()
    assert h["status"] == "ok"
    run = c.post("/runs").json()
    assert run["sealed_ground_truth_hash"] == sealed_hash()
    ev = c.get("/evaluation")
    assert ev.status_code == 200
