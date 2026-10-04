from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.models.schemas import Detection

ROOT = Path(__file__).resolve().parents[2]
DETECTIONS_FILE = ROOT / "data" / "detections" / "detections.json"
SEALED_FILE = ROOT / "data" / "ground_truth" / "sealed_labels.json"


def load_detections() -> list[Detection]:
    raw = json.loads(DETECTIONS_FILE.read_text())
    return [Detection(**item) for item in raw]


def sealed_hash() -> str:
    return hashlib.sha256(SEALED_FILE.read_bytes()).hexdigest()


def load_labels_for_evaluation() -> dict[str, str]:
    return json.loads(SEALED_FILE.read_text())
