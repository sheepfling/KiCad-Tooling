"""Source-bound regressions for missing embedded library-symbol definitions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_source_integrity import (
    missing_embedded_library_symbol_candidates,
)

RULE_ID = "schematic.missing_embedded_symbol_definition"
PROJECT = "projects/synthetic/kicad/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/kicad/controller.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/missing-embedded-symbol-definition"
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
    version: str = "10.0.5",
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


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return missing_embedded_library_symbol_candidates(root, config, source_hashes)


def test_missing_definition_fault_is_localized_and_control_is_quiet(tmp_path: Path) -> None:
    fault_root, config, fault_hashes = _project(tmp_path / "fault", "fault.kicad_sch")
    control_root, control_config, control_hashes = _project(
        tmp_path / "control", "control.kicad_sch"
    )

    (candidate,) = _scan(fault_root, config, fault_hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":J1")
    assert "Connector:USB_A" in candidate.message
    assert candidate.evidence["source_path"] == (SCHEMATIC,)
    assert candidate.evidence["source_sha256"] == (fault_hashes[SCHEMATIC],)
    assert candidate.evidence["reference"] == ("J1",)
    assert candidate.evidence["library_id"] == ("Connector:USB_A",)
    assert candidate.evidence["symbol_uuid"] == ("48000000-0000-4000-8000-000000000210",)
    assert _scan(control_root, control_config, control_hashes) == ()


def test_irrelevant_source_edit_preserves_the_finding_and_refreshes_its_hash(
    tmp_path: Path,
) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch")
    (before,) = _scan(root, config, source_hashes)
    schematic_path = root / SCHEMATIC
    content = schematic_path.read_bytes().replace(
        b"Synthetic USB direct peer reference review",
        b"Synthetic USB source integrity review",
    )
    schematic_path.write_bytes(content)
    source_hashes[SCHEMATIC] = digest(schematic_path)

    first = _scan(root, config, source_hashes)
    second = _scan(root, config, source_hashes)

    assert first == second
    assert len(first) == 1
    assert first[0].subject == before.subject
    assert first[0].evidence["source_sha256"] == (source_hashes[SCHEMATIC],)
    assert first[0].evidence["source_sha256"] != before.evidence["source_sha256"]


def test_source_inventory_must_match_current_schematic_bytes(tmp_path: Path) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch")
    source = root / SCHEMATIC
    source.write_bytes(source.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, source_hashes)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.6", "10.0.8", "11.0.0"))
def test_native_evidence_version_boundary_is_exact(tmp_path: Path, version: str) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch", version=version)

    assert _scan(root, config, source_hashes) == ()


def test_pcb_only_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, config, source_hashes = _project(
        tmp_path,
        "fault.kicad_sch",
        kind=ProjectKind.PCB_ONLY,
    )

    assert _scan(root, config, source_hashes) == ()
