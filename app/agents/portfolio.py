from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.schemas import ApprovalStatus, Confidence, Decision, PortfolioDecision

if TYPE_CHECKING:
    from app.orchestration.state import TriageState

KEEP_MIN_F1 = 0.75
KEEP_MAX_FPR = 0.02
KEEP_MAX_DEGRADATION = 0.15
KEEP_MAX_UNCERTAINTY = 0.45
DECOMMISSION_MAX_F1 = 0.45
DECOMMISSION_MAX_PRECISION = 0.35
DECOMMISSION_MIN_ALERTS_PER_USER_DAY = 2.0
DECOMMISSION_MAX_UNCERTAINTY = 0.5


def classify(state: TriageState) -> tuple[Decision, str]:
    sc = state.scorecard
    u = state.uncertainty.value
    noisy = sc.precision < DECOMMISSION_MAX_PRECISION or sc.alerts_per_user_day > DECOMMISSION_MIN_ALERTS_PER_USER_DAY
    if noisy and sc.f1 < DECOMMISSION_MAX_F1 and u < DECOMMISSION_MAX_UNCERTAINTY:
        return Decision.DECOMMISSION, (
            f"precision {sc.precision:.2f} / alerts per user-day {sc.alerts_per_user_day:.2f} indicate noise, "
            f"F1 {sc.f1:.2f} < {DECOMMISSION_MAX_F1}, uncertainty {u:.2f} < {DECOMMISSION_MAX_UNCERTAINTY}"
        )
    keep_checks = {
        f"F1 {sc.f1:.2f} >= {KEEP_MIN_F1}": sc.f1 >= KEEP_MIN_F1,
        f"FPR {sc.false_positive_rate:.3f} <= {KEEP_MAX_FPR}": sc.false_positive_rate <= KEEP_MAX_FPR,
        f"robustness degradation {sc.robustness_degradation:.2f} < {KEEP_MAX_DEGRADATION}": sc.robustness_degradation
        < KEEP_MAX_DEGRADATION,
        f"uncertainty {u:.2f} < {KEEP_MAX_UNCERTAINTY}": u < KEEP_MAX_UNCERTAINTY,
    }
    if all(keep_checks.values()):
        return Decision.KEEP, "; ".join(keep_checks)
    failed = [check for check, ok in keep_checks.items() if not ok]
    return Decision.INVESTIGATE, "KEEP criteria not met: " + "; ".join(failed)


def _confidence(uncertainty: float) -> Confidence:
    if uncertainty < 0.3:
        return Confidence.HIGH
    if uncertainty < 0.55:
        return Confidence.MEDIUM
    return Confidence.LOW


def decide(run_id: str, state: TriageState, next_test: str | None) -> PortfolioDecision:
    decision, rationale = classify(state)
    needs_approval = decision == Decision.DECOMMISSION
    return PortfolioDecision(
        decision_id=f"{run_id}:{state.detection.detection_id}",
        detection_id=state.detection.detection_id,
        decision=decision,
        rationale=f"{decision.value}: {rationale}. Tests run: {', '.join(state.tests_run)}.",
        confidence=_confidence(state.uncertainty.value),
        evidence_ids=list(state.evidence_ids),
        scorecard=state.scorecard,
        uncertainty=state.uncertainty.value,
        recommended_next_test=next_test if decision == Decision.INVESTIGATE else None,
        requires_human_approval=needs_approval,
        approval_status=ApprovalStatus.PENDING if needs_approval else ApprovalStatus.NOT_REQUIRED,
    )
