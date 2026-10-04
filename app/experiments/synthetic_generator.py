from __future__ import annotations

import random
from typing import Any


def generate_dataset(seed: int, detection_id: str, variant: str = "baseline") -> dict[str, Any]:
    rnd = random.Random(seed)
    users = [f"user_{i}" for i in range(1, 6)]
    events = []
    for i in range(60):
        events.append(
            {
                "user": rnd.choice(users),
                "hour": rnd.randint(0, 23),
                "event_type": rnd.choice(["auth", "file", "network", "usb", "email", "powershell", "mouse"]),
                "value": rnd.randint(1, 100),
            }
        )
    if detection_id == "D03":
        if variant == "baseline":
            events += [{"event_type": "mouse", "interval_ms": 60000} for _ in range(20)]
        else:
            events += [{"event_type": "mouse", "interval_ms": rnd.randint(45000, 95000)} for _ in range(20)]
    return {
        "dataset_id": f"{detection_id}-{variant}-{seed}",
        "seed": seed,
        "generator_version": "1.0",
        "parameters": {"variant": variant},
        "events": events,
    }
