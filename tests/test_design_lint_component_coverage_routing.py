"""Typed request boundary and source identity for component-map coverage."""

from __future__ import annotations

from dataclasses import fields
from inspect import signature
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_return_distribution_models import (
    ConnectorReturnDistributionCoverageReport,
)
from kicad_tooling.hwrepo.crystal_network_models import (
    CrystalNetworkCoverageEntry,
    CrystalNetworkCoverageReport,
)
from kicad_tooling.hwrepo.design_lint_component_coverage import (
    ComponentMapCoverageInputs,
    ComponentMapCoverageRequest,
    resolve_component_map_coverage,
)
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate
from kicad_tooling.hwrepo.i2c_address_models import I2cAddressCoverageReport
from kicad_tooling.hwrepo.models import DesignLintPolicy, NetlistContract
from kicad_tooling.hwrepo.rc_filter_models import RcFilterCoverageEntry, RcFilterCoverageReport
from kicad_tooling.hwrepo.regulator_feedback_models import (
    RegulatorFeedbackCoverageEntry,
    RegulatorFeedbackCoverageReport,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.architecture]

_CURRENT_NETLIST = "a" * 64
_STALE_NETLIST = "b" * 64
_CURRENT_CATALOG = "c" * 64
_STALE_CATALOG = "d" * 64


def _request(inputs: ComponentMapCoverageInputs | None = None) -> ComponentMapCoverageRequest:
    return ComponentMapCoverageRequest(
        policy=DesignLintPolicy(),
        observed=NetlistContract(components={}, nets={}),
        netlist_sha256=_CURRENT_NETLIST,
        inputs=inputs if inputs is not None else ComponentMapCoverageInputs(),
    )


def test_no_authored_or_supplied_component_map_is_explicitly_not_requested() -> None:
    coverage = resolve_component_map_coverage(_request())

    assert {
        coverage.i2c_address.status,
        coverage.crystal_network.status,
        coverage.regulator_feedback.status,
        coverage.rc_filter.status,
        coverage.connector_return_distribution.status,
    } == {"NOT_REQUESTED"}


def test_legacy_evaluator_coverage_arguments_enter_through_the_typed_group() -> None:
    request_fields = {field.name for field in fields(DesignLintEvaluationRequest)}
    legacy_coverage_fields = {
        "connector_coverage",
        "i2c_address_coverage",
        "crystal_network_coverage",
        "regulator_feedback_coverage",
        "rc_filter_coverage",
        "connector_return_distribution_coverage",
    }

    assert "component_map_coverage" in request_fields
    assert request_fields.isdisjoint(legacy_coverage_fields)
    assert (
        get_type_hints(DesignLintEvaluationRequest)["component_map_coverage"]
        is ComponentMapCoverageInputs
    )
    assert legacy_coverage_fields <= set(signature(evaluate).parameters)


def test_stale_netlist_coverage_is_blocked_without_rebinding_its_source() -> None:
    crystal = CrystalNetworkCoverageReport(
        status="COMPLETE",
        netlist_sha256=_STALE_NETLIST,
        entries=(
            CrystalNetworkCoverageEntry(
                oscillator_reference="U1",
                resonator_reference="Y1",
                load_capacitor_references=("C1", "C2"),
                status="OUT_OF_RANGE",
                target_minimum_load_pf=10,
                target_maximum_load_pf=12,
                minimum_stray_capacitance_pf=1,
                maximum_stray_capacitance_pf=3,
                basis="Synthetic source-binding regression",
            ),
        ),
    )
    regulator = RegulatorFeedbackCoverageReport(
        status="COMPLETE",
        netlist_sha256=_STALE_NETLIST,
        entries=(
            RegulatorFeedbackCoverageEntry(
                id="main-rail",
                regulator_reference="U1",
                status="OUT_OF_RANGE",
                output_net="VOUT",
                reference_net="GND",
                feedback_reference_minimum_v=0.79,
                feedback_reference_maximum_v=0.81,
                target_output_minimum_v=5,
                target_output_maximum_v=5.2,
                basis="Synthetic source-binding regression",
            ),
        ),
    )
    rc_filter = RcFilterCoverageReport(
        status="COMPLETE",
        netlist_sha256=_STALE_NETLIST,
        entries=(
            RcFilterCoverageEntry(
                id="input-filter",
                resistor_reference="R1",
                capacitor_reference="C1",
                status="OUT_OF_RANGE",
                input_net="VIN",
                filtered_net="VOUT",
                reference_net="GND",
                target_minimum_corner_hz=1,
                target_maximum_corner_hz=2,
                nominal_resistance_range_ohms=(1, 2),
                nominal_capacitance_range_pf=(1, 2),
                basis="Synthetic source-binding regression",
            ),
        ),
    )
    coverage = resolve_component_map_coverage(
        _request(
            ComponentMapCoverageInputs(
                i2c_address_coverage=I2cAddressCoverageReport(
                    status="COMPLETE", netlist_sha256=_STALE_NETLIST
                ),
                crystal_network_coverage=crystal,
                regulator_feedback_coverage=regulator,
                rc_filter_coverage=rc_filter,
                connector_return_distribution_coverage=ConnectorReturnDistributionCoverageReport(
                    status="COMPLETE",
                    netlist_sha256=_STALE_NETLIST,
                    interface_catalog_sha256=_STALE_CATALOG,
                ),
            )
        )
    )

    assert coverage.i2c_address.status == "BLOCKED"
    assert coverage.i2c_address.netlist_sha256 == _STALE_NETLIST
    for report in (
        coverage.crystal_network,
        coverage.regulator_feedback,
        coverage.rc_filter,
        coverage.connector_return_distribution,
    ):
        assert report.status == "BLOCKED"
        assert report.netlist_sha256 == _STALE_NETLIST
        assert report.entries == ()


def test_stale_interface_catalog_is_blocked_without_rebinding_its_identity() -> None:
    coverage = resolve_component_map_coverage(
        _request(
            ComponentMapCoverageInputs(
                connector_coverage=ConnectorCoverageReport(
                    status="COMPLETE",
                    scope="Synthetic interface scope",
                    inventory_review_basis="Synthetic independent review",
                    interface_catalog_sha256=_CURRENT_CATALOG,
                ),
                connector_return_distribution_coverage=ConnectorReturnDistributionCoverageReport(
                    status="COMPLETE",
                    netlist_sha256=_CURRENT_NETLIST,
                    interface_catalog_sha256=_STALE_CATALOG,
                ),
            ),
        )
    )

    blocked = coverage.connector_return_distribution
    assert blocked.status == "BLOCKED"
    assert blocked.netlist_sha256 == _CURRENT_NETLIST
    assert blocked.interface_catalog_sha256 == _STALE_CATALOG
    assert blocked.entries == ()
