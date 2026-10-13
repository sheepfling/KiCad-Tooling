"""Assertions for the native two-domain USB isolator coverage boundary."""

from __future__ import annotations

from .hwrepo.design_lint_report_models import DesignLintReport


def validate_usb_isolator_reference_boundary(report: DesignLintReport) -> None:
    """Require quiet findings with explicit incomplete coverage for an isolator."""
    if any(
        item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
        for item in report.findings
    ):
        raise ValueError("Native intentional USB isolation boundary produced a path finding")
    coverage = report.usb_peer_reference_coverage
    if coverage is None or (
        coverage.status != "INCOMPLETE"
        or coverage.recognized_connector_group_count != 2
        or coverage.supported_connector_group_count != 2
        or coverage.recognized_phy_group_count != 2
        or coverage.supported_phy_group_count != 0
        or coverage.incomplete_group_count != 2
        or coverage.supported_data_path_count != 0
        or coverage.candidate_group_count != 0
        or coverage.path_entries != ()
        or tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in coverage.endpoint_groups or ()
        )
        != (
            ("connector", "J1", None, "SUPPORTED"),
            ("connector", "J2", None, "SUPPORTED"),
            ("phy", "U1", "1", "INCOMPLETE"),
            ("phy", "U1", "2", "INCOMPLETE"),
        )
    ):
        raise ValueError(
            "Native intentional USB isolation did not remain visible as incomplete coverage"
        )
