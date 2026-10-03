from __future__ import annotations

from app.models.schemas import DetectionScorecard, ExperimentResult


def analyze(result: ExperimentResult, robustness_degradation: float = 0.0) -> DetectionScorecard:
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
        alerts_per_user_day=round((tp + fp) / 5, 4),
        redundancy_overlap=0.2,
        robustness_degradation=round(robustness_degradation, 4),
    )
