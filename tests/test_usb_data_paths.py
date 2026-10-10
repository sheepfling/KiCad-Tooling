"""Synthetic PHY-specific USB data-path lint regressions."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
    UsbDataPathLineRequirement,
    UsbDataSeriesResistorRequirement,
)
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from tests.usb_data_path_support import (
    lint_report,
    usb_data_map,
    usb_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_documented_integrated_phy_direct_path_is_a_valid_control() -> None:
    mismatches = usb_data_path_mismatches(usb_data_map("direct"), usb_netlist("direct"))
    assert mismatches == ()
    report = lint_report(usb_netlist("direct"), usb_data_map("direct"))
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)
    run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert run.status == "EVALUATED"
    assert (
        run.map_sha256
        == hashlib.sha256(usb_data_map("direct").model_dump_json().encode("utf-8")).hexdigest()
    )
    assert run.requirement_count == 1
    assert run.finding_count == 0


def test_documented_external_phy_and_27r_pair_is_a_valid_control() -> None:
    report = lint_report(usb_netlist(), usb_data_map())
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


def test_missing_required_resistor_is_new_coverage_beyond_named_pair_prompt() -> None:
    missing = usb_netlist(fault="missing-dp-resistor")
    report = lint_report(missing, usb_data_map())
    path_findings = [
        item for item in report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    ]
    assert len(path_findings) == 1
    assert path_findings[0].subject == "usb-port-1: USB D+ path"
    assert "R1 is absent" in path_findings[0].evidence["issues"][0]
    assert report.netlist_sha256 == "a" * 64
    assert not any(
        item.rule_id == "bus.usb_data_path_mismatch" for item in lint_report(missing, None).findings
    )
    unconfigured = next(
        item
        for item in lint_report(missing, None).mapped_check_runs
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert unconfigured.status == "NOT_CONFIGURED"
    assert unconfigured.requirement_count == 0
    fault_run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert fault_run.status == "EVALUATED"
    assert fault_run.finding_count == 1


def test_missing_path_evidence_is_order_stable_and_repair_clears_it() -> None:
    path_map = usb_data_map()
    missing = usb_netlist(fault="missing-dp-resistor")
    reordered = missing.model_copy(
        update={
            "components": dict(reversed(tuple(missing.components.items()))),
            "nets": dict(reversed(tuple(missing.nets.items()))),
            "component_symbols": dict(reversed(tuple(missing.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(missing.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(missing.pin_functions.items()))),
        }
    )
    original_report = lint_report(missing, path_map)
    reordered_report = lint_report(reordered, path_map)
    original_finding = next(
        item for item in original_report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    reordered_finding = next(
        item for item in reordered_report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )

    repaired_report = lint_report(usb_netlist(), path_map)
    assert "bus.usb_data_path_mismatch" not in {item.rule_id for item in repaired_report.findings}


@pytest.mark.parametrize(
    ("fault", "expected"),
    (
        ("wrong-dp-resistor-value", "R1 is 22 Ω"),
        ("dnp-dp-resistor", "R1 is marked DNP"),
        ("wrong-dp-resistor-net", "R1 spans"),
    ),
    ids=("wrong-value", "dnp", "wrong-net"),
)
def test_value_dnp_and_wrong_net_mutations_are_detected(fault: str, expected: str) -> None:
    mismatches = usb_data_path_mismatches(usb_data_map(), usb_netlist(fault=fault))
    assert len(mismatches) == 1
    assert any(expected in item for item in mismatches[0].issues)


def test_rule_uses_project_review_block_off_and_exact_ignore_lifecycle() -> None:
    fault = usb_netlist(fault="missing-dp-resistor")
    blocked = lint_report(
        fault,
        usb_data_map(),
        override=DesignLintRuleOverride(
            rule_id="bus.usb_data_path_mismatch",
            mode="block",
            reason="The approved external PHY topology is a release requirement",
        ),
    )
    assert blocked.status == "FAIL"

    finding = next(
        item
        for item in lint_report(fault, usb_data_map()).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    ignored = lint_report(
        fault,
        usb_data_map(),
        ignore=DesignLintIgnore(
            rule_id=finding.rule_id,
            fingerprint=finding.fingerprint,
            reason="Reviewed against the approved assembly option",
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert ignored_finding.disposition == "IGNORED"

    disabled = lint_report(
        fault,
        usb_data_map(),
        override=DesignLintRuleOverride(
            rule_id="bus.usb_data_path_mismatch",
            mode="off",
            reason="The documented PHY disposition is not used in this configuration",
        ),
    )
    disabled_finding = next(
        item for item in disabled.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert disabled_finding.disposition == "RULE_OFF"
    disabled_run = next(
        item for item in disabled.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (disabled_run.status, disabled_run.mode) == ("EVALUATED", "off")
    assert disabled_run.finding_count == 1


def test_contract_rejects_ambiguous_or_unjustified_topologies() -> None:
    with pytest.raises(ValidationError, match="Direct USB data paths"):
        UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP",
            phy_net="USB_DP_PHY",
            topology="direct",
        )
    with pytest.raises(ValidationError, match="series-resistor paths"):
        UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP",
            phy_net="USB_DP",
            topology="series_resistor",
        )
    with pytest.raises(ValidationError, match="range is reversed"):
        UsbDataSeriesResistorRequirement(
            reference="R1",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:0603",
            minimum_ohms=28,
            maximum_ohms=27,
        )
