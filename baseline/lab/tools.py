import csv

KEEP_PRECISION = 0.25
DECOM_PRECISION = 0.05
DECOM_MIN_FIRES = 10


def verdict(precision, fires, healthy):
    if not healthy:
        return "investigate"  # can't trust precision on a broken data source
    if precision >= KEEP_PRECISION:
        return "keep"
    if precision < DECOM_PRECISION and fires >= DECOM_MIN_FIRES:
        return "decommission"
    return "investigate"


def score_detections(path):
    rows = []
    for r in csv.DictReader(open(path)):
        fires, tp = int(r["fires_30d"]), int(r["true_positives"])
        mins = float(r["analyst_minutes_per_alert"])
        healthy = r["data_source_healthy"].lower() == "true"
        precision = tp / fires if fires else 0.0
        rows.append({
            **r,
            "fires": fires,
            "tp": tp,
            "healthy": healthy,
            "last_tuned_days": int(r["last_tuned_days"]),
            "precision": precision,
            "cost_hours": fires * mins / 60,
            "verdict": verdict(precision, fires, healthy),
        })
    return rows
