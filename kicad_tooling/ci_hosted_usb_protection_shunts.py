"""Acceptance assertions for native USB protection-shunt fixtures."""

from __future__ import annotations

from collections.abc import Mapping

from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.usb_data_path_types import UsbDataPathMismatch


def validate_usb_protection_shunt_fixture_mismatches(
    case: str, mismatches: tuple[UsbDataPathMismatch, ...]
) -> bool:
    """Accept only the exact mapped-pin mismatches authored by shunt fault fixtures."""
    expected_issue = {
        "protection-shunt-pin-fault": "U6.2 is on USB_DP",
        "inline-protection-shunt-fault": "U6.3 is on USB_DM_SHUNT_FAULT; expected USB_DM_PHY",
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
    """Require split-reference, common-reference, and mapped-pin native outcomes."""
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
    if (
        inline_coverage is None
        or inline_coverage.supported_data_path_count != 1
        or any(
            item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
            for item in inline_control.findings
        )
        or inline_coverage.path_entries[0].data_path.protection_shunts[0].reference != "U6"
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
