from app.models.schemas import PortfolioDecision, SafetyDecision, SafetyOutcome


def validate_safety(decision: PortfolioDecision) -> SafetyDecision:
    reasons = [
        "Synthetic-only operation enforced.",
        "No real telemetry allowed.",
        "No real-world offensive actions allowed.",
    ]
    if decision.requires_human_approval:
        return SafetyDecision(
            detection_id=decision.detection_id,
            status=SafetyOutcome.REQUIRES_HUMAN_APPROVAL,
            reasons=reasons + ["Human approval required for DECOMMISSION."],
        )
    return SafetyDecision(detection_id=decision.detection_id, status=SafetyOutcome.APPROVED, reasons=reasons)
