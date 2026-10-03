from __future__ import annotations

import time

from app.experiments.synthetic_generator import generate_dataset
from app.models.schemas import ExperimentResult, ExperimentSpec
from app.services.detection_engine import evaluate_detection


def run_experiment(run_id: str, spec: ExperimentSpec) -> ExperimentResult:
    t0 = time.perf_counter()
    variant = spec.parameters.get("variant", "baseline")
    dataset = generate_dataset(spec.random_seed, spec.detection_id, variant)
    metric = evaluate_detection(spec.detection_id, dataset)
    return ExperimentResult(
        run_id=run_id,
        detection_id=spec.detection_id,
        experiment_type=spec.experiment_type,
        random_seed=spec.random_seed,
        parameters=spec.parameters,
        metrics={"score": metric["score"]},
        raw_results=metric,
        execution_time=time.perf_counter() - t0,
    )
