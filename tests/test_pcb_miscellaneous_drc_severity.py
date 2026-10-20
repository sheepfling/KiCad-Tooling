"""Synthetic source-bound review of lowered miscellaneous DRC severities."""

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
    downgraded_miscellaneous_drc_check_candidates,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-miscellaneous-drc-severity"
RULE_ID = "pcb.miscellaneous_drc_check_downgraded"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
EXPECTED_CHECKS = (
    ("footprint", "warning"),
    ("item_on_disabled_layer", "ignore"),
    ("items_not_allowed", "warning"),
    ("npth_inside_courtyard", "ignore"),
    ("pth_inside_courtyard", "warning"),
    ("text_on_edge_cuts", "ignore"),
    ("through_hole_pad_without_hole", "warning"),
    ("unresolved_variable", "ignore"),
    ("zones_intersect", "warning"),
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


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return downgraded_miscellaneous_drc_check_candidates(root, config, source_hashes)


@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
@pytest.mark.parametrize("kind", (ProjectKind.PCB, ProjectKind.PCB_ONLY))
def test_error_default_miscellaneous_checks_configured_below_error_create_review_candidates(
    tmp_path: Path, kicad_version: str, kind: ProjectKind
) -> None:
    root, project, config, source_hashes = _project(
        tmp_path, kicad_version=kicad_version, kind=kind
    )

    candidates = _scan(root, config, source_hashes)

    assert (
        tuple(
            (item.evidence["check_id"][0], item.evidence["configured_severity"][0])
            for item in candidates
        )
        == EXPECTED_CHECKS
    )
    first = candidates[0]
    assert first.rule_id == RULE_ID
    assert first.subject == (f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/footprint")
    assert "configured as Warning" in first.message
    assert candidates[1].message.endswith(
        "configured as Ignore; confirm lowering its severity is intentional."
    )
    assert first.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (kicad_version,),
        "check_id": ("footprint",),
        "configured_severity": ("warning",),
    }


def test_error_defaults_and_other_miscellaneous_overrides_are_valid_controls(
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


def test_changed_settings_after_source_hash_capture_fail_closed(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text('{"board":{"design_settings":{"rule_severities":{}}}}', encoding="utf-8")

    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, source_hashes)


def test_json_key_order_does_not_change_review_candidate_order(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":'
        '{"zones_intersect":"warning","footprint":"warning"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)
    first = _scan(root, config, source_hashes)
    project.write_text(
        '{"board":{"design_settings":{"rule_severities":'
        '{"footprint":"warning","zones_intersect":"warning"}}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)

    second = _scan(root, config, source_hashes)

    assert tuple(item.subject for item in second) == tuple(item.subject for item in first)


def test_downgraded_findings_use_standard_default_review_policy(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    report = evaluate(
        "synthetic-miscellaneous-severity",
        coach(NetlistContract(components={}, nets={})),
        DesignLintPolicy(),
        pcb_native_drc_candidates=_scan(root, config, source_hashes),
    )

    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert len(findings) == len(EXPECTED_CHECKS)
    assert all(item.mode == "review" and item.disposition == "OPEN" for item in findings)
