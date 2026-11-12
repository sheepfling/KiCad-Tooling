"""Source-bound regressions for embedded and placed symbol pin-number mismatch."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_source_integrity import (
    embedded_symbol_pin_number_mismatch_candidates,
)

RULE_ID = "schematic.embedded_symbol_pin_number_mismatch"
PROJECT = "projects/synthetic/kicad/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/kicad/controller.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/embedded-symbol-pin-number-mismatch"
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
    return embedded_symbol_pin_number_mismatch_candidates(root, config, source_hashes)


def test_unique_definition_pin_number_mismatch_is_localized_and_control_is_quiet(
    tmp_path: Path,
) -> None:
    fault_root, config, fault_hashes = _project(tmp_path / "fault", "fault.kicad_sch")
    control_root, control_config, control_hashes = _project(
        tmp_path / "control", "control.kicad_sch"
    )

    (candidate,) = _scan(fault_root, config, fault_hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":J1")
    assert "review which source representation" in candidate.message
    assert candidate.evidence["source_path"] == (SCHEMATIC,)
    assert candidate.evidence["source_sha256"] == (fault_hashes[SCHEMATIC],)
    assert candidate.evidence["reference"] == ("J1",)
    assert candidate.evidence["library_id"] == ("Connector:USB_A",)
    assert candidate.evidence["unit"] == ("1",)
    assert candidate.evidence["convert"] == ("1",)
    assert candidate.evidence["definition_pin_numbers"] == ("1", "2", "9")
    assert candidate.evidence["placed_pin_numbers"] == ("1", "2", "4")
    assert candidate.evidence["definition_only_pin_numbers"] == ("9",)
    assert candidate.evidence["placed_only_pin_numbers"] == ("4",)
    assert _scan(control_root, control_config, control_hashes) == ()


def test_nonselected_multi_unit_definition_does_not_hide_matching_group(tmp_path: Path) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch")
    source = root / SCHEMATIC
    content = source.read_text(encoding="utf-8")
    needle = '(number "9" (effects (font (size 1.27 1.27)))))))'
    replacement = """(number "9" (effects (font (size 1.27 1.27))))))
      (symbol "USB_A_2_1"
        (pin passive line (at 0 0 0) (length 2.54)
          (name "ALT" (effects (font (size 1.27 1.27))))
          (number "7" (effects (font (size 1.27 1.27)))))
      )
    )"""
    assert content.count(needle) == 1
    source.write_text(content.replace(needle, replacement, 1), encoding="utf-8")
    source_hashes[SCHEMATIC] = digest(source)

    (candidate,) = _scan(root, config, source_hashes)
    assert candidate.evidence["definition_pin_numbers"] == ("1", "2", "9")
    assert candidate.evidence["placed_pin_numbers"] == ("1", "2", "4")


def test_selected_multi_unit_group_is_compared_and_control_is_quiet(tmp_path: Path) -> None:
    fault_root, config, fault_hashes = _project(tmp_path / "fault", "multi-unit-fault.kicad_sch")
    control_root, control_config, control_hashes = _project(
        tmp_path / "control", "multi-unit-control.kicad_sch"
    )

    (candidate,) = _scan(fault_root, config, fault_hashes)

    assert candidate.subject.endswith(":J1")
    assert candidate.evidence["unit"] == ("2",)
    assert candidate.evidence["convert"] == ("1",)
    assert candidate.evidence["definition_pin_numbers"] == ("9",)
    assert candidate.evidence["placed_pin_numbers"] == ("5",)
    assert candidate.evidence["definition_only_pin_numbers"] == ("9",)
    assert candidate.evidence["placed_only_pin_numbers"] == ("5",)
    assert _scan(control_root, control_config, control_hashes) == ()


def test_shared_unit_zero_pin_group_remains_unsupported(tmp_path: Path) -> None:
    root, config, source_hashes = _project(tmp_path, "multi-unit-fault.kicad_sch")
    source = root / SCHEMATIC
    content = source.read_text(encoding="utf-8")
    needle = '(symbol "USB_A_0_1"\n        (rectangle'
    replacement = """(symbol "USB_A_0_1"
        (pin passive line (at 0 0 0) (length 2.54)
          (name "SHARED" (effects (font (size 1.27 1.27))))
          (number "8" (effects (font (size 1.27 1.27)))))
        (rectangle"""
    assert content.count(needle) == 1
    source.write_text(content.replace(needle, replacement, 1), encoding="utf-8")
    source_hashes[SCHEMATIC] = digest(source)

    assert _scan(root, config, source_hashes) == ()


def test_irrelevant_source_edit_preserves_finding_and_refreshes_hash(tmp_path: Path) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch")
    (before,) = _scan(root, config, source_hashes)
    source = root / SCHEMATIC
    source.write_bytes(
        source.read_bytes().replace(
            b"Synthetic USB direct peer reference review",
            b"Synthetic embedded pin-number mismatch review",
        )
    )
    source_hashes[SCHEMATIC] = digest(source)

    first = _scan(root, config, source_hashes)
    assert first == _scan(root, config, source_hashes)
    assert len(first) == 1
    assert first[0].subject == before.subject
    assert first[0].evidence["source_sha256"] == (source_hashes[SCHEMATIC],)
    assert first[0].evidence["source_sha256"] != before.evidence["source_sha256"]


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
