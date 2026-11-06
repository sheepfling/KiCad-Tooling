"""Shared isolated pytest collection for design-lint rule markers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def collect_rule_nodes(rule_ids: str | tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    """Collect tests selected by one or more design-lint rule identifiers."""
    environment = os.environ.copy()
    environment.pop("KICAD_TEMPLATE_ROOT", None)
    return subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "pytest",
            "-q",
            "--collect-only",
            "-m",
            " or ".join(
                f'design_lint_rule(rule_id="{rule_id}")'
                for rule_id in ((rule_ids,) if isinstance(rule_ids, str) else rule_ids)
            ),
        ),
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
