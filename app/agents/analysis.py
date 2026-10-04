from __future__ import annotations

from math import sqrt

from app.agents.portfolio import DECOMMISSION_MAX_F1, KEEP_MIN_F1
from app.models.schemas import DetectionScorecard, ExperimentResult, UncertaintyEstimate
from app.orchestration.state import TriageState

UNTESTED_ROBUSTNESS_PENALTY = 0.1
MARGIN_WINDOW = 0.05
MARGIN_PENALTY = 0.15


def analyze(result: ExperimentResult) -> DetectionScorecard:
    tp = result.raw_results["tp"]
    fp = result.raw_results["fp"]
    fn = result.raw_results["fn"]
    tn = result.raw_results["tn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return DetectionScorecard(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        false_positive_rate=round(fpr, 4),
        alert_volume=float(tp + fp),
        alerts_per_user_day=result.raw_results["alerts_per_user_day"],
        redundancy_overlap=0.0,
        robustness_degradation=0.0,
    )


def _wilson_width(p: float, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 1.0
    denom = 1 + z * z / n
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return 2 * half


def estimate_uncertainty(state: TriageState) -> UncertaintyEstimate:
    sc = state.scorecard
    components = {
        # 95% Wilson interval width on recall: how much the efficacy sample alone can tell us.
        "sampling": _wilson_width(sc.recall, state.sample_size),
        "literature": (1 - state.literature.evidence_quality) * 0.3 * (0.5 if state.evidence_reviewed else 1.0),
        "robustness": state.robustness.reference_degradation if state.robustness else UNTESTED_ROBUSTNESS_PENALTY,
        "decision_margin": MARGIN_PENALTY
        if min(abs(sc.f1 - KEEP_MIN_F1), abs(sc.f1 - DECOMMISSION_MAX_F1)) < MARGIN_WINDOW
        else 0.0,
    }
    value = min(0.95, max(0.05, sum(components.values())))
    return UncertaintyEstimate(value=round(value, 4), components={k: round(v, 4) for k, v in components.items()})
