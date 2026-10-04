from __future__ import annotations

import shutil
from pathlib import Path

from app.mcp_tools import ROLE_TOOLS

BUNDLE = Path(__file__).resolve().parents[2] / "omnigent" / "triage_lab"


def detect_omnigent() -> dict:
    # Omnigent runs as its own tool (`omni host` / `omnigent run`) and calls into the lab over MCP,
    # so the lab only reports whether the CLI and the agent bundle are present.
    cli = shutil.which("omnigent") or shutil.which("omni")
    return {
        "cli": cli,
        "bundle": str(BUNDLE) if (BUNDLE / "config.yaml").exists() else None,
        "mcp_endpoints": {role: f"/lab/{role}/mcp" for role in ROLE_TOOLS},
        "mode": "agentic_ready" if cli else "deterministic_only",
    }
