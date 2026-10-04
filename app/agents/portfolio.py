from app.models.schemas import Confidence, Decision, DetectionScorecard, PortfolioDecision


def decide(detection_id: str, scorecard: DetectionScorecard, uncertainty: float) -> PortfolioDecision:
    if scorecard.f1 >= 0.8 and scorecard.false_positive_rate <= 0.15 and uncertainty < 0.45:
        decision = Decision.KEEP
        next_test = None
    elif scorecard.f1 < 0.5 and scorecard.false_positive_rate > 0.35 and uncertainty < 0.5:
        decision = Decision.DECOMMISSION
        next_test = None
    else:
        decision = Decision.INVESTIGATE
        next_test = "evidence_quality_review"
    return PortfolioDecision(
        detection_id=detection_id,
        decision=decision,
        rationale="Deterministic rule-based portfolio decision from scorecard + uncertainty.",
        confidence=Confidence.MEDIUM if decision == Decision.INVESTIGATE else Confidence.HIGH,
        evidence_ids=[f"evidence-{detection_id}"],
        scorecard=scorecard,
        uncertainty=round(uncertainty, 4),
        recommended_next_test=next_test,
        requires_human_approval=decision == Decision.DECOMMISSION,
    )
