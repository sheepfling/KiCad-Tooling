"""Configurable review for unsupported multi-pin USB data topologies."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintRuleOverride
from tests.usb_data_path_support import (
    lint_report,
    usb_inline_component_map,
    usb_inline_component_netlist,
)
from tests.usb_peer_reference_support import usb_peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_unmapped_multi_pin_topology"


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def test_unmapped_inline_usb_topology_requests_a_project_map_without_claiming_a_path() -> None:
    report = lint_report(usb_inline_component_netlist(), None)
    finding = _finding(report)

    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.status == "NO_SUPPORTED_PEER_PATHS"
    assert coverage.supported_data_path_count == 0
    assert len(coverage.unsupported_multi_pin_paths) == 1
    assert finding.mode == "review"
    assert finding.subject == "J1 / U1: unmapped USB multi-pin topology port 1 (U2)"
    assert finding.evidence["multi_pin_component"] == (
        "U2: Synthetic:UsbProtection; Synthetic:QFN; 6 native pins",
    )
    assert finding.evidence["USB_D+_connector_side"] == ("USB_DP_PORT: U2.1",)
    assert finding.evidence["USB_D+_PHY_side"] == ("USB_DP_PHY: U2.2",)
    assert finding.evidence["USB_D-_connector_side"] == ("USB_DM_PORT: U2.3",)
    assert finding.evidence["USB_D-_PHY_side"] == ("USB_DM_PHY: U2.4",)
    assert "do not establish a data path" in finding.message
    assert "does not assert component conduction" in finding.message
    assert not any(item.rule_id == "bus.usb_peer_reference_review" for item in report.findings)


def test_exact_project_map_resolves_unmapped_topology_prompt() -> None:
    report = lint_report(usb_inline_component_netlist(), usb_inline_component_map())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 1


def test_map_for_another_data_port_group_does_not_suppress_topology_prompt() -> None:
    path_map = usb_inline_component_map()
    other_port = path_map.interfaces[0].model_copy(update={"data_port_group": "2"})
    report = lint_report(
        usb_inline_component_netlist(),
        path_map.model_copy(update={"interfaces": (other_port,)}),
    )

    finding = _finding(report)
    assert finding.subject == "J1 / U1: unmapped USB multi-pin topology port 1 (U2)"
    assert finding.evidence["USB_port_group"] == ("1",)
    assert finding.evidence["USB_data_map_state"] == (
        "no map matches this connector/PHY port group",
    )
    assert finding.evidence["USB_data_map_sha256"]


def test_direct_usb_path_is_not_a_multi_pin_topology_candidate() -> None:
    report = lint_report(
        usb_peer_netlist(connector_reference_net="GND", phy_reference_net="GND"), None
    )

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.common_reference_path_count == 1


def test_dnp_component_is_not_reported_as_an_unmapped_path_candidate() -> None:
    report = lint_report(usb_inline_component_netlist(fault="dnp"), None)

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.unsupported_multi_pin_paths == ()


def test_endpoint_pair_with_authored_but_stale_map_uses_path_mismatch_only() -> None:
    path_map = usb_inline_component_map()
    interface = path_map.interfaces[0].model_copy(
        update={
            "inline_component": path_map.interfaces[0].inline_component.model_copy(
                update={"expected_symbol": "Synthetic:WrongProtection"}
            )
        }
    )
    report = lint_report(
        usb_inline_component_netlist(),
        path_map.model_copy(update={"interfaces": (interface,)}),
    )

    assert any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)
    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_unmapped_topology_fingerprint_is_stable_under_netlist_order() -> None:
    observed = usb_inline_component_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    first = _finding(lint_report(observed, None))
    second = _finding(lint_report(reordered, None))

    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)


def test_project_can_configure_or_ignore_the_unmapped_topology_prompt() -> None:
    observed = usb_inline_component_netlist()
    control = _finding(lint_report(observed, None))
    blocked = _finding(
        lint_report(
            observed,
            None,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires explicit USB path coverage",
            ),
        )
    )
    disabled = lint_report(
        observed,
        None,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="This board intentionally excludes peer-path review",
        ),
    )
    ignored = lint_report(
        observed,
        None,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=control.fingerprint,
            reason="Reviewed and documented in the project record",
        ),
    )

    assert blocked.mode == "block"
    disabled_finding = _finding(disabled)
    assert disabled_finding.disposition == "RULE_OFF"
    assert _finding(ignored).disposition == "IGNORED"
