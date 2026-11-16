"""Source-bound regressions for the reserved placed-symbol ``dnp`` field."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_reserved_dnp_property import (
    source_bound_reserved_dnp_property_candidates,
)

RULE_ID = "schematic.reserved_dnp_property_collision"
PROJECT = "projects/synthetic/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/controller.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/reserved-dnp-property"
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


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_reserved_dnp_property_candidates(root, config, source_hashes)


def test_placed_dnp_property_is_localized_and_controls_are_quiet(tmp_path: Path) -> None:
    cases = (
        ("fault-custom-only-yes.kicad_sch", "no", ("yes",)),
        ("fault-native-yes-custom-no.kicad_sch", "yes", ("no",)),
    )
    for index, (fixture, native_dnp, values) in enumerate(cases):
        root, config, hashes = _project(tmp_path / f"fault-{index}", fixture)
        (candidate,) = _scan(root, config, hashes)

        assert candidate.rule_id == RULE_ID
        assert candidate.subject.endswith(":J1")
        assert candidate.evidence["source_path"] == (SCHEMATIC,)
        assert candidate.evidence["source_sha256"] == (hashes[SCHEMATIC],)
        assert candidate.evidence["reference"] == ("J1",)
        assert candidate.evidence["symbol_uuid"] == ("48000000-0000-4000-8000-000000000210",)
        assert candidate.evidence["native_dnp"] == (native_dnp,)
        assert candidate.evidence["property_values"] == values
        assert len(candidate.evidence["property_lines"]) == 1

    for index, fixture in enumerate(
        ("control.kicad_sch", "control-native-dnp.kicad_sch", "control-library-only.kicad_sch")
    ):
        root, config, hashes = _project(tmp_path / f"control-{index}", fixture)
        assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize("version", ("10.0.1", "10.0.6", "10.0.7", "10.0.9", "11.0.0"))
def test_native_version_boundary_is_exact(tmp_path: Path, version: str) -> None:
    root, config, hashes = _project(
        tmp_path,
        "fault-custom-only-yes.kicad_sch",
        version=version,
    )

    assert _scan(root, config, hashes) == ()


def test_pcb_only_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, config, hashes = _project(
        tmp_path,
        "fault-custom-only-yes.kicad_sch",
        kind=ProjectKind.PCB_ONLY,
    )

    assert _scan(root, config, hashes) == ()


def test_finding_is_deterministic_and_bound_to_current_source(tmp_path: Path) -> None:
    root, config, hashes = _project(tmp_path, "fault-custom-only-yes.kicad_sch")
    first = _scan(root, config, hashes)
    assert first == _scan(root, config, hashes)

    source = root / SCHEMATIC
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, hashes)

    with pytest.raises(ValueError, match="absent from the source-bound hashes"):
        _scan(root, config, {})
