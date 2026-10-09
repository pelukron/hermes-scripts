#!/usr/bin/env python3
"""gate-doctor.py — toolchain contract check for the quality gate.

Usage::

    uv run python bin/gate-doctor.py   # silent when green, noisy findings otherwise

First step of `make check`: every reader (pre-commit, CI YAML, local docs)
must agree with `[tool.hermes.gate]` before the gate runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.gate_doctor import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
