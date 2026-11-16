"""Source-bound schematic integrity catalog reachability fixtures."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_conflicting_placed_footprint import (
    source_bound_conflicting_placed_footprint_candidates,
)
from kicad_tooling.hwrepo.schematic_conflicting_placed_reference import (
    source_bound_conflicting_placed_reference_candidates,
)
from kicad_tooling.hwrepo.schematic_conflicting_placed_value import (
    source_bound_conflicting_placed_value_candidates,
)
from kicad_tooling.hwrepo.schematic_reserved_dnp_property import (
    source_bound_reserved_dnp_property_candidates,
)
from kicad_tooling.hwrepo.schematic_source_integrity import (
    duplicate_embedded_library_symbol_candidates,
    duplicate_schematic_object_uuid_candidates,
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
    duplicate_uuid_relative = (
        "tests/fixtures/design_lint/schematic-duplicate-object-uuid/fault.kicad_sch"
    )
    duplicate_uuid_source = repository / duplicate_uuid_relative
    duplicate_uuid_project = duplicate_uuid_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    duplicate_uuid_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=duplicate_uuid_project,
            kicad_version="10.0.5",
        ),
    )
    duplicate_uuid_candidates = duplicate_schematic_object_uuid_candidates(
        repository,
        duplicate_uuid_config,
        {duplicate_uuid_relative: digest(duplicate_uuid_source)},
    )
    conflicting_value_relative = (
        "tests/fixtures/design_lint/conflicting-placed-value/fault.kicad_sch"
    )
    conflicting_value_source = repository / conflicting_value_relative
    conflicting_value_project = conflicting_value_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    conflicting_value_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=conflicting_value_project,
            kicad_version="10.0.8",
        ),
    )
    conflicting_value_candidates = source_bound_conflicting_placed_value_candidates(
        repository,
        conflicting_value_config,
        {conflicting_value_relative: digest(conflicting_value_source)},
    )
    conflicting_footprint_relative = (
        "tests/fixtures/design_lint/conflicting-placed-footprint/fault.kicad_sch"
    )
    conflicting_footprint_source = repository / conflicting_footprint_relative
    conflicting_footprint_project = (
        conflicting_footprint_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    )
    conflicting_footprint_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=conflicting_footprint_project,
            kicad_version="10.0.8",
        ),
    )
    conflicting_footprint_candidates = source_bound_conflicting_placed_footprint_candidates(
        repository,
        conflicting_footprint_config,
        {conflicting_footprint_relative: digest(conflicting_footprint_source)},
    )
    reserved_dnp_relative = (
        "tests/fixtures/design_lint/reserved-dnp-property/fault-custom-only-yes.kicad_sch"
    )
    reserved_dnp_source = repository / reserved_dnp_relative
    reserved_dnp_project = reserved_dnp_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    reserved_dnp_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=reserved_dnp_project,
            kicad_version="10.0.8",
        ),
    )
    reserved_dnp_candidates = source_bound_reserved_dnp_property_candidates(
        repository,
        reserved_dnp_config,
        {reserved_dnp_relative: digest(reserved_dnp_source)},
    )
    conflicting_reference_relative = (
        "tests/fixtures/design_lint/conflicting-placed-reference/fault.kicad_sch"
    )
    conflicting_reference_source = repository / conflicting_reference_relative
    conflicting_reference_project = (
        conflicting_reference_relative.removesuffix(".kicad_sch") + ".kicad_pro"
    )
    conflicting_reference_config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project=conflicting_reference_project,
            kicad_version="10.0.8",
        ),
    )
    conflicting_reference_candidates = source_bound_conflicting_placed_reference_candidates(
        repository,
        conflicting_reference_config,
        {conflicting_reference_relative: digest(conflicting_reference_source)},
    )
    return frozenset(
        item.rule_id
        for item in (
            *candidates,
            *duplicate_candidates,
            *pin_mismatch_candidates,
            *duplicate_uuid_candidates,
            *conflicting_value_candidates,
            *conflicting_footprint_candidates,
            *reserved_dnp_candidates,
            *conflicting_reference_candidates,
        )
    )
