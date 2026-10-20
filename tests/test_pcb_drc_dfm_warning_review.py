"""Synthetic source-bound review of downgraded DFM DRC severities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_global_severity_review import (
    warning_dfm_native_drc_check_candidates,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-dfm-drc-warning"
RULE_ID = "pcb.dfm_drc_check_warning"
PROJECT_RELATIVE = "projects/controller.kicad_pro"


def _project(
    tmp_path: Path,
    fixture: str = "fault.kicad_pro",
    *,
    kicad_version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=kind,
            project=PROJECT_RELATIVE,
            kicad_version=kicad_version,
        ),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return warning_dfm_native_drc_check_candidates(root, config, source_hashes)


@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_documented_error_default_dfm_checks_configured_as_warning_prompt_for_review(
    tmp_path: Path, kicad_version: str
) -> None:
    root, project, config, source_hashes = _project(tmp_path, kicad_version=kicad_version)

    candidates = _scan(root, config, source_hashes)

    assert tuple(item.evidence["check_id"][0] for item in candidates) == (
        "hole_clearance",
        "solder_mask_bridge",
        "track_width",
    )
    first = candidates[0]
    assert first.rule_id == RULE_ID
    assert (
        first.subject == f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/hole_clearance"
    )
    assert "confirm that lowering its severity is intentional" in first.message
    assert first.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (kicad_version,),
        "check_id": ("hole_clearance",),
        "configured_severity": ("warning",),
    }


def test_error_defaults_and_warning_settings_outside_dfm_scope_are_valid_controls(
    tmp_path: Path,
) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control.kicad_pro")

    assert _scan(root, config, source_hashes) == ()


@pytest.mark.parametrize("version", ("9.0.7", "10.1.0", "11.0.0"))
def test_versions_outside_reviewed_kicad_10_0_profile_are_out_of_scope(
    tmp_path: Path, version: str
) -> None:
    root, _, config, source_hashes = _project(tmp_path, kicad_version=version)

    assert _scan(root, config, source_hashes) == ()


def test_non_pcb_project_is_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=ProjectKind.SCHEMATIC)

    assert _scan(root, config, source_hashes) == ()


def test_json_key_order_does_not_change_warning_candidates(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    first_source = (
        '{"board":{"design_settings":{"rule_severities":'
        '{"track_width":"warning","hole_clearance":"warning"}}}}'
    )
    second_source = (
        '{"board":{"design_settings":{"rule_severities":'
        '{"hole_clearance":"warning","track_width":"warning"}}}}'
    )
    project.write_text(first_source, encoding="utf-8")
    source_hashes[PROJECT_RELATIVE] = digest(project)
    first = _scan(root, config, source_hashes)
    project.write_text(second_source, encoding="utf-8")
    source_hashes[PROJECT_RELATIVE] = digest(project)

    second = _scan(root, config, source_hashes)

    assert tuple(item.subject for item in second) == tuple(item.subject for item in first)
    assert tuple(item.evidence["check_id"] for item in second) == tuple(
        item.evidence["check_id"] for item in first
    )


def test_warning_finding_uses_standard_default_review_policy(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    candidate = _scan(root, config, source_hashes)[0]
    report = evaluate(
        "synthetic-dfm-drc-warning",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_native_drc_candidates=(candidate,),
    )

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"
