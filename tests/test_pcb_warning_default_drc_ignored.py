"""Synthetic source-bound review of ignored Warning-default PCB DRC checks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_global_severity_review import (
    ignored_warning_default_native_drc_check_candidates,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-warning-default-drc-ignored"
RULE_ID = "pcb.warning_default_drc_check_ignored"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
EXPECTED_CHECK_IDS = (
    "connection_width",
    "copper_sliver",
    "duplicate_footprints",
    "extra_footprint",
    "hole_to_hole",
    "holes_co_located",
    "isolated_copper",
    "lib_footprint_issues",
    "lib_footprint_mismatch",
    "mirrored_text_on_front_layer",
    "missing_footprint",
    "missing_tuning_profile",
    "net_conflict",
    "nonmirrored_text_on_back_layer",
    "padstack",
    "schematic_fields_parity",
    "schematic_parity",
    "silk_edge_clearance",
    "silk_over_copper",
    "silk_overlap",
    "text_height",
    "text_thickness",
    "track_dangling",
    "via_dangling",
)


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


def _scan(root: Path, config: ProjectConfig, source_hashes: Mapping[str, str]):
    return ignored_warning_default_native_drc_check_candidates(root, config, source_hashes)


@pytest.mark.parametrize(
    "kicad_version", ("10.0.0", "10.0.3", "10.0.4", "10.0.5", "10.0.6", "10.0.7")
)
@pytest.mark.parametrize("kind", (ProjectKind.PCB, ProjectKind.PCB_ONLY))
def test_ignored_warning_default_checks_create_source_bound_review_candidates(
    tmp_path: Path, kicad_version: str, kind: ProjectKind
) -> None:
    root, project, config, source_hashes = _project(
        tmp_path, kicad_version=kicad_version, kind=kind
    )

    candidates = _scan(root, config, source_hashes)

    assert tuple(item.evidence["check_id"][0] for item in candidates) == EXPECTED_CHECK_IDS
    first = candidates[0]
    assert first.rule_id == RULE_ID
    assert first.subject == (
        f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/connection_width"
    )
    assert "configured as Ignore" in first.message
    assert first.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (kicad_version,),
        "check_id": ("connection_width",),
        "configured_severity": ("ignore",),
    }


def test_warning_defaults_and_unrelated_ignored_checks_are_valid_controls(
    tmp_path: Path,
) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control.kicad_pro")

    assert _scan(root, config, source_hashes) == ()


@pytest.mark.parametrize("version", ("10.0.1", "10.0.2", "10.1.0", "11.0.0"))
def test_unreviewed_patch_profiles_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(tmp_path, kicad_version=version)

    assert _scan(root, config, source_hashes) == ()


def test_non_pcb_project_is_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=ProjectKind.SCHEMATIC)

    assert _scan(root, config, source_hashes) == ()


def test_changed_settings_after_source_hash_capture_fail_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text('{"board":{"design_settings":{"rule_severities":{}}}}', encoding="utf-8")

    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, source_hashes)


def test_json_key_order_does_not_change_review_candidate_order(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":'
        '{"via_dangling":"ignore","connection_width":"ignore"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    first = _scan(root, config, source_hashes)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":'
        '{"connection_width":"ignore","via_dangling":"ignore"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)

    assert tuple(item.subject for item in _scan(root, config, source_hashes)) == tuple(
        item.subject for item in first
    )


def test_ignored_warning_default_findings_use_standard_review_policy(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    report = evaluate(
        "synthetic-warning-default-drc",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_native_drc_candidates=_scan(root, config, source_hashes),
    )

    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert len(findings) == len(EXPECTED_CHECK_IDS)
    assert all(item.mode == "review" and item.disposition == "OPEN" for item in findings)
