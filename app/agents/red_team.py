from app.models.schemas import Confidence, RobustnessResult


def adaptive_robustness_result(baseline_score: float, adapted_score: float) -> RobustnessResult:
    degradation = max(0.0, baseline_score - adapted_score)
    return RobustnessResult(
        baseline_score=baseline_score,
        adapted_scores=[adapted_score],
        degradation_curve=[degradation],
        breaking_parameters={"timing_randomisation": True},
        explanation="Adaptive timing randomisation reduced fixed-interval detection quality.",
        confidence=Confidence.HIGH if degradation > 0.2 else Confidence.MEDIUM,
    )
