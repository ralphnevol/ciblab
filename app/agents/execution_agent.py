"""Execution Agent — Runs the fuzzing experiment.

Scientific method phase: EXPERIMENT
Takes the seed corpus from the Seed Agent, executes each seed against
the vulnerable binary, performs additional mutations, and returns
all crashes found.
"""

from __future__ import annotations

import base64
import random
import time
from uuid import uuid4

from app.experiments.vulnerable_binary import run_target
from app.models.schemas import CrashReport, SeedCorpus


def _mutate(data: bytes, rng: random.Random) -> bytes:
    """Apply a single random mutation to *data*."""
    if not data:
        return b"\x00"
    mutation = rng.choice(["bitflip", "insert", "extend", "truncate"])
    ba = bytearray(data)

    if mutation == "bitflip" and ba:
        idx = rng.randint(0, len(ba) - 1)
        ba[idx] ^= 1 << rng.randint(0, 7)
    elif mutation == "insert":
        idx = rng.randint(0, len(ba))
        ba.insert(idx, rng.randint(0, 255))
    elif mutation == "extend":
        ba.extend(bytes(rng.getrandbits(8) for _ in range(rng.randint(20, 80))))
    elif mutation == "truncate" and len(ba) > 1:
        ba = ba[: rng.randint(1, len(ba) - 1)]

    return bytes(ba)


def run_fuzz_experiment(
    corpus: SeedCorpus,
    seed: int = 42,
    mutation_rounds: int = 10,
) -> list[CrashReport]:
    """Execute the fuzzing experiment.

    1. Run every seed from the corpus against the target.
    2. Perform *mutation_rounds* additional mutations on each seed.
    3. Collect and de-duplicate crashes.
    """
    rng = random.Random(seed)
    crashes: list[CrashReport] = []
    seen_inputs: set[str] = set()
    start = time.perf_counter()

    # Phase 1: direct seed execution
    for entry in corpus.seeds:
        data = base64.b64decode(entry.content_b64)
        result = run_target(data)
        hex_key = data.hex()

        if result.crashed and hex_key not in seen_inputs:
            seen_inputs.add(hex_key)
            crashes.append(CrashReport(
                crash_id=f"crash-{uuid4().hex[:8]}",
                input_filename=entry.filename,
                input_hex=hex_key,
                signal=result.signal,
                exit_code=result.exit_code,
                stderr_snippet=result.stderr[:200],
            ))

    # Phase 2: mutation-based fuzzing
    for entry in corpus.seeds:
        original = base64.b64decode(entry.content_b64)
        for _ in range(mutation_rounds):
            mutated = _mutate(original, rng)
            result = run_target(mutated)
            hex_key = mutated.hex()

            if result.crashed and hex_key not in seen_inputs:
                seen_inputs.add(hex_key)
                crashes.append(CrashReport(
                    crash_id=f"crash-{uuid4().hex[:8]}",
                    input_filename=f"mutated_{entry.filename}",
                    input_hex=hex_key,
                    signal=result.signal,
                    exit_code=result.exit_code,
                    stderr_snippet=result.stderr[:200],
                ))

    elapsed = time.perf_counter() - start

    return crashes
