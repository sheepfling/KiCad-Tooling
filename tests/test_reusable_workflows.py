"""Guard the trust boundary of workflows executed inside an adopting repository."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"
PROJECT_WORKFLOWS = (
    "kicad-template.yml",
    "3d-preview.yml",
    "electrical-analysis.yml",
    "release-candidate.yml",
)


@pytest.mark.parametrize("name", PROJECT_WORKFLOWS)
def test_project_jobs_check_out_caller_source_and_install_its_reviewed_pin(name: str) -> None:
    workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
    jobs = workflow.split("\njobs:\n", 1)[1]
    checkouts = jobs.count("uses: actions/checkout@")
    assert checkouts > 0
    assert checkouts == jobs.count("-r requirements-tooling.txt")
    assert checkouts == jobs.count("persist-credentials: false")
    # No provider checkout, ref override, or alternate workspace may replace
    # the adopting repository and its pull-request merge commit.
    assert not re.search(r"(?m)^\s+(repository|ref|working-directory):", jobs)
    assert "KICAD_TEMPLATE_ROOT" not in jobs
    assert "PYTHONPATH" not in jobs


@pytest.mark.parametrize("name", PROJECT_WORKFLOWS)
def test_calls_cannot_elevate_permissions_or_interpolate_inputs_into_shell(name: str) -> None:
    workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
    assert "  workflow_call:\n" in workflow
    assert "permissions:\n  contents: read\n" in workflow
    for forbidden in (
        "secrets:",
        "write-all",
        ": write",
        "pull_request_target:",
        "continue-on-error:",
        "concurrency:",
    ):
        assert forbidden not in workflow
    for command in re.findall(r"(?ms)^\s+run:.*?(?=^\s+- |\Z)", workflow):
        assert "${{ inputs." not in command
    for action in re.findall(r"uses: ([^\s]+)", workflow):
        assert re.fullmatch(r"[\w/-]+@[0-9a-f]{40}", action)


@pytest.mark.parametrize("name", PROJECT_WORKFLOWS[1:])
def test_manual_lanes_keep_failure_receipts(name: str) -> None:
    workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
    assert "      project_id:\n" in workflow
    assert "        required: true\n        type: string" in workflow
    assert "if: always()" in workflow
    assert "build/ci-hosted/" in workflow
    assert "retention-days: 30" in workflow
