"""Exact USB inline data-path and protection-shunt map regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from tests.usb_data_path_support import lint_report, usb_inline_component_netlist
from tests.usb_inline_protection_shunt_support import (
    composite_inline_protection_test_map,
    inline_protection_shunt_map,
    inline_protection_shunt_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

PATH_RULE = "bus.usb_data_path_mismatch"
PEER_RULE = "bus.usb_peer_reference_review"


def test_mapped_inline_path_can_include_shunts_on_either_data_net() -> None:
    observed = inline_protection_shunt_netlist()
    path_map = inline_protection_shunt_map()

    mismatches = usb_data_path_mismatches(path_map, observed)
    assert not mismatches, tuple((item.line, item.issues) for item in mismatches)
    report = lint_report(observed, path_map)
    assert not any(item.rule_id in {PATH_RULE, PEER_RULE} for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 1
    path = report.usb_peer_reference_coverage.path_entries[0].data_path
    assert path.protection_shunts[0].reference == "U6"
    assert {(item.line, item.net) for item in path.protection_shunts[0].data_pins} == {
        ("D+", "USB_DP_PORT"),
        ("D-", "USB_DM_PHY"),
    }
    assert "U6.2=GND" in path.protection_shunts[0].pin_assignments


def test_misassigned_inline_path_shunt_fails_the_exact_map_closed() -> None:
    observed = inline_protection_shunt_netlist(wrong_dminus_side=True)
    path_map = inline_protection_shunt_map()

    report = lint_report(observed, path_map)
    findings = tuple(item for item in report.findings if item.rule_id == PATH_RULE)
    assert len(findings) == 1, tuple((item.subject, item.evidence) for item in findings)
    assert findings[0].evidence["line"] == ("protection_shunt",)
    assert "U6.3 is on USB_DM_PORT; expected USB_DM_PHY" in findings[0].evidence["issues"]
    assert PEER_RULE not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 0


def test_inline_shunt_fault_evidence_is_stable_under_netlist_order() -> None:
    observed = inline_protection_shunt_netlist(wrong_dminus_side=True)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
        }
    )
    path_map = inline_protection_shunt_map()
    first = lint_report(observed, path_map)
    second = lint_report(reordered, path_map)

    assert tuple((item.fingerprint, item.evidence) for item in first.findings) == tuple(
        (item.fingerprint, item.evidence) for item in second.findings
    )
    assert first.usb_peer_reference_coverage == second.usb_peer_reference_coverage


@pytest.mark.design_lint_rule(rule_id=PATH_RULE)
@pytest.mark.design_lint_rule(rule_id=PEER_RULE)
def test_one_exact_component_can_cover_inline_path_and_protection_shunts() -> None:
    observed = usb_inline_component_netlist()
    path_map = composite_inline_protection_test_map()

    assert usb_data_path_mismatches(path_map, observed) == ()
    report = lint_report(observed, path_map)
    assert not any(item.rule_id in {PATH_RULE, PEER_RULE} for item in report.findings)
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.supported_data_path_count == 1
    shunt = coverage.path_entries[0].data_path.protection_shunts[0]
    assert shunt.reference == "U2"
    assert {(item.line, item.pin, item.net) for item in shunt.data_pins} == {
        ("D+", "U2.1", "USB_DP_PORT"),
        ("D+", "U2.2", "USB_DP_PHY"),
        ("D-", "U2.3", "USB_DM_PORT"),
        ("D-", "U2.4", "USB_DM_PHY"),
    }


@pytest.mark.design_lint_rule(rule_id=PATH_RULE)
@pytest.mark.design_lint_rule(rule_id=PEER_RULE)
def test_composite_inline_protection_fault_localizes_the_wrong_line() -> None:
    observed = usb_inline_component_netlist()
    nets = dict(observed.nets)
    nets["USB_DP_PHY"] = tuple(pin for pin in nets["USB_DP_PHY"] if pin != "U2.2")
    nets["USB_DP_PORT"] = (*nets["USB_DP_PORT"], "U2.2")
    report = lint_report(
        observed.model_copy(update={"nets": nets}),
        composite_inline_protection_test_map(),
    )

    findings = tuple(item for item in report.findings if item.rule_id == PATH_RULE)
    assert len(findings) == 1
    assert findings[0].evidence["line"] == ("D+",)
    assert "U2.2 is on USB_DP_PORT; expected USB_DP_PHY" in findings[0].evidence["issues"]
    assert PEER_RULE not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 0


@pytest.mark.design_lint_rule(rule_id=PATH_RULE)
@pytest.mark.design_lint_rule(rule_id=PEER_RULE)
def test_composite_inline_protection_findings_are_order_stable() -> None:
    observed = usb_inline_component_netlist()
    nets = dict(observed.nets)
    nets["USB_DP_PHY"] = tuple(pin for pin in nets["USB_DP_PHY"] if pin != "U2.2")
    nets["USB_DP_PORT"] = (*nets["USB_DP_PORT"], "U2.2")
    fault = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "nets": dict(reversed(tuple(nets.items()))),
        }
    )
    reference_order = observed.model_copy(update={"nets": dict(observed.nets)})
    path_map = composite_inline_protection_test_map()

    first = lint_report(fault, path_map)
    second = lint_report(reference_order.model_copy(update={"nets": nets}), path_map)
    assert tuple((item.fingerprint, item.evidence) for item in first.findings) == tuple(
        (item.fingerprint, item.evidence) for item in second.findings
    )
    assert first.usb_peer_reference_coverage == second.usb_peer_reference_coverage


def test_composite_protection_map_rejects_partial_or_different_pin_contracts() -> None:
    path_map = composite_inline_protection_test_map()
    interface = path_map.interfaces[0]
    shunt = interface.protection_shunts[0]

    with pytest.raises(
        ValidationError, match="USB protection shunts must map one pin per data line"
    ):
        UsbDataPathMap.model_validate(
            {
                **path_map.model_dump(),
                "interfaces": (
                    {
                        **interface.model_dump(),
                        "protection_shunts": (
                            shunt.model_copy(update={"data_pins": shunt.data_pins[:2]}),
                        ),
                    },
                ),
            }
        )

    with pytest.raises(ValidationError, match="exact identity and pin map"):
        UsbDataPathMap.model_validate(
            {
                **path_map.model_dump(),
                "interfaces": (
                    {
                        **interface.model_dump(),
                        "protection_shunts": (
                            shunt.model_copy(
                                update={
                                    "pins": tuple(item for item in shunt.pins if item.pin != "U2.6")
                                }
                            ),
                        ),
                    },
                ),
            }
        )
