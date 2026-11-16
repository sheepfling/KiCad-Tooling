"""Source-bound regressions for conflicting duplicate user symbol fields."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_conflicting_placed_custom_properties import (
    source_bound_conflicting_placed_custom_property_candidates,
)

RULE_ID = "schematic.conflicting_placed_custom_properties"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/conflicting-placed-custom-properties"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str,
    *,
    version: str = "10.0.8",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    source = root / SCHEMATIC
    source.parent.mkdir(parents=True)
    source.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=Path(PROJECT), kicad_version=version),
    )
    return root, config, {SCHEMATIC: digest(source)}


def _scan(root: Path, config: ProjectConfig, hashes: dict[str, str]):
    return source_bound_conflicting_placed_custom_property_candidates(root, config, hashes)


def test_conflicting_placed_custom_property_is_localized_and_controls_are_quiet(
    tmp_path: Path,
) -> None:
    root, config, hashes = _project(tmp_path / "fault", "fault.kicad_sch")

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":J1:MFR_PN")
    assert candidate.evidence["source_path"] == (SCHEMATIC,)
    assert candidate.evidence["source_sha256"] == (hashes[SCHEMATIC],)
    assert candidate.evidence["reference"] == ("J1",)
    assert candidate.evidence["symbol_uuid"] == ("48000000-0000-4000-8000-000000000210",)
    assert candidate.evidence["property_name"] == ("MFR_PN",)
    assert candidate.evidence["property_values"] == ("SYNTHETIC-PN-A", "SYNTHETIC-PN-B")
    assert len(candidate.evidence["property_lines"]) == 2

    for fixture in (
        "control-unique.kicad_sch",
        "control-identical-duplicates.kicad_sch",
        "control-distinct-names.kicad_sch",
        "control-case-distinct-names.kicad_sch",
        "control-standard-description.kicad_sch",
        "control-reserved-ki-prefix.kicad_sch",
        "control-library-only-conflict.kicad_sch",
    ):
        control_root, control_config, control_hashes = _project(tmp_path / fixture, fixture)
        assert _scan(control_root, control_config, control_hashes) == ()


@pytest.mark.parametrize("version", ("9.0.6", "10.0.1", "10.0.7", "10.0.9", "11.0.0"))
def test_native_evidence_version_boundary_is_exact(tmp_path: Path, version: str) -> None:
    root, config, hashes = _project(tmp_path, "fault.kicad_sch", version=version)

    assert _scan(root, config, hashes) == ()


def test_pcb_only_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, config, hashes = _project(
        tmp_path,
        "fault.kicad_sch",
        kind=ProjectKind.PCB_ONLY,
    )

    assert _scan(root, config, hashes) == ()


def test_current_source_hash_is_required(tmp_path: Path) -> None:
    root, config, hashes = _project(tmp_path, "fault.kicad_sch")
    source = root / SCHEMATIC
    source.write_bytes(source.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, hashes)


def test_repeated_scan_is_deterministic_and_missing_hash_blocks(tmp_path: Path) -> None:
    root, config, hashes = _project(tmp_path, "fault.kicad_sch")

    first = _scan(root, config, hashes)

    assert first == _scan(root, config, hashes)
    with pytest.raises(ValueError, match="absent from the source-bound hashes"):
        _scan(root, config, {})
