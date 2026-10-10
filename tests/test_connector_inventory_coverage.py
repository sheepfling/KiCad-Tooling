"""Focused connector coverage checks for a single review theme."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.connector_coverage import evaluate
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ContractCoachReport,
    DesignLintPolicy,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    interface_record,
    inventory_review,
    observed_connector,
)

pytestmark = [
    pytest.mark.connector_lint,
    pytest.mark.design_lint,
]


def test_standard_connector_symbol_identity_finds_nonstandard_reference_candidates() -> None:
    observed = NetlistContract(
        components={},
        nets={},
        component_symbols={
            "EXT1": "Connector:USB_C_Receptacle_USB2.0_16P",
            "HDR1": "Connector_Generic_MountingPin:Conn_01x02_MountingPin",
            "J1": "Device:R",
            "U7": "Connector_Generic:Conn_01x02",
            "U8": "Connector:TestPoint_Alt",
            "U9": "Device:R",
        },
    )

    coverage = evaluate(observed, (), ())

    assert (tuple(item.reference for item in coverage.entries)) == (("EXT1", "HDR1", "J1", "U7"))
    assert (coverage.status) == ("UNDECLARED")
    assert ("U8") not in ({item.reference for item in coverage.entries})
    assert ("U9") not in ({item.reference for item in coverage.entries})


def test_standard_test_point_library_control_does_not_create_connector_coverage() -> None:
    observed = NetlistContract(
        components={},
        nets={},
        component_symbols={
            "U1": "Connector:TestPoint_2Pole",
            "TP1": "TestPoint:TestPoint_Pad_1.5x1.5mm",
            "R1": "Device:R",
        },
    )

    coverage = evaluate(observed, (), (), inventory_review=inventory_review())

    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries) == (())


def test_unreviewed_candidate_is_a_coverage_gap_and_keeps_lint_at_review() -> None:
    coverage = evaluate(observed_connector(), (), ())
    assert (coverage.status) == ("UNDECLARED")
    assert (coverage.entries[0].reference) == ("J1")
    assert (coverage.entries[0].status) == ("UNDECLARED")
    report = evaluate_design_lint(
        "synthetic",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic",
            observed=observed_connector(),
        ),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    assert (report.status) == ("REVIEW")
    assert ("Connector coverage: UNDECLARED") in (text_report(report))
    assert ("UNDECLARED connector J1") in (text_report(report))


def test_complete_interface_review_accounts_for_every_catalog_and_symbol_pin() -> None:
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic interface pinout reviewed",
        interface_id="debug-port",
        pin_map={"1": "1", "2": "2"},
        unlisted_pin_reasons={"3": "Synthetic shield pin reviewed separately"},
    )
    coverage = evaluate(
        observed_connector(),
        ("debug-port",),
        (review,),
        interfaces={"debug-port": interface_record()},
        inventory_review=inventory_review(),
    )
    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries[0].status) == ("COVERED")
    assert (coverage.unbound_interface_ids) == (())
    assert (coverage.inventory_review_basis) == (
        "Synthetic review covered the complete schematic symbol inventory"
    )
    assert (coverage.entries[0].interface_pin_map) == ({"1": "1", "2": "2"})
    assert (coverage.entries[0].mapped_pins[0].interface_signal) == ("TX")
    assert (coverage.entries[0].mapped_pins[0].nets) == (("TX",))
    assert (coverage.entries[0].unlisted_pin_reasons) == (
        {"3": "Synthetic shield pin reviewed separately"}
    )


def test_reviewed_custom_symbol_discovers_exact_symbol_peers_for_coverage() -> None:
    observed = NetlistContract(
        components={},
        nets={"RETURN": ("A1.1", "A2.1"), "OTHER": ("A3.1",)},
        component_symbols={
            "A1": "Synthetic:CustomPort",
            "A2": "Synthetic:CustomPort",
            "A3": "Synthetic:DifferentPort",
        },
        component_pin_numbers={
            "A1": ("1",),
            "A2": ("1",),
            "A3": ("1",),
        },
        pin_functions={"A1.1": "Pin_1", "A2.1": "Pin_1", "A3.1": "Pin_1"},
    )
    interface = InterfaceRecord(
        id="custom-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="RETURN",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    review = ConnectorInterfaceReview(
        reference="A1",
        disposition="interface",
        basis="Synthetic custom connector pinout was reviewed",
        interface_id="custom-port",
        pin_map={"1": "1"},
    )

    coverage = evaluate(
        observed,
        ("custom-port",),
        (review,),
        interfaces={"custom-port": interface},
        inventory_review=inventory_review(),
    )

    assert ({item.reference: item.status for item in coverage.entries}) == (
        {"A1": "COVERED", "A2": "UNDECLARED"}
    )
    assert (coverage.status) == ("UNDECLARED")

    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )
    reordered_coverage = evaluate(
        reordered,
        ("custom-port",),
        (review,),
        interfaces={"custom-port": interface},
        inventory_review=inventory_review(),
    )
    assert (reordered_coverage) == (coverage)

    not_applicable = ConnectorInterfaceReview(
        reference="A2",
        disposition="not_applicable",
        basis="Synthetic instance is a local fixture connector",
    )
    dispositioned = evaluate(
        observed,
        ("custom-port",),
        (review, not_applicable),
        interfaces={"custom-port": interface},
        inventory_review=inventory_review(),
    )
    assert (dispositioned.status) == ("COMPLETE")
    assert ({item.reference: item.status for item in dispositioned.entries}) == (
        {"A1": "COVERED", "A2": "NOT_APPLICABLE"}
    )


def test_missing_and_unknown_catalog_or_symbol_pins_are_named() -> None:
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic partial interface map",
        interface_id="debug-port",
        pin_map={"1": "1", "stale": "9"},
    )
    coverage = evaluate(
        observed_connector(),
        ("debug-port",),
        (review,),
        interfaces={"debug-port": interface_record()},
    )
    entry = coverage.entries[0]
    assert (coverage.status) == ("INCOMPLETE")
    assert (entry.status) == ("INCOMPLETE")
    assert (entry.interface_pins_unmapped) == (("2",))
    assert (entry.interface_pins_unknown) == (("stale",))
    assert (entry.component_pins_unaccounted) == (("2", "3"))
    assert (entry.component_pins_unknown) == (("9",))


def test_explicit_not_applicable_decision_covers_a_candidate_without_joining_nets() -> None:
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="not_applicable",
        basis="Synthetic connector is a local service jumper, not an external interface",
    )
    coverage = evaluate(observed_connector(), (), (review,), inventory_review=inventory_review())
    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries[0].status) == ("NOT_APPLICABLE")


def test_reviewed_connector_rows_still_need_complete_inventory_scope() -> None:
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="not_applicable",
        basis="Synthetic connector is a local service jumper",
    )
    coverage = evaluate(observed_connector(), (), (review,))
    assert (coverage.status) == ("SCOPE_UNREVIEWED")


def test_explicit_review_can_cover_a_reference_outside_candidate_prefixes() -> None:
    review = ConnectorInterfaceReview(
        reference="EXT1",
        disposition="not_applicable",
        basis="Synthetic external-style reference was reviewed directly",
    )
    observed = NetlistContract(
        components={},
        nets={},
        component_symbols={"EXT1": "Synthetic:DebugConnector"},
        component_pin_numbers={"EXT1": ("1",)},
    )
    coverage = evaluate(observed, (), (review,), inventory_review=inventory_review())
    assert (coverage.status) == ("COMPLETE")
    assert (coverage.entries[0].status) == ("NOT_APPLICABLE")


def test_stale_review_and_missing_interface_record_are_incomplete() -> None:
    stale = ConnectorInterfaceReview(
        reference="J2",
        disposition="not_applicable",
        basis="Synthetic old reference",
    )
    stale_coverage = evaluate(observed_connector(), (), (stale,))
    assert (stale_coverage.status) == ("INCOMPLETE")
    stale_entry = next(entry for entry in stale_coverage.entries if entry.reference == "J2")
    assert (stale_entry.status) == ("STALE")

    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic missing catalog record",
        interface_id="missing-interface",
        pin_map={"1": "1"},
    )
    missing = evaluate(
        observed_connector(),
        ("missing-interface",),
        (review,),
        interfaces={},
    )
    assert (missing.status) == ("INCOMPLETE")
    assert ("missing-interface") in (missing.entries[0].issues[0])


def test_no_candidates_without_declarations_is_explicitly_unassessed() -> None:
    observed = observed_connector(candidate=False)
    coverage = evaluate(observed, (), ())
    assert (coverage.status) == ("UNASSESSED")
    assert ("does not prove") in (coverage.scope)
    report = evaluate_design_lint(
        "synthetic-no-interfaces",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-no-interfaces",
            observed=observed,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    assert (report.status) == ("REVIEW")
    assert ("connector_inventory_review") in (" ".join(report.next_actions))


def test_explicit_inventory_review_can_confirm_no_external_connectors() -> None:
    observed = NetlistContract(components={}, nets={})
    coverage = evaluate(observed, (), (), inventory_review=inventory_review())
    assert (coverage.status) == ("COMPLETE")
    report = evaluate_design_lint(
        "synthetic-no-interfaces",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-no-interfaces",
            observed=observed,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    assert (report.status) == ("PASS")
    assert (
        "Inventory review basis: Synthetic review covered the complete schematic symbol inventory"
    ) in (text_report(report))


def test_complete_report_cannot_omit_inventory_review_basis() -> None:
    with pytest.raises(ValidationError, match="inventory review basis"):
        ConnectorCoverageReport(status="COMPLETE", scope="Synthetic connector inventory")


def test_interface_record_rejects_duplicate_pin_numbers() -> None:
    valid = interface_record()
    with pytest.raises(ValueError, match="pin numbers must be unique"):
        InterfaceRecord(
            id="duplicate",
            revision="synthetic-1",
            pins=(valid.pins[0], valid.pins[0]),
        )
