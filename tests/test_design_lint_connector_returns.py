"""Focused synthetic regressions for the connector returns lint theme."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, NetlistContract
from tests.design_lint_fixtures import (
    coach,
    cross_symbol_power,
    cross_symbol_returns,
    multiconductor_connector,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
]


def _lint(netlist: NetlistContract) -> DesignLintReport:
    return evaluate("synthetic-ports", coach(netlist), DesignLintPolicy())


def test_multiconductor_connector_without_connected_return_needs_review() -> None:
    report = _lint(multiconductor_connector())

    assert report.status == "REVIEW"
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule_id == "connector.unconnected_return_pin"
    assert finding.subject == "J1.4: GND"
    assert finding.evidence == {"J1.4": ()}
    assert "no net assignment" in finding.message


def test_connector_without_identified_return_needs_review() -> None:
    report = _lint(multiconductor_connector(return_named=False))

    assert len(report.findings) == 1
    assert report.findings[0].rule_id == "connector.no_connected_return"
    assert "3 connected non-shield pins" in report.findings[0].message


def test_connector_return_fingerprint_is_order_stable_and_repair_clears_candidate() -> None:
    rule_id = "connector.no_connected_return"
    source = multiconductor_connector(return_named=False)

    def lint_with_source_hash(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        report = evaluate(
            "synthetic-ports",
            coach(netlist).model_copy(update={"netlist_sha256": source_hash}),
            DesignLintPolicy(),
        )
        return source_hash, report

    source_hash, original = lint_with_source_hash(source)
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1

    reordered_source = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered_hash, reordered = lint_with_source_hash(reordered_source)
    assert source_hash != reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    repaired_hash, repaired = lint_with_source_hash(multiconductor_connector(return_connected=True))
    assert source_hash != repaired_hash
    assert rule_id not in {item.rule_id for item in repaired.findings}


def test_return_named_net_is_context_not_proof_of_connector_pin_role() -> None:
    observed_without_roles = multiconductor_connector(return_named=False)
    nets = dict(observed_without_roles.nets)
    nets["0V IFACE 1"] = ("J1.4",)
    observed_with_return_label = observed_without_roles.model_copy(update={"nets": nets})

    report = _lint(observed_with_return_label)
    findings = [item for item in report.findings if item.rule_id == "connector.no_connected_return"]

    assert len(findings) == 1
    finding = findings[0]
    assert (
        "no native symbol function or a source-matched project interface role identifies"
        in finding.message
    )
    assert "net labels look return-related" in finding.message
    assert finding.subject == "J1: return pin role not identified"
    assert finding.evidence["return_named_net_candidates"] == ("J1.4: 0V IFACE 1",)


def test_connected_return_clears_missing_return_candidate() -> None:
    report = _lint(multiconductor_connector(return_connected=True))

    assert report.status == "PASS"
    assert not report.findings


def test_shield_connection_does_not_count_as_a_signal_return() -> None:
    report = _lint(multiconductor_connector(with_shield=True, return_named=False))

    assert any(item.rule_id == "connector.no_connected_return" for item in report.findings)


def test_small_connector_is_excluded_from_missing_return_candidate() -> None:
    two_pins = NetlistContract(
        components={},
        nets={"DATA_A": ("J1.1",), "DATA_B": ("J1.2",)},
        component_symbols={"J1": "Synthetic:DifferentialPort"},
        pin_functions={"J1.1": "D+", "J1.2": "D-", "J1.3": "GND"},
    )

    report = _lint(two_pins)

    assert not any(item.rule_id == "connector.no_connected_return" for item in report.findings)


@pytest.mark.parametrize(
    ("common", "usb_function", "serial_function"),
    [
        pytest.param(True, "PWR", "POWER", id="common-supply-alias"),
        pytest.param(True, "+3.3V", "3V3", id="voltage-alias"),
        pytest.param(False, "VBUS", "VCC", id="different-rail-names"),
        pytest.param(False, "3.3V", "33V", id="different-voltage-names"),
        pytest.param(False, "+5V", "-5V", id="opposite-polarity-rails"),
    ],
)
def test_connector_power_labels_do_not_merge_distinct_domains(
    common: bool,
    usb_function: str,
    serial_function: str,
) -> None:
    report = _lint(
        cross_symbol_power(
            common=common,
            usb_function=usb_function,
            serial_function=serial_function,
        )
    )

    assert report.status == "PASS"
    assert not report.findings


def test_return_pin_disagreement_within_one_connector_needs_review() -> None:
    observed_connector = NetlistContract(
        components={},
        nets={"SIGNAL_RETURN": ("J1.7",), "LOGIC_RETURN": ("J1.9",)},
        component_symbols={"J1": "Synthetic:DB9"},
        pin_functions={"J1.7": "GND", "J1.9": "GND"},
    )

    report = evaluate("synthetic-single-port", coach(observed_connector), DesignLintPolicy())

    assert report.status == "REVIEW"
    assert len(report.findings) == 1
    assert report.findings[0].subject == "Synthetic:DB9: ground/return"
    assert report.findings[0].evidence == {
        "J1.7": ("SIGNAL_RETURN",),
        "J1.9": ("LOGIC_RETURN",),
    }


def test_common_return_across_symbols_keeps_shield_separate() -> None:
    report = _lint(cross_symbol_returns(common=True))

    assert report.status == "PASS"
    assert not report.findings
