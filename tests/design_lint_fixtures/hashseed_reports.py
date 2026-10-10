"""Run the complete synthetic lint report probe once per pytest process."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from tests.hashseed_probe_cases import HASHSEED_REPORT_FAMILIES

_FAMILIES_ENV = "KICAD_TEAM_TOOLING_HASHSEED_FAMILIES"
_FULL_REPORT_DATA: tuple[dict[str, object], dict[str, tuple[str, ...]]] | None = None


def hashseed_probe_reports(*, families: tuple[str, ...] | None = None) -> dict[str, object]:
    """Return all reports or just the requested themed report families."""
    global _FULL_REPORT_DATA

    if families is None:
        reports, family_keys = _hashseed_probe_report_data(None)
        _FULL_REPORT_DATA = reports, family_keys
        return reports
    if not families:
        raise ValueError("at least one hash-seed report family is required")
    selected = tuple(sorted(set(families)))
    unknown = sorted(set(selected) - set(HASHSEED_REPORT_FAMILIES))
    if unknown:
        raise ValueError(f"unknown hash-seed report families: {unknown}")
    if _FULL_REPORT_DATA is not None:
        all_reports, all_family_keys = _FULL_REPORT_DATA
        selected_keys = {key for family in selected for key in all_family_keys[family]}
        return {key: value for key, value in all_reports.items() if key in selected_keys}
    reports, _family_keys = _hashseed_probe_report_data(selected)
    return reports


@lru_cache(maxsize=32)
def _hashseed_probe_report_data(
    families: tuple[str, ...] | None,
) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]:
    repository = Path(__file__).resolve().parents[2]
    probe = Path(__file__).resolve().parents[1] / "hashseed_probe.py"
    command = [
        sys.executable,
        "-I",
        "-m",
        "pytest",
        "-q",
        "-s",
        "--override-ini=python_files=hashseed_probe.py",
        str(probe),
    ]
    outputs: list[str] = []
    hash_markers: set[int] = set()
    for _process_index in range(3):
        environment = os.environ.copy()
        environment.pop("PYTHONHASHSEED", None)
        environment.pop(_FAMILIES_ENV, None)
        if families is not None:
            environment[_FAMILIES_ENV] = ",".join(families)
        result = subprocess.run(
            command,
            cwd=repository,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"hash-seed probe failed:\n{result.stdout}\n{result.stderr}"
        payloads = [
            line.removeprefix("DESIGN_LINT_HASHSEED_REPORTS=")
            for line in result.stdout.splitlines()
            if line.startswith("DESIGN_LINT_HASHSEED_REPORTS=")
        ]
        assert len(payloads) == 1, result.stdout
        payload = json.loads(payloads[0])
        assert payload["hash_randomization"] == 1
        hash_markers.add(payload["hash_marker"])
        outputs.append(
            json.dumps(
                {
                    "report_families": payload["report_families"],
                    "reports": payload["reports"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    assert len(hash_markers) == 3, "probe processes did not use distinct hash secrets"
    digests = tuple(hashlib.sha256(output.encode("utf-8")).hexdigest() for output in outputs)
    assert digests[0] == digests[1], "full report JSON changed across hash seeds"
    assert digests[1] == digests[2], "full report JSON changed across hash seeds"
    comparison = json.loads(outputs[0])
    report_families = {
        family: tuple(keys) for family, keys in comparison["report_families"].items()
    }
    expected_families = HASHSEED_REPORT_FAMILIES if families is None else families
    assert tuple(report_families) == expected_families
    return comparison["reports"], report_families
