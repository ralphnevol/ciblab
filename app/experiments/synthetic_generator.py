from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

GENERATOR_VERSION = "2.0"
WORLD_FILE = Path(__file__).resolve().parents[2] / "data" / "simulation" / "world_profiles.json"

# Dataset shapes per variant: (users, days, benign events per user-day, injected malicious events)
VARIANT_SHAPES = {
    "baseline": (20, 5, 20, 100),
    "evasion": (20, 5, 20, 100),
    "alert_volume": (50, 30, 20, 0),
}


@lru_cache(maxsize=1)
def _world() -> dict[str, Any]:
    # Environment-side parameters of the simulated world. Agents never read this file;
    # they only observe the datasets generated from it.
    return json.loads(WORLD_FILE.read_text())


def generate_dataset(seed: int, detection_id: str, variant: str = "baseline", strength: float = 0.0) -> dict[str, Any]:
    world = _world()
    profile = world["detections"][detection_id]
    users, days, per_user_day, n_malicious = VARIANT_SHAPES[variant]
    # Baseline and evasion variants share the same random stream, so an evasion run is a
    # paired comparison: identical events, with only the malicious signal shifted.
    stream = "alert_volume" if variant == "alert_volume" else "efficacy"
    rnd = random.Random(f"{seed}:{detection_id}:{stream}")
    shift = strength * profile["evasion_capacity"] if variant == "evasion" else 0.0

    events = []
    for _ in range(users * days * per_user_day):
        events.append(
            {
                "user": f"user_{rnd.randrange(users):02d}",
                "day": rnd.randrange(days),
                "signal": rnd.gauss(world["benign_mean"], 1.0),
                "injected_malicious": False,
                "sibling_alerted": False,
            }
        )
    for _ in range(n_malicious):
        signal = rnd.gauss(profile["malicious_mean"], 1.0)
        sibling = rnd.random() < profile["overlap"]
        events.append(
            {
                "user": f"user_{rnd.randrange(users):02d}",
                "day": rnd.randrange(days),
                "signal": signal - shift,
                "injected_malicious": True,
                "sibling_alerted": sibling,
            }
        )
    return {
        "dataset_id": f"{detection_id}-{variant}-s{strength:g}-{seed}",
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": {
            "variant": variant,
            "strength": strength,
            "users": users,
            "days": days,
            "evasion_technique": profile["technique"] if variant == "evasion" else None,
            "sibling_detection": profile["overlaps_with"],
        },
        "events": events,
    }
