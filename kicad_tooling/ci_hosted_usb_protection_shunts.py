"""Acceptance assertions for native USB protection-shunt fixtures."""

from __future__ import annotations

from collections.abc import Mapping

from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.usb_data_path_types import UsbDataPathMismatch


def validate_usb_protection_shunt_fixture_mismatches(
    case: str, mismatches: tuple[UsbDataPathMismatch, ...]
) -> bool:
    """Accept only the exact mapped-pin mismatches authored by shunt fault fixtures."""
    if case == "composite-inline-protection-fault":
        if {item.line for item in mismatches} != {"D+", "D-"} or not all(
            any("U2.5 is on unconnected" in issue for issue in item.issues) for item in mismatches
        ):
            raise ValueError("Native composite inline-protection fault omitted exact pin evidence")
        return True
    expected_issue = {
        "protection-shunt-pin-fault": "U6.2 is on USB_DP",
        "inline-protection-shunt-fault": "U6.3 is on USB_DM_SHUNT_FAULT; expected USB_DM_PHY",
        "series-protection-shunt-pin-fault": "U6.1 is on USB_DP_PHY; expected USB_D+",
    }.get(case)
    if expected_issue is None:
        return False
    if tuple(item.line for item in mismatches) != ("protection_shunt",) or not any(
        expected_issue in issue for item in mismatches for issue in item.issues
    ):
        raise ValueError(f"Native {case} fixture omitted its exact mapped protection-pin fault")
    return True


