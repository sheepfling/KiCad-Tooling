"""Mapped-topology run records require authored maps for emitted findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_mapped_topology_coverage import (
    mapped_topology_coverage_runs,
)
from kicad_tooling.hwrepo.design_lint_mapped_topology_results import (
    MappedTopologyFindingCounts,
)
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.usb_data_path_models import usb_data_path_map_sha256
from tests.usb_data_path_support import usb_data_map

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.rule_gate_integrity,
]

_RULE_MODES = {
    "bus.usb_data_path_mismatch": "review",
    "power.mapped_series_path_mismatch": "review",
    "power.mapped_sequence_dependency_mismatch": "review",
    "oscillator.output_load_path_mismatch": "review",
}


def test_unconfigured_mapped_rule_cannot_report_findings() -> None:
    with pytest.raises(ValueError, match="require a project-authored map"):
        mapped_topology_coverage_runs(
            DesignLintPolicy(),
            _RULE_MODES,
            MappedTopologyFindingCounts(usb_data_path_mismatch=1),
            "a" * 64,
        )


def test_unconfigured_mapped_rules_retain_zero_finding_counts() -> None:
    runs = mapped_topology_coverage_runs(
        DesignLintPolicy(),
        _RULE_MODES,
        MappedTopologyFindingCounts(),
        "a" * 64,
    )

    assert {run.status for run in runs} == {"NOT_CONFIGURED"}
    assert all(run.finding_count == 0 for run in runs)


def test_usb_map_coverage_uses_canonical_map_digest() -> None:
    usb_map = usb_data_map()
    policy = DesignLintPolicy(usb_data_path_map=usb_map)
    runs = mapped_topology_coverage_runs(
        policy,
        _RULE_MODES,
        MappedTopologyFindingCounts(),
        "a" * 64,
    )

    usb_run = next(run for run in runs if run.rule_id == "bus.usb_data_path_mismatch")

    assert usb_run.map_sha256 == usb_data_path_map_sha256(usb_map)
