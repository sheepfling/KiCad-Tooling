"""Project-authored external-protection map and coverage regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint_connector_coverage import mapped_usb_c_protection_pins
from kicad_tooling.hwrepo.external_protection import evaluate
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    ExternalProtectionChannelRequirement,
    ExternalProtectionMap,
    UsbCNetPinAssignment,
    UsbCProtectionAnalysis,
)
from tests.external_protection_support import (
    connector_coverage,
    observed_netlist,
    protection_map,
    usb_c_protection_requirement,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]


def test_exact_tvs_channel_matches_native_component_pin_and_net_inventory() -> None:
    report = evaluate(protection_map(), observed_netlist(), connector_coverage(), "a" * 64)

    assert report.status == "COMPLETE"
    assert report.netlist_sha256 == "a" * 64
    assert report.entries[0].status == "PROTECTED"
    assert report.entries[0].device_references == ("D1",)


def test_explicit_not_required_decision_remains_covered() -> None:
    report = evaluate(
        protection_map(disposition="not_required"),
        observed_netlist(),
        connector_coverage(),
        "b" * 64,
    )

    assert report.status == "COMPLETE"
    assert report.entries[0].status == "NOT_REQUIRED"
    assert "integrated protection" in (report.entries[0].basis or "")


@pytest.mark.parametrize("fault", ("connector-wrong-net", "protector-wrong-net"))
def test_wrong_connector_or_protector_net_is_a_project_requirement_mismatch(fault: str) -> None:
    report = evaluate(
        protection_map(),
        observed_netlist(fault=fault),
        connector_coverage(),
        "c" * 64,
    )

    assert report.status == "INCOMPLETE"
    assert report.entries[0].status == "INCOMPLETE"


@pytest.mark.parametrize("fault", ("wrong-identity", "dnp", "unaccounted-pin"))
def test_wrong_identity_dnp_and_unaccounted_device_pin_fail(fault: str) -> None:
    requirements = protection_map()
    observed = observed_netlist()
    if fault == "wrong-identity":
        requirements = requirements.model_copy(
            update={
                "devices": (
                    requirements.devices[0].model_copy(
                        update={"expected_symbol": "Synthetic:WrongProtector"}
                    ),
                )
            }
        )
    elif fault == "dnp":
        observed = observed_netlist(dnp=("D1",))
    else:
        observed = observed_netlist(extra_device_pin=True)

    report = evaluate(requirements, observed, connector_coverage(), "d" * 64)

    assert report.status == "INCOMPLETE"
    assert report.entries[0].issues


def test_explicit_unmapped_pin_reason_and_usb_c_contract_suppress_duplicate_prompt() -> None:
    mapped = protection_map(unmapped_pin_reasons={"D1.3": "Synthetic NC package pin"})
    observed = observed_netlist(extra_device_pin=True)
    accepted = evaluate(mapped, observed, connector_coverage(), "e" * 64)
    assert accepted.entries[0].status == "PROTECTED"

    usb_c_owned = evaluate(
        None,
        observed,
        connector_coverage(),
        "e" * 64,
        handled_by_existing_contract={"J1.1": "USB_DP"},
        electrical_contract_path="examples/project/tests/electrical.json",
        electrical_contract_sha256="f" * 64,
    )
    assert usb_c_owned.entries[0].status == "HANDLED_BY_EXISTING_CONTRACT"

    duplicate = evaluate(
        protection_map(),
        observed_netlist(),
        connector_coverage(),
        "e" * 64,
        handled_by_existing_contract={"J1.1": "USB_DP"},
    )
    assert duplicate.entries[0].status == "INCOMPLETE"
    assert "already covered" in duplicate.entries[0].issues[0]


def test_usb_c_protection_map_covers_only_matching_signal_pins() -> None:
    requirement = usb_c_protection_requirement()
    port = requirement.ports[0]
    assert isinstance(port.protection, UsbCProtectionAnalysis)
    component = port.protection.components[0].model_copy(
        update={
            "pins": (
                UsbCNetPinAssignment(pin="D1.1", net="USB_DP"),
                UsbCNetPinAssignment(pin="D1.2", net="GND"),
            )
        }
    )
    protection = port.protection.model_copy(update={"components": (component,)})
    analysis = requirement.model_copy(
        update={"ports": (port.model_copy(update={"protection": protection}),)}
    )
    coverage = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic USB-C interface map",
        inventory_review_basis="Synthetic review covered the complete connector inventory",
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number="6",
                        interface_signal="USB_D+",
                        component_pin="J1.6",
                        nets=("USB_DP",),
                    ),
                    ConnectorMappedPinEvidence(
                        interface_pin_number="2",
                        interface_signal="GND",
                        component_pin="J1.2",
                        nets=("GND",),
                    ),
                ),
            ),
        ),
    )
    handled = mapped_usb_c_protection_pins(analysis, coverage)
    assert handled == {"J1.6": "USB_DP"}

    baseline = observed_netlist()
    observed = baseline.model_copy(
        update={
            "nets": {**baseline.nets, "USB_DP": ("J1.6", "D1.1")},
            "component_pin_numbers": {
                **baseline.component_pin_numbers,
                "J1": ("1", "2", "6"),
            },
        }
    )
    report = evaluate(
        None,
        observed,
        coverage,
        "a" * 64,
        handled_by_existing_contract=handled,
    )
    data_line = next(item for item in report.entries if item.connector_pin == "J1.6")
    ground = next(item for item in report.entries if item.connector_pin == "J1.2")
    assert data_line.status == "HANDLED_BY_EXISTING_CONTRACT"
    assert ground.status == "UNDECLARED"


def test_map_rejects_wrong_device_pin_ownership_and_duplicate_connector_pin() -> None:
    with pytest.raises(ValidationError, match="belong to the declared device"):
        ExternalProtectionChannelRequirement(
            device_reference="D1",
            signal_pin="D2.1",
            reference_pin="D1.2",
            reference_net="GND",
        )

    duplicate = protection_map().model_dump(mode="python")
    duplicate["interfaces"] = (duplicate["interfaces"][0], duplicate["interfaces"][0])
    with pytest.raises(ValidationError, match="interface pins must be unique"):
        ExternalProtectionMap.model_validate(duplicate)
