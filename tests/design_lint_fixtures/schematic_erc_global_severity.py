"""Catalog-reachability probes for global schematic ERC severity review."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_catalog_coverage import (
    source_bound_schematic_erc_catalog_coverage_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_global_severity_review import (
    source_bound_schematic_erc_ignored_rule_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_unknown_rule_key_review import (
    source_bound_schematic_erc_unknown_rule_key_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_warning_downgrade import (
    source_bound_schematic_erc_warning_downgrade_candidates,
)


def schematic_erc_global_severity_rule_ids() -> frozenset[str]:
    """Reach active global-severity rules from source-bound synthetic fixtures."""
    repository = Path(__file__).resolve().parents[2]
    config = cast(
        ProjectConfig,
        SimpleNamespace(
            kind=ProjectKind.PCB,
            project="tests/fixtures/design_lint/schematic-erc-global-severity/fault.kicad_pro",
            kicad_version="10.0.5",
        ),
    )
    ignore_relative = str(config.project)
    ignore_settings = repository / ignore_relative
    ignored = source_bound_schematic_erc_ignored_rule_candidates(
        repository,
        config,
        {ignore_relative: digest(ignore_settings)},
    )
    warning_relative = "tests/fixtures/design_lint/schematic-erc-warning-downgrade/fault.kicad_pro"
    warning_settings = repository / warning_relative
    warning_config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=warning_relative, kicad_version="10.0.5"),
    )
    downgraded = source_bound_schematic_erc_warning_downgrade_candidates(
        repository,
        warning_config,
        {warning_relative: digest(warning_settings)},
    )
    unknown_relative = "tests/fixtures/design_lint/schematic-erc-global-severity/unknown.kicad_pro"
    unknown_settings = repository / unknown_relative
    unknown_config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=unknown_relative, kicad_version="10.0.5"),
    )
    unknown = source_bound_schematic_erc_unknown_rule_key_candidates(
        repository,
        unknown_config,
        {unknown_relative: digest(unknown_settings)},
    )
    coverage_config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=unknown_relative, kicad_version="10.0.3"),
    )
    coverage = source_bound_schematic_erc_catalog_coverage_candidates(
        repository,
        coverage_config,
        {unknown_relative: digest(unknown_settings)},
    )
    return frozenset(
        candidate.rule_id for candidate in (*ignored, *downgraded, *unknown, *coverage)
    )
