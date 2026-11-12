"""Source-bound schematic integrity catalog reachability fixtures."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_source_integrity import (
    duplicate_embedded_library_symbol_candidates,
    embedded_symbol_pin_number_mismatch_candidates,
    missing_embedded_library_symbol_candidates,
)


def schematic_source_integrity_rule_ids() -> frozenset[str]:
    """Reach schematic source-integrity rules from stored tooling fixtures."""
    repository = Path(__file__).resolve().parents[2]
    relative = "tests/fixtures/design_lint/missing-embedded-symbol-definition/fault.kicad_sch"
    source = repository / relative
    project = relative.removesuffix(".kicad_sch") + ".kicad_pro"
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=project,
            kicad_version="10.0.5",
        ),
    )
    candidates = missing_embedded_library_symbol_candidates(
        repository,
        config,
        {relative: digest(source)},
    )
    duplicate_relative = (
        "tests/fixtures/design_lint/duplicate-embedded-symbol-definition/fault.kicad_sch"
    )
    duplicate_source = repository / duplicate_relative
    duplicate_project = duplicate_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    duplicate_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=duplicate_project,
            kicad_version="10.0.5",
        ),
    )
    duplicate_candidates = duplicate_embedded_library_symbol_candidates(
        repository,
        duplicate_config,
        {duplicate_relative: digest(duplicate_source)},
    )
    pin_mismatch_relative = (
        "tests/fixtures/design_lint/embedded-symbol-pin-number-mismatch/fault.kicad_sch"
    )
    pin_mismatch_source = repository / pin_mismatch_relative
    pin_mismatch_project = pin_mismatch_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    pin_mismatch_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=pin_mismatch_project,
            kicad_version="10.0.5",
        ),
    )
    pin_mismatch_candidates = embedded_symbol_pin_number_mismatch_candidates(
        repository,
        pin_mismatch_config,
        {pin_mismatch_relative: digest(pin_mismatch_source)},
    )
    return frozenset(
        item.rule_id for item in (*candidates, *duplicate_candidates, *pin_mismatch_candidates)
    )
