from __future__ import annotations

from app.agents.experiment_runner import run_experiment
from app.models.schemas import Confidence, Detection, ExperimentResult, ExperimentSpec, RobustnessResult

STRENGTHS = (0.25, 0.5, 0.75, 1.0)
# Degradation is judged at a moderate adversary; stronger variants are reported but not scored.
REFERENCE_STRENGTH = 0.5
BREAK_THRESHOLD = 0.2


def run_red_team(run_id: str, detection: Detection, seed: int, baseline_recall: float) -> tuple[RobustnessResult, list[ExperimentResult]]:
    """Escalate a parameterised synthetic evasion until the detection breaks or the sweep ends."""
    experiments: list[ExperimentResult] = []
    degradations: list[float] = []
    breaking_strength = None
    for strength in STRENGTHS:
        spec = ExperimentSpec(
            detection_id=detection.detection_id,
            experiment_type="robustness_test",
            random_seed=seed,
            parameters={"variant": "evasion", "strength": strength},
        )
        result = run_experiment(run_id, spec, detection)
        experiments.append(result)
        degradations.append(round(max(0.0, baseline_recall - result.metrics["recall"]), 4))
        if degradations[-1] > BREAK_THRESHOLD:
            breaking_strength = strength
            break

    tested = list(STRENGTHS[: len(experiments)])
    reference = max(d for s, d in zip(tested, degradations) if s <= REFERENCE_STRENGTH)
    technique = experiments[0].raw_results["evasion_technique"]
    if breaking_strength is not None:
        explanation = (
            f"{technique} at strength {breaking_strength} reduced recall by {degradations[-1]:.2f} "
            f"(break threshold {BREAK_THRESHOLD})."
        )
    else:
        explanation = f"{technique} up to strength {STRENGTHS[-1]} never reduced recall by more than {BREAK_THRESHOLD}."
    robustness = RobustnessResult(
        baseline_score=baseline_recall,
        evasion_technique=technique,
        strengths_tested=tested,
        adapted_scores=[r.metrics["recall"] for r in experiments],
        degradation_curve=degradations,
        reference_degradation=reference,
        breaking_parameters={"technique": technique, "strength": breaking_strength},
        explanation=explanation,
        confidence=Confidence.HIGH if breaking_strength is not None else Confidence.MEDIUM,
    )
    return robustness, experiments
