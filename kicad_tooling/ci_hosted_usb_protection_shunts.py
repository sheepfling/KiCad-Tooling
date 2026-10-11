"""Acceptance assertions for native USB protection-shunt fixtures."""

from __future__ import annotations

from collections.abc import Mapping

from .hwrepo.design_lint_report_models import DesignLintReport


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
