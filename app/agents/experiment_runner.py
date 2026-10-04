from __future__ import annotations

import time

from app.experiments.synthetic_generator import generate_dataset
from app.models.schemas import Detection, ExperimentResult, ExperimentSpec
from app.services.detection_engine import evaluate_detection

DEFAULT_VARIANTS = {
    "efficacy_test": "baseline",
    "redundancy_check": "baseline",
    "robustness_test": "evasion",
    "alert_volume_test": "alert_volume",
}
METRIC_KEYS = ("recall", "false_positive_rate", "alerts_per_user_day", "sibling_overlap")


def run_experiment(run_id: str, spec: ExperimentSpec, detection: Detection) -> ExperimentResult:
    t0 = time.perf_counter()
    variant = spec.parameters.get("variant", DEFAULT_VARIANTS[spec.experiment_type])
    strength = float(spec.parameters.get("strength", 0.0))
    dataset = generate_dataset(spec.random_seed, spec.detection_id, variant, strength)
    raw = evaluate_detection(detection, dataset)
    return ExperimentResult(
        run_id=run_id,
        detection_id=spec.detection_id,
        experiment_type=spec.experiment_type,
        random_seed=spec.random_seed,
        parameters={**spec.parameters, "variant": variant, "strength": strength, "dataset_id": dataset["dataset_id"]},
        metrics={k: float(raw[k]) for k in METRIC_KEYS},
        raw_results=raw,
        execution_time=time.perf_counter() - t0,
    )
