"""Experiment runner CLI. Input: JSON list of specs (file path or stdin). Independent experiments run in parallel;
each aggregates over 20 fixed seeds. A control experiment is added (no-op replay identical, disable-all detects
nothing, determinism). Reports parallel wall time vs the sum of per-experiment times (sequential equivalent).
ALL DATA IS SYNTHETIC."""
import json, sys, time
from concurrent.futures import ProcessPoolExecutor
from sim.core import run_experiment, SEEDS


def run_all(specs):
    t0 = time.time()
    specs = [{"id": "CONTROL", "type": "control"}] + specs
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(run_experiment, specs))
    wall = time.time() - t0
    seq = sum(r["duration_s"] for r in results)
    return {"seeds": [SEEDS[0], SEEDS[-1]], "n_seeds": len(SEEDS), "n_experiments": len(results),
            "wall_seconds_parallel": round(wall, 2), "sum_experiment_seconds_sequential": round(seq, 2),
            "results": results}


if __name__ == "__main__":
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run_all(json.loads(src)), indent=1))
