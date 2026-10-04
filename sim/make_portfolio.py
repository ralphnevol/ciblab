"""Derive data/portfolio.csv from the seeded 30-day BASELINE window (natural attack prevalence) so the portfolio and the
replay come from one generator. Also writes data/portfolio_truth.csv (ground truth, for the reconciliation table).
ALL DATA IS SYNTHETIC. Run: python3 -m sim.make_portfolio"""
import csv, os, random
from . import catalog as C
from .core import BASELINE_SEED, ROOT, SEEDS, replay


def main():
    per, caught, scen = replay(BASELINE_SEED, mode="baseline")
    rng = random.Random(BASELINE_SEED + 1)  # analyst confirmation draw, independent of event generation
    rows, truth = [], []
    for r in C.RULES:
        p = per[r["id"]]
        q = C.CONFIRM_PROB.get(r["id"], C.CONFIRM_PROB["default"])
        confirmed = sum(rng.random() < q for _ in range(p["tp"]))
        rows.append([r["id"], r["name"], r["tech"], p["alerts"], confirmed, r["mins"], r["tuned"], str(r["healthy"]).lower()])
        truth.append([r["id"], p["alerts"], p["tp"], confirmed, round(sum(replay(s)[0][r["id"]]["tp"] for s in SEEDS) / len(SEEDS), 2)])
    d = os.path.join(ROOT, "data")
    with open(os.path.join(d, "portfolio.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow("detection_id,name,mitre_technique,fires_30d,true_positives,analyst_minutes_per_alert,last_tuned_days,data_source_healthy".split(","))
        w.writerows(rows)
    with open(os.path.join(d, "portfolio_truth.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["detection_id", "baseline_alerts", "baseline_ground_truth_tp", "baseline_confirmed_tp", "replay_tp_mean_over_seeds"])
        w.writerows(truth)
    print(f"wrote {len(rows)} rules; baseline window scenarios: {len(scen)}")


if __name__ == "__main__":
    main()
