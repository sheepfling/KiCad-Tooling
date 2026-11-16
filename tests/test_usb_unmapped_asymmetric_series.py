"""Review unmapped USB 2.0 pairs with one direct and one resistor path."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintRuleOverride
from tests.usb_asymmetric_series_support import (
    asymmetric_series_data_map,
    asymmetric_series_netlist,
)
from tests.usb_peer_reference_support import (
    lint_report,
    usb_peer_netlist,
    usb_peer_series_netlist,
    usb_series_data_map,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_unmapped_asymmetric_series"
UsbLine = Literal["D+", "D-"]


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("series_line", ("D+", "D-"))
def test_one_sided_series_resistor_requests_review(series_line: UsbLine) -> None:
    report = lint_report(asymmetric_series_netlist(series_line), path_map=None)
    finding = _finding(report)

    assert finding.mode == "review"
    assert finding.evidence["USB_series_resistor_line"] == (series_line,)
    assert finding.evidence["USB_direct_line"] == (("D-" if series_line == "D+" else "D+"),)
    assert finding.evidence["USB_topology_kind"] == ("one_data_line_series_resistor_other_direct",)
    assert "review whether that line-level difference is intentional" in finding.message.lower()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_and_matching_two_resistor_paths_are_quiet_controls() -> None:
    direct = usb_peer_netlist(connector_reference_net="GND", phy_reference_net="GND")
    matched = usb_peer_series_netlist(connector_reference_net="GND", phy_reference_net="GND")

    assert not any(item.rule_id == RULE_ID for item in lint_report(direct).findings)
    assert not any(item.rule_id == RULE_ID for item in lint_report(matched).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("series_line", ("D+", "D-"))
def test_exact_endpoint_map_records_and_suppresses_intentional_asymmetry(
    series_line: UsbLine,
) -> None:
    report = lint_report(
        asymmetric_series_netlist(series_line),
        path_map=asymmetric_series_data_map(series_line),
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_topology_mismatch_stays_with_existing_path_rule() -> None:
    report = lint_report(asymmetric_series_netlist(), path_map=usb_series_data_map())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_series_component_does_not_make_a_supported_path() -> None:
    report = lint_report(asymmetric_series_netlist("D+", dnp_resistor=True))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_is_configurable_and_exactly_ignorable() -> None:
    source = asymmetric_series_netlist()
    default = _finding(lint_report(source))
    blocked = _finding(
        lint_report(
            source,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires symmetric USB data paths",
            ),
        )
    )
    off = _finding(
        lint_report(
            source,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Reviewed outside this project profile",
            ),
        )
    )
    ignored = _finding(
        lint_report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="Project record approves the mixed topology",
            ),
        )
    )

    assert blocked.mode == "block"
    assert off.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_evidence_is_stable_under_native_netlist_reordering() -> None:
    source = asymmetric_series_netlist()
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

    first = _finding(lint_report(source))
    second = _finding(lint_report(reordered))

    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)
