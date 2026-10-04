from __future__ import annotations

from app.models.schemas import Detection


def evaluate_detection(detection: Detection, dataset: dict) -> dict:
    threshold = detection.parameters["signal_threshold"]
    tp = fp = fn = tn = sibling_hits = 0
    for e in dataset["events"]:
        fired = e["signal"] >= threshold
        if e["injected_malicious"]:
            if fired:
                tp += 1
                sibling_hits += int(e["sibling_alerted"])
            else:
                fn += 1
        elif fired:
            fp += 1
        else:
            tn += 1
    params = dataset["parameters"]
    user_days = params["users"] * params["days"]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
        "alerts_per_user_day": round((tp + fp) / user_days, 4),
        "sibling_overlap": round(sibling_hits / tp, 4) if tp else 0.0,
        "sibling_detection": params["sibling_detection"],
        "evasion_technique": params["evasion_technique"],
        "dataset_id": dataset["dataset_id"],
        "generator_version": dataset["generator_version"],
    }