def validate_usb_protection_shunt_fixture_reports(
    reports: Mapping[tuple[str, str], DesignLintReport],
) -> None:
    """Require separate and composite protection-map native outcomes."""
    split = reports[("protection-shunt-split-reference", "first")]
    peer_findings = tuple(
        item for item in split.findings if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(peer_findings) != 1:
        raise ValueError("Native split-reference protection shunt should produce one review")
    evidence = peer_findings[0].evidence
    if evidence.get("USB_mapped_protection_shunts") != (
        "U6 (Synthetic:UsbProtectionArray; Synthetic:DFN-6)",
    ) or "U6.2=BOARD_GND" not in evidence.get("USB_mapped_protection_shunt_pin_assignments", ()):
        raise ValueError("Native protection-shunt review omitted exact pin-map evidence")

    common = reports[("protection-shunt-common-reference", "first")]
    if any(
        item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
        for item in common.findings
    ):
        raise ValueError("Native common-reference protection-shunt control produced a finding")

    faulty = reports[("protection-shunt-pin-fault", "first")]
    path_findings = tuple(
        item for item in faulty.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    if faulty.status != "REVIEW" or tuple(item.evidence.get("line") for item in path_findings) != (
        ("protection_shunt",),
    ):
        raise ValueError("Native protection-shunt pin fault did not produce one exact path finding")
    if not any(
        "U6.2 is on USB_DP" in issue
        for item in path_findings
        for issue in item.evidence.get("issues", ())
    ) or any(item.rule_id == "bus.usb_peer_reference_review" for item in faulty.findings):
        raise ValueError(
            "Native protection-shunt fault omitted exact pin evidence or duplicated review"
        )

    inline_control = reports[("inline-protection-shunt-control", "first")]
    inline_coverage = inline_control.usb_peer_reference_coverage
    inline_path_entries = inline_coverage.path_entries if inline_coverage is not None else None
    inline_data_path = inline_path_entries[0].data_path if inline_path_entries else None
    if (
        inline_coverage is None
        or inline_coverage.supported_data_path_count != 1
        or any(
            item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
            for item in inline_control.findings
        )
        or inline_data_path is None
        or not inline_data_path.protection_shunts
        or inline_data_path.protection_shunts[0].reference != "U6"
    ):
        raise ValueError("Native combined inline-path and mapped-shunt control was not supported")

    inline_fault = reports[("inline-protection-shunt-fault", "first")]
    inline_faults = tuple(
        item for item in inline_fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    if (
        inline_fault.status != "REVIEW"
        or len(inline_faults) != 1
        or inline_faults[0].evidence.get("line") != ("protection_shunt",)
        or not any(
            "U6.3 is on USB_DM_SHUNT_FAULT; expected USB_DM_PHY" in issue
            for issue in inline_faults[0].evidence.get("issues", ())
        )
        or inline_fault.usb_peer_reference_coverage is None
        or inline_fault.usb_peer_reference_coverage.supported_data_path_count != 0
    ):
        raise ValueError("Native combined inline-path and mapped-shunt fault was not localized")

    composite_control = reports[("composite-inline-protection-control", "first")]
    composite_coverage = composite_control.usb_peer_reference_coverage
    composite_path_entries = (
        composite_coverage.path_entries if composite_coverage is not None else None
    )
    composite_data_path = composite_path_entries[0].data_path if composite_path_entries else None
    composite_shunts = (
        composite_data_path.protection_shunts if composite_data_path is not None else ()
    )
    if (
        any(
            item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
            for item in composite_control.findings
        )
        or composite_coverage is None
        or composite_coverage.supported_data_path_count != 1
        or not composite_shunts
        or composite_shunts[0].reference != "U2"
        or len(composite_shunts[0].data_pins) != 4
    ):
        raise ValueError("Native composite inline-protection control was not supported exactly")

    composite_fault = reports[("composite-inline-protection-fault", "first")]
    composite_faults = tuple(
        item for item in composite_fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    if (
        composite_fault.status != "REVIEW"
        or {item.evidence.get("line", ()) for item in composite_faults} != {("D+",), ("D-",)}
        or not all(
            any("U2.5 is on unconnected" in issue for issue in item.evidence.get("issues", ()))
            for item in composite_faults
        )
        or composite_fault.usb_peer_reference_coverage is None
        or composite_fault.usb_peer_reference_coverage.supported_data_path_count != 0
    ):
        raise ValueError("Native composite inline-protection fault lost its exact pin diagnosis")


def validate_usb_series_protection_shunt_fixture_reports(
    reports: Mapping[tuple[str, str], DesignLintReport],
) -> None:
    """Require series-path shunt taps to match exact split, common, and fault maps."""
    split = reports[("series-protection-shunt-split-reference", "first")]
    split_reviews = tuple(
        item for item in split.findings if item.rule_id == "bus.usb_peer_reference_review"
    )
    split_coverage = split.usb_peer_reference_coverage
    if (
        split.status != "REVIEW"
        or len(split_reviews) != 1
        or any(item.rule_id == "bus.usb_data_path_mismatch" for item in split.findings)
        or split_coverage is None
        or split_coverage.supported_data_path_count != 1
        or split_reviews[0].evidence.get("USB_D+_series_resistor")
        != ("R1 (Device:R, 27R; R1.1=USB_D+, R1.2=USB_DP_PHY)",)
        or split_reviews[0].evidence.get("USB_D-_series_resistor")
        != ("R2 (Device:R, 27R; R2.1=USB_D-, R2.2=USB_DM_PHY)",)
        or split_reviews[0].evidence.get("USB_mapped_protection_shunts")
        != ("U6 (Synthetic:UsbProtectionArray; Synthetic:DFN-6)",)
        or "U6.2=USB_GND"
        not in split_reviews[0].evidence.get("USB_mapped_protection_shunt_pin_assignments", ())
    ):
        raise ValueError("Native series-plus-shunt split-reference review lost exact path evidence")

    common = reports[("series-protection-shunt-common-reference", "first")]
    common_coverage = common.usb_peer_reference_coverage
    if (
        any(
            item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
            for item in common.findings
        )
        or common_coverage is None
        or common_coverage.supported_data_path_count != 1
    ):
        raise ValueError("Native series-plus-shunt common-reference control produced a finding")

    fault = reports[("series-protection-shunt-pin-fault", "first")]
    fault_findings = tuple(
        item for item in fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    fault_coverage = fault.usb_peer_reference_coverage
    if (
        fault.status != "REVIEW"
        or len(fault_findings) != 1
        or fault_findings[0].evidence.get("line") != ("protection_shunt",)
        or not any(
            "U6.1 is on USB_DP_PHY; expected USB_D+" in issue
            for issue in fault_findings[0].evidence.get("issues", ())
        )
        or any(item.rule_id == "bus.usb_peer_reference_review" for item in fault.findings)
        or fault_coverage is None
        or fault_coverage.supported_data_path_count != 0
    ):
        raise ValueError("Native series-plus-shunt wrong-side fault was not localized exactly")
