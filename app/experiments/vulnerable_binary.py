"""Synthetic vulnerable parser — simulates a C binary with memory safety bugs.

This module provides a deterministic 'binary' that processes stdin input
and crashes on specific patterns. It is the fuzz target for the lab.

The parser has three intentional vulnerabilities:
  1. Buffer overflow: inputs longer than 64 bytes
  2. Null-byte injection: embedded \\x00 in the middle of input
  3. Format-string bug: inputs containing %n or %s sequences

Each crash is deterministic given the same input, enabling reproducibility.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from enum import IntEnum


class Signal(IntEnum):
    """Unix signal codes for crash classification."""
    SIGSEGV = 11
    SIGABRT = 6
    SIGFPE = 8


@dataclass
class ExecutionResult:
    """Result of running the vulnerable binary on a single input."""
    exit_code: int
    signal: int
    stdout: str
    stderr: str
    crashed: bool


# ── Internal parser (the 'binary') ──────────────────────────────────

_BUFFER_LIMIT = 64


def _parse_input(data: bytes) -> ExecutionResult:
    """Simulate a vulnerable C parser processing *data*.

    The parser is intentionally broken:
    - Inputs > 64 bytes trigger a buffer overflow (SIGSEGV).
    - Embedded null bytes trigger an abort (SIGABRT).
    - Format-string tokens (%n, %s) trigger a segfault (SIGSEGV).
    - All other inputs are parsed successfully.
    """

    # ── Vulnerability 1: buffer overflow ─────────────────────────
    if len(data) > _BUFFER_LIMIT:
        return ExecutionResult(
            exit_code=139,
            signal=Signal.SIGSEGV,
            stdout="",
            stderr=f"*** buffer overflow detected ***: input length {len(data)} exceeds buffer of {_BUFFER_LIMIT}",
            crashed=True,
        )

    # ── Vulnerability 2: null-byte injection ─────────────────────
    if b"\x00" in data[:-1]:  # ignore trailing null
        return ExecutionResult(
            exit_code=134,
            signal=Signal.SIGABRT,
            stdout="",
            stderr="Aborted: unexpected null byte in input stream",
            crashed=True,
        )

    # ── Vulnerability 3: format string ───────────────────────────
    text = data.decode("utf-8", errors="replace")
    if "%n" in text or "%s" in text:
        return ExecutionResult(
            exit_code=139,
            signal=Signal.SIGSEGV,
            stdout="",
            stderr="Segmentation fault: format string vulnerability triggered",
            crashed=True,
        )

    # ── Normal execution ─────────────────────────────────────────
    digest = hashlib.sha256(data).hexdigest()[:16]
    return ExecutionResult(
        exit_code=0,
        signal=0,
        stdout=f"OK parsed {len(data)} bytes [sha256:{digest}]",
        stderr="",
        crashed=False,
    )


def run_target(data: bytes) -> ExecutionResult:
    """Public entry point — run the vulnerable binary on *data*."""
    return _parse_input(data)


# Allow running as a standalone script for testing:
#   echo "AAAA..." | python -m app.experiments.vulnerable_binary
if __name__ == "__main__":
    raw = sys.stdin.buffer.read()
    result = run_target(raw)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    sys.exit(result.exit_code)
