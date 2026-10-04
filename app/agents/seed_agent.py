"""Seed Agent — Hypothesis generation and corpus creation.

Scientific method phase: EVIDENCE → HYPOTHESIS
This agent analyzes the fuzz target, formulates a hypothesis about which
input patterns will trigger crashes, and generates a seed corpus.
"""

from __future__ import annotations

import base64
import os
import random
import string
from uuid import uuid4

from dotenv import load_dotenv

from app.models.schemas import FuzzTarget, SeedCorpus, SeedEntry

load_dotenv()


def _generate_hypothesis_with_llm(target: FuzzTarget) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = (
            f"You are a cybersecurity research specialist in fuzzing and memory safety.\n"
            f"Formulate a concise, rigorous scientific hypothesis (2-3 sentences) predicting what inputs "
            f"will trigger memory corruption crashes in this target parser:\n"
            f"Target Name: {target.name}\n"
            f"Description: {target.description}\n"
            f"Input Format: {target.input_format}\n"
            f"Known Constraints: {', '.join(target.known_constraints)}\n"
            f"Return only the scientific hypothesis statement."
        )
        resp = client.chat.completions.create(
            model="gpt-6-luna",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        return None


def _generate_seeds(target: FuzzTarget, seed: int = 42) -> list[SeedEntry]:
    """Generate 5 seed files with different mutation strategies."""
    rng = random.Random(seed)
    seeds: list[SeedEntry] = []

    # Seed 1: Oversized input (boundary mutation)
    long_payload = "A" * 128
    seeds.append(SeedEntry(
        filename="seed_overflow.txt",
        content_b64=base64.b64encode(long_payload.encode()).decode(),
        mutation_strategy="boundary_overflow",
        rationale="Input exceeding expected buffer size to test boundary handling",
    ))

    # Seed 2: Null byte injection
    null_payload = b"VALID\x00INJECTED"
    seeds.append(SeedEntry(
        filename="seed_nullbyte.bin",
        content_b64=base64.b64encode(null_payload).decode(),
        mutation_strategy="null_injection",
        rationale="Embedded null bytes to test string termination assumptions",
    ))

    # Seed 3: Format string tokens
    fmt_payload = "%s%s%s%n"
    seeds.append(SeedEntry(
        filename="seed_fmtstr.txt",
        content_b64=base64.b64encode(fmt_payload.encode()).decode(),
        mutation_strategy="format_string",
        rationale="Format string specifiers to test printf-family handling",
    ))

    # Seed 4: Random binary blob
    blob = bytes(rng.getrandbits(8) for _ in range(rng.randint(32, 100)))
    seeds.append(SeedEntry(
        filename="seed_random.bin",
        content_b64=base64.b64encode(blob).decode(),
        mutation_strategy="random_binary",
        rationale="Random bytes to explore unexpected parser states",
    ))

    # Seed 5: Valid-looking input with edge chars
    edge = "".join(rng.choices(string.printable, k=60)) + "\xff\xfe"
    seeds.append(SeedEntry(
        filename="seed_edge.txt",
        content_b64=base64.b64encode(edge.encode("latin-1")).decode(),
        mutation_strategy="edge_characters",
        rationale="Printable string with trailing high-byte characters",
    ))

    return seeds


def generate_corpus(
    case_id: str,
    target: FuzzTarget,
    seed: int = 42,
) -> SeedCorpus:
    """Analyze target and produce hypothesis + seed corpus.

    Uses GPT-6 Luna when available, falling back to deterministic template.
    """
    seeds = _generate_seeds(target, seed)

    llm_hypothesis = _generate_hypothesis_with_llm(target)
    if llm_hypothesis:
        hypothesis = llm_hypothesis
    else:
        hypothesis = (
            f"The target '{target.name}' processes {target.input_format} input "
            f"with implicit size and encoding assumptions. "
            f"Sending inputs that violate these assumptions — oversized payloads, "
            f"embedded control characters, or format string tokens — will expose "
            f"memory safety vulnerabilities in the parser."
        )

    return SeedCorpus(
        case_id=case_id,
        target_id=target.target_id,
        hypothesis=hypothesis,
        seeds=seeds,
        confidence=0.88 if llm_hypothesis else 0.78,
    )
