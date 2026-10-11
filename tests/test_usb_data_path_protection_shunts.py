"""Exact-map and heuristic coverage for multi-pin USB protection shunts."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from tests.usb_protection_shunt_support import protection_shunt_map, protection_shunt_netlist

RULE_ID = "bus.usb_peer_reference_review"
PATH_RULE_ID = "bus.usb_data_path_mismatch"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def lint_report(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
):
    return evaluate(
        "synthetic-usb-protection-shunt",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-usb-protection-shunt",
            observed=observed,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(usb_data_path_map=path_map),
    )


def test_exact_mapped_protection_array_supports_split_reference_review() -> None:
    observed = protection_shunt_netlist()
    path_map = protection_shunt_map()
    assert usb_data_path_mismatches(path_map, observed) == ()

    report = lint_report(observed, path_map)
    reviews = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert len(reviews) == 1
    assert PATH_RULE_ID not in {item.rule_id for item in report.findings}
    assert reviews[0].evidence["USB_mapped_protection_shunts"] == (
        "U6 (Synthetic:UsbProtectionArray; Synthetic:DFN-6)",
    )
    assert "U6.2=BOARD_GND" in reviews[0].evidence["USB_mapped_protection_shunt_pin_assignments"]
    path = report.usb_peer_reference_coverage.path_entries[0]
    assert path.data_path.protection_shunts[0].reference == "U6"
    assert path.data_path.protection_shunts[0].data_pins[0].line == "D+"
    assert "mapped protection shunt: U6" in text_report(report)


@pytest.mark.parametrize(
    "fault",
    (
        "wrong-symbol",
        "wrong-footprint",
        "dnp",
        "missing-pin",
        "wrong-data-net",
        "missing-no-connect",
    ),
)
def test_stale_or_faulty_shunt_map_fails_closed(fault: str) -> None:
    observed = protection_shunt_netlist()
    if fault == "wrong-symbol":
        observed = observed.model_copy(
            update={
                "component_symbols": {
                    **observed.component_symbols,
                    "U6": "Synthetic:WrongProtection",
                }
            }
        )
    elif fault == "wrong-footprint":
        observed = observed.model_copy(
            update={
                "components": {
                    **observed.components,
                    "U6": observed.components["U6"].model_copy(
                        update={"footprint": "Synthetic:WrongPackage"}
                    ),
                }
            }
        )
    elif fault == "dnp":
        observed = observed.model_copy(update={"dnp_components": ("U6",)})
    elif fault == "missing-pin":
        observed = observed.model_copy(
            update={
                "component_pin_numbers": {
                    **observed.component_pin_numbers,
                    "U6": ("1", "2", "3", "4", "5"),
                }
            }
        )
    elif fault == "wrong-data-net":
        nets = dict(observed.nets)
        nets["USB_DP"] = tuple(pin for pin in nets["USB_DP"] if pin != "U6.1")
        nets["OTHER"] = ("U6.1",)
        observed = observed.model_copy(update={"nets": nets})
    else:
        observed = observed.model_copy(update={"unconnected_nets": {}})

    report = lint_report(observed, protection_shunt_map())
    path_findings = tuple(item for item in report.findings if item.rule_id == PATH_RULE_ID)
    assert len(path_findings) == 1
    assert path_findings[0].evidence["line"] == ("protection_shunt",)
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage.supported_data_path_count == 0


def test_unmapped_array_and_unexplained_data_peer_remain_unsupported() -> None:
    unmapped = lint_report(protection_shunt_netlist(), None)
    assert RULE_ID not in {item.rule_id for item in unmapped.findings}
    assert unmapped.usb_peer_reference_coverage.supported_data_path_count == 0

    observed = protection_shunt_netlist()
    extra = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "TP1": ComponentContract(value="Synthetic test point", footprint="Synthetic:TP"),
            },
            "component_symbols": {
                **observed.component_symbols,
                "TP1": "Connector:TestPoint",
            },
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "TP1": ("1",),
            },
            "pin_functions": {**observed.pin_functions, "TP1.1": "TestPoint"},
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "TP1.1": "passive",
            },
            "nets": {**observed.nets, "USB_DP": (*observed.nets["USB_DP"], "TP1.1")},
        }
    )
    report = lint_report(extra, protection_shunt_map())
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage.supported_data_path_count == 0


def test_explicit_common_reference_policy_suppresses_the_review() -> None:
    observed = protection_shunt_netlist(common_reference=True)
    path_map = protection_shunt_map(reference_policy="common_net")
    report = lint_report(observed, path_map)

    assert usb_data_path_mismatches(path_map, observed) == ()
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage.common_reference_path_count == 1
    assert (
        report.usb_peer_reference_coverage.path_entries[0].data_path.protection_shunts[0].reference
        == "U6"
    )


def test_shunt_path_evidence_is_stable_under_native_mapping_order() -> None:
    observed = protection_shunt_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
        }
    )
    path_map = protection_shunt_map()
    first = lint_report(observed, path_map)
    second = lint_report(reordered, path_map)
    assert tuple((item.fingerprint, item.evidence) for item in first.findings) == tuple(
        (item.fingerprint, item.evidence) for item in second.findings
    )
    assert first.usb_peer_reference_coverage == second.usb_peer_reference_coverage

    faulty = observed.model_copy(
        update={
            "component_symbols": {
                **observed.component_symbols,
                "U6": "Synthetic:WrongProtection",
            }
        }
    )
    faulty_reordered = faulty.model_copy(
        update={
            "components": dict(reversed(tuple(faulty.components.items()))),
            "component_symbols": dict(reversed(tuple(faulty.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(faulty.component_pin_numbers.items()))),
            "nets": dict(reversed(tuple(faulty.nets.items()))),
        }
    )
    faulty_first = lint_report(faulty, path_map)
    faulty_second = lint_report(faulty_reordered, path_map)
    for rule_id in (RULE_ID, PATH_RULE_ID):
        first_findings = tuple(
            (item.fingerprint, item.evidence)
            for item in faulty_first.findings
            if item.rule_id == rule_id
        )
        second_findings = tuple(
            (item.fingerprint, item.evidence)
            for item in faulty_second.findings
            if item.rule_id == rule_id
        )
        assert first_findings == second_findings
