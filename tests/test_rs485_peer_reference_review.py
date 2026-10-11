"""Deterministic project-mapped RS-485 peer reference regressions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_rs485_candidates import rs485_peer_reference_candidates
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.rs485_models import Rs485Analysis
from kicad_tooling.hwrepo.rs485_peer_reference_scan import scan_rs485_peer_references
from kicad_tooling.hwrepo.rs485_peer_reference_types import Rs485PeerReferenceContext
from tests.design_lint_fixtures import coach
from tests.rs485_peer_reference_support import rs485_peer_reference_fixture

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.rs485_peer_reference_review"
NATIVE_FIXTURES = Path(__file__).parent / "fixtures/design_lint/rs485-peer-reference-native"


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def test_shared_mapped_pair_with_split_references_emits_exact_review() -> None:
    _, context, source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}
    )
    scan = scan_rs485_peer_references(context, source)
    report = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(),
        rs485_peer_reference_context=context,
    )
    findings = _findings(report)

    assert scan.recognized_endpoint_count == 3
    assert len(scan.pairs) == 1
    assert scan.pairs[0].disposition == "SPLIT_REFERENCE_REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].evidence == {
        "bus": ("field-bus",),
        "pair": ("pair-a",),
        "line_1": ("RS485_A",),
        "line_2": ("RS485_B",),
        "participants": ("U1", "U2", "U3"),
        "reference_assignments": (
            "U1: U1.5 on GND_A",
            "U2: U2.5 on GND_B",
            "U3: U3.5 on GND_A",
        ),
        "reference_nets": ("GND_A", "GND_B"),
    }
    assert "does not require a common return" in findings[0].message
    coverage = report.rs485_peer_reference_coverage
    assert coverage is not None
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.authored_map_path == "contracts/electrical.json"
    assert coverage.authored_map_source_sha256 == "a" * 64
    assert coverage.authored_rs485_map_sha256 is not None
    assert coverage.candidate_group_count == 1


def test_common_references_and_unshared_native_pairs_are_controls() -> None:
    _, context, common_source = rs485_peer_reference_fixture()
    common = evaluate(
        "synthetic-rs485-reference",
        coach(common_source),
        DesignLintPolicy(),
        rs485_peer_reference_context=context,
    )
    _, split_context, source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}
    )
    split_pins = {"U2.1", "U2.2", "U3.1", "U3.2"}
    mutated_nets = {
        net: tuple(pin for pin in pins if pin not in split_pins)
        for net, pins in source.nets.items()
    }
    for reference in ("U2", "U3"):
        for suffix, number in (("A", "1"), ("B", "2")):
            net = f"OTHER_{reference}_{suffix}"
            mutated_nets[net] = (f"{reference}.{number}",)
    unshared = source.model_copy(update={"nets": mutated_nets})
    unshared_report = evaluate(
        "synthetic-rs485-reference",
        coach(unshared),
        DesignLintPolicy(),
        rs485_peer_reference_context=split_context,
    )

    assert not _findings(common)
    assert common.rs485_peer_reference_coverage.entries[0].disposition == "COMMON_REFERENCE"
    assert not _findings(unshared_report)
    assert unshared_report.rs485_peer_reference_coverage.status == "NO_SHARED_ENDPOINTS"


def test_partial_split_survives_missing_reference_assignment() -> None:
    _, context, source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_C"},
        incomplete_references=("U3",),
    )
    report = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(),
        rs485_peer_reference_context=context,
    )

    assert len(_findings(report)) == 1
    coverage = report.rs485_peer_reference_coverage
    assert coverage is not None
    assert coverage.status == "INCOMPLETE"
    assert coverage.entries[0].disposition == "PARTIAL_SPLIT_REFERENCE_REVIEW"
    assert coverage.entries[0].incomplete_references == ("U3",)


def test_absent_map_dnp_and_no_reference_map_remain_visible_without_guessing() -> None:
    _, _, source = rs485_peer_reference_fixture()
    absent = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(),
        rs485_peer_reference_context=Rs485PeerReferenceContext(state="not_configured"),
    )
    _, dnp_context, dnp_source = rs485_peer_reference_fixture(dnp=("U3",))
    dnp = evaluate(
        "synthetic-rs485-reference",
        coach(dnp_source),
        DesignLintPolicy(),
        rs485_peer_reference_context=dnp_context,
    )
    analysis, context, mapped_source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_C"}
    )
    endpoints = tuple(
        endpoint.model_copy(
            update={"pins": tuple(pin for pin in endpoint.pins if pin.role != "reference")}
        )
        if endpoint.reference == "U3"
        else endpoint
        for endpoint in analysis.buses[0].endpoints
    )
    bus = analysis.buses[0].model_copy(update={"endpoints": endpoints})
    no_reference_map = analysis.model_copy(update={"buses": (bus,)})
    no_reference_context = replace(context, analysis=no_reference_map)
    no_reference = evaluate(
        "synthetic-rs485-reference",
        coach(mapped_source),
        DesignLintPolicy(),
        rs485_peer_reference_context=no_reference_context,
    )

    assert not _findings(absent)
    assert absent.rs485_peer_reference_coverage.status == "NOT_CONFIGURED"
    assert not _findings(dnp)
    assert dnp.rs485_peer_reference_coverage.recognized_endpoint_count == 2
    assert len(_findings(no_reference)) == 1
    assert no_reference.rs485_peer_reference_coverage.entries[0].incomplete_references == ("U3",)


def test_exact_component_peer_duplicate_suppression_and_review_policy() -> None:
    _, context, source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}
    )
    scan = scan_rs485_peer_references(context, source)
    exact_assignments = {
        pin.pin: (pin.net,)
        for endpoint in scan.reviews[0].endpoints
        for pin in endpoint.reference_pins
        if pin.net is not None
    }
    covering = Candidate(
        rule_id="component.peer_power_pin_assignment_divergence",
        subject="synthetic component peer coverage",
        message="synthetic complete coverage",
        evidence={"peer_role": ("ground/return",), **exact_assignments},
    )
    partial = Candidate(
        rule_id="component.peer_power_pin_assignment_divergence",
        subject="synthetic partial coverage",
        message="synthetic partial coverage",
        evidence={
            "peer_role": ("ground/return",),
            next(iter(exact_assignments)): next(iter(exact_assignments.values())),
        },
    )
    baseline = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(),
        rs485_peer_reference_context=context,
    )
    finding = _findings(baseline)[0]
    blocked = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic blocking policy regression",
                ),
            )
        ),
        rs485_peer_reference_context=context,
    )
    disabled = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic isolated-link control",
                ),
            )
        ),
        rs485_peer_reference_context=context,
    )
    ignored = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic map explicitly documents intentional isolation",
                ),
            )
        ),
        rs485_peer_reference_context=context,
    )

    assert not rs485_peer_reference_candidates(scan, (covering,))
    assert len(rs485_peer_reference_candidates(scan, (partial,))) == 1
    assert blocked.status == "FAIL"
    assert _findings(blocked)[0].mode == "block"
    assert disabled.rs485_peer_reference_coverage.mode == "off"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


def test_source_and_mapping_order_preserve_the_candidate_fingerprint() -> None:
    _, context, source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}
    )
    baseline = evaluate(
        "synthetic-rs485-reference",
        coach(source),
        DesignLintPolicy(),
        rs485_peer_reference_context=context,
    )
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
        }
    )
    reordered_report = evaluate(
        "synthetic-rs485-reference",
        coach(reordered),
        DesignLintPolicy(),
        rs485_peer_reference_context=context,
    )

    assert _findings(reordered_report)[0].fingerprint == _findings(baseline)[0].fingerprint
    assert _findings(reordered_report)[0].evidence == _findings(baseline)[0].evidence


def test_native_fault_and_control_maps_differ_only_at_the_j3_reference() -> None:
    control = Rs485Analysis.model_validate_json(
        (NATIVE_FIXTURES / "reference-control.json").read_text(encoding="utf-8")
    )
    fault = Rs485Analysis.model_validate_json(
        (NATIVE_FIXTURES / "reference-fault.json").read_text(encoding="utf-8")
    )
    control_pins = {
        pin.pin: pin.net for endpoint in control.buses[0].endpoints for pin in endpoint.pins
    }
    fault_pins = {
        pin.pin: pin.net for endpoint in fault.buses[0].endpoints for pin in endpoint.pins
    }
    differences = {
        pin: (control_pins[pin], fault_pins[pin])
        for pin in control_pins.keys() | fault_pins.keys()
        if control_pins.get(pin) != fault_pins.get(pin)
    }

    assert differences == {"J3.3": ("GND_A", "GND_B")}
    assert control.buses[0].pairs[0].line_1_net == fault.buses[0].pairs[0].line_1_net
    assert control.buses[0].pairs[0].line_2_net == fault.buses[0].pairs[0].line_2_net
