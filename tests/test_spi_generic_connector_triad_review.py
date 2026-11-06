"""Review generic connector pins spanning an exact native SPI role triad."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.models import ContractCoachReport
from tests.design_lint_fixtures.spi_generic_connector_triad import (
    generic_spi_connector_triad_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_generic_connector_triad_review"


def _report(
    observed=None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
):
    netlist = observed or generic_spi_connector_triad_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-spi-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage,
    )


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_spi_pin_map() -> ConnectorCoverageReport:
    signals = (
        ("1", "SCK", "SPI_SCK"),
        ("2", "MOSI", "SPI_MOSI"),
        ("3", "MISO", "SPI_MISO"),
        ("4", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic SPI connector inventory",
        project_interfaces=("synthetic-spi",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-spi",
                basis="Synthetic approved SPI pin map",
                interface_pin_map={signal: number for number, signal, _ in signals},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function=f"Pin_{number}",
                        nets=(net,),
                    )
                    for number, signal, net in signals
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_spi_triad_emit_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: generic pins match SPI clock and both data roles"
    assert finding.evidence["clock_net"] == ("SPI_SCK",)
    assert finding.evidence["clock_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["controller-to-peripheral data_net"] == ("SPI_MOSI",)
    assert finding.evidence["controller-to-peripheral data_generic_connector_pins"] == (
        "J1.2",
    )
    assert finding.evidence["peripheral-to-controller data_net"] == ("SPI_MISO",)
    assert finding.evidence["peripheral-to-controller data_generic_connector_pins"] == (
        "J1.3",
    )
    assert finding.evidence["SPI_endpoint_triads"] == (
        "U1:default:clock=U1.1/SPI_SCK;data_input=U1.2/SPI_MOSI;data_output=U1.3/SPI_MISO",
    )
    assert "does not infer connector or device identity" in finding.message
    assert "power requirements" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_connector_roles_and_current_pin_map_suppress_review() -> None:
    named = generic_spi_connector_triad_netlist(
        connector_functions=("SCK", "MOSI", "MISO", "GND")
    )
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(connector_coverage=_source_matched_spi_pin_map()).findings
    )
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=stale_map).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_partial_ambiguous_dnp_and_incomplete_cases_are_quiet() -> None:
    observed = generic_spi_connector_triad_netlist()
    partial = generic_spi_connector_triad_netlist(include_data_output_contact=False)
    ambiguous_connector = observed.model_copy(
        update={"nets": {**observed.nets, "OTHER": ("J1.1",)}}
    )
    dnp_connector = observed.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = observed.model_copy(update={"dnp_components": ("U1",)})
    incomplete_connector = observed.model_copy(
        update={"component_pin_numbers": {**observed.component_pin_numbers, "J1": ("1", "2", "3")}}
    )
    missing_endpoint_metadata = observed.model_copy(
        update={"pin_electrical_types": {key: value for key, value in observed.pin_electrical_types.items() if key != "U1.3"}}
    )
    duplicate_clock = observed.model_copy(
        update={"pin_functions": {**observed.pin_functions, "U1.5": "SCK"}}
    )

    for case in (
        partial,
        ambiguous_connector,
        dnp_connector,
        dnp_endpoint,
        incomplete_connector,
        missing_endpoint_metadata,
        duplicate_clock,
    ):
        assert not any(item.rule_id == RULE_ID for item in _report(case).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_roles_and_not_applicable_disposition_are_quiet() -> None:
    observed = generic_spi_connector_triad_netlist()
    same_net = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "SPI_MOSI": ("J1.2", "U1.1", "U1.2"),
                "SPI_SCK": (),
            }
        }
    )
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Synthetic connector inventory review",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(same_net).findings)
    assert not any(
        item.rule_id == RULE_ID for item in _report(connector_coverage=not_applicable).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    finding = _finding(_report())
    blocked = _report(
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Review connector SPI pinout before release",
                ),
            )
        )
    )
    ignored = _report(
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic interface pinout is reviewed elsewhere",
                ),
            )
        )
    )

    assert blocked.status == "FAIL"
    assert _finding(blocked).mode == "block"
    assert _finding(ignored).disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_spi_connector_triad_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    original = _finding(_report(observed))
    permuted = _finding(_report(reordered))
    assert (original.subject, original.evidence) == (permuted.subject, permuted.evidence)
