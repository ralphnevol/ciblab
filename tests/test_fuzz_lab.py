"""Tests for the Agentic Fuzzing Discovery Lab."""

from fastapi.testclient import TestClient

from app.experiments.vulnerable_binary import run_target, Signal
from app.agents.seed_agent import generate_corpus
from app.agents.execution_agent import run_fuzz_experiment
from app.agents.safety_fuzz import validate_fuzz_target, gate_crash_reproduction
from app.agents.triage_agent import triage_all
from app.orchestration.fuzz_lab import DEFAULT_TARGET, start_fuzz_run, approve_and_triage, FUZZ_RUNS
from app.evaluation.fuzz_evaluator import evaluate_fuzz_runs
from app.main import app


def test_vulnerable_binary_crashes():
    # 1. Overflow
    res_overflow = run_target(b"A" * 100)
    assert res_overflow.crashed
    assert res_overflow.signal == Signal.SIGSEGV
    assert "buffer overflow" in res_overflow.stderr.lower()

    # 2. Null byte
    res_null = run_target(b"VALID\x00ANOMALY")
    assert res_null.crashed
    assert res_null.signal == Signal.SIGABRT
    assert "null byte" in res_null.stderr.lower()

    # 3. Format string
    res_fmt = run_target(b"%s%s%n")
    assert res_fmt.crashed
    assert res_fmt.signal == Signal.SIGSEGV
    assert "format string" in res_fmt.stderr.lower()

    # 4. Safe input
    res_safe = run_target(b"SAFE_INPUT")
    assert not res_safe.crashed
    assert res_safe.exit_code == 0


def test_seed_agent_generates_corpus():
    corpus = generate_corpus("TEST-001", DEFAULT_TARGET, seed=42)
    assert len(corpus.seeds) == 5
    assert corpus.hypothesis
    assert corpus.confidence > 0.7
    strategies = [s.mutation_strategy for s in corpus.seeds]
    assert "boundary_overflow" in strategies
    assert "null_injection" in strategies
    assert "format_string" in strategies


def test_execution_agent_discovers_crashes():
    corpus = generate_corpus("TEST-002", DEFAULT_TARGET, seed=42)
    crashes = run_fuzz_experiment(corpus, seed=42, mutation_rounds=5)
    assert len(crashes) > 0
    signals = {c.signal for c in crashes}
    assert Signal.SIGSEGV in signals


def test_safety_agent_validates_and_gates():
    # Validation
    safe_dec = validate_fuzz_target(DEFAULT_TARGET)
    assert safe_dec.status.value == "APPROVED"

    # Gate
    gate_dec = gate_crash_reproduction(crash_count=10)
    assert gate_dec.status.value == "REQUIRES_HUMAN_APPROVAL"


def test_fuzz_lab_end_to_end():
    run_id = start_fuzz_run(
        question="Test Question: memory corruption?",
        seed=42,
    )
    assert run_id in FUZZ_RUNS
    run = FUZZ_RUNS[run_id]
    assert run.pending_approval is True
    assert run.crash_count > 0

    discovery = approve_and_triage(run_id, approved=True)
    assert discovery is not None
    assert discovery.hypothesis_confirmed is True
    assert discovery.crashes_found > 0
    assert len(discovery.triage_results) > 0
    assert discovery.speedup_vs_manual > 1.0


def test_api_endpoints():
    client = TestClient(app)

    # Health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # Start run
    res_run = client.post("/fuzz-runs?seed=42")
    assert res_run.status_code == 200
    data = res_run.json()
    run_id = data["run_id"]
    assert data["pending_approval"] is True

    # Events timeline
    res_events = client.get(f"/fuzz-runs/{run_id}/events")
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) >= 4

    # Approve
    res_approve = client.post(f"/fuzz-approvals/{run_id}?approved=true")
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "completed"

    # Metrics
    res_metrics = client.get("/fuzz-metrics")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert metrics["total_runs"] > 0
