"""Exact multi-pin USB inline-component contract regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from tests.usb_data_path_support import (
    lint_report,
    usb_inline_component_map,
    usb_inline_component_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_exact_multi_pin_protection_path_is_a_valid_control() -> None:
    path_map = usb_inline_component_map()
    observed = usb_inline_component_netlist()

    assert usb_data_path_mismatches(path_map, observed) == ()
    report = lint_report(observed, path_map)
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)
    run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (run.status, run.requirement_count, run.finding_count) == ("EVALUATED", 1, 0)


@pytest.mark.parametrize(
    ("fault", "expected_line", "expected_issue"),
    (
        ("wrong-positive-input-net", "D+", "U2.1 is on OTHER"),
        ("wrong-reference-net", "D+", "U2.5 is on FLOATING_GND"),
        ("extra-native-pin", "D+", "unexpected 7"),
        ("connected-optional-pin", "D+", "U2.6 is on VBUS"),
        ("unmarked-optional-pin", "D+", "explicit no-connect"),
        ("wrong-symbol", "D+", "U2 symbol is Synthetic:WrongProtection"),
        ("wrong-footprint", "D+", "U2 footprint is Synthetic:DFN"),
        ("dnp", "D+", "U2 is marked DNP"),
    ),
    ids=(
        "wrong-data-pin-net",
        "wrong-component-reference-net",
        "extra-component-pin",
        "unexpected-connected-pin",
        "unmarked-no-connect",
        "stale-symbol-identity",
        "stale-footprint-identity",
        "dnp-component",
    ),
)
def test_inline_component_faults_report_exact_pin_evidence(
    fault: str, expected_line: str, expected_issue: str
) -> None:
    mismatches = usb_data_path_mismatches(
        usb_inline_component_map(), usb_inline_component_netlist(fault=fault)
    )

    assert mismatches
    finding = next(item for item in mismatches if item.line == expected_line)
    assert any(expected_issue in issue for issue in finding.issues)
    report_finding = next(
        item
        for item in lint_report(
            usb_inline_component_netlist(fault=fault), usb_inline_component_map()
        ).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert report_finding.evidence["inline_component"] == ("U2",)
    assert report_finding.evidence["inline_component_identity"] == (
        "Synthetic:UsbProtection; Synthetic:QFN",
    )
    assert "U2.5=GND" in report_finding.evidence["inline_component_pin_assignments"]


def test_missing_inline_component_reports_both_data_lines() -> None:
    mismatches = usb_data_path_mismatches(
        usb_inline_component_map(), usb_inline_component_netlist(fault="missing-component")
    )

    assert {item.line for item in mismatches} == {"D+", "D-"}
    assert all(any("U2 is absent" in issue for issue in item.issues) for item in mismatches)


def test_inline_component_findings_are_order_stable_and_repair_clears_them() -> None:
    path_map = usb_inline_component_map()
    fault = usb_inline_component_netlist(fault="wrong-positive-input-net")
    reordered = fault.model_copy(
        update={
            "components": dict(reversed(tuple(fault.components.items()))),
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "component_symbols": dict(reversed(tuple(fault.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(fault.component_pin_numbers.items()))),
        }
    )
    first = lint_report(fault, path_map)
    second = lint_report(reordered, path_map)
    first_findings = tuple(
        (item.fingerprint, item.evidence)
        for item in first.findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    second_findings = tuple(
        (item.fingerprint, item.evidence)
        for item in second.findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert second_findings == first_findings
    inline = path_map.interfaces[0].inline_component
    assert inline is not None
    reordered_interface = path_map.interfaces[0].model_copy(
        update={
            "inline_component": inline.model_copy(update={"pins": tuple(reversed(inline.pins))})
        }
    )
    reordered_map = path_map.model_copy(update={"interfaces": (reordered_interface,)})
    assert tuple(
        (item.line, item.issues) for item in usb_data_path_mismatches(path_map, fault)
    ) == tuple((item.line, item.issues) for item in usb_data_path_mismatches(reordered_map, fault))
    repaired = evaluate(
        "synthetic-usb-inline-component",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-usb-inline-component",
            observed=usb_inline_component_netlist(),
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(usb_data_path_map=path_map),
    )
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in repaired.findings)


def test_inline_topology_requires_one_complete_project_authored_component_map() -> None:
    path_map = usb_inline_component_map()
    interface = path_map.interfaces[0].model_dump(mode="python")
    interface["inline_component"] = None

    with pytest.raises(ValidationError, match="need an exact component map"):
        type(path_map.interfaces[0]).model_validate(interface)

    interface = path_map.interfaces[0].model_dump(mode="python")
    interface["inline_component"]["pins"] = interface["inline_component"]["pins"][1:]
    with pytest.raises(ValidationError, match="include all four data-path pins"):
        type(path_map.interfaces[0]).model_validate(interface)

    interface = path_map.interfaces[0].model_dump(mode="python")
    interface["inline_component"]["pins"][0]["net"] = "USB_DM_PORT"
    with pytest.raises(ValidationError, match="must match the line's endpoint nets"):
        type(path_map.interfaces[0]).model_validate(interface)
