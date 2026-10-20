"""Validate native USB hub peer-reference fixture outcomes."""

from collections.abc import Mapping

from .hwrepo.design_lint_report_models import DesignLintReport

USB_MULTI_PORT_REFERENCE_EXPECTATIONS = (
    (
        "usb-multiport-peer-reference-fault",
        (
            ("J1 / U1: USB reference-domain review (port 1)", ("1",)),
            ("J2 / U1: USB reference-domain review (port 2)", ("2",)),
        ),
    ),
    (
        "usb-threeport-peer-reference-fault",
        (("J3 / U1: USB reference-domain review (port 3)", ("3",)),),
    ),
)


def validate_usb_multiport_peer_reference_reports(
    reports: Mapping[tuple[str, str], DesignLintReport],
) -> None:
    """Require exact hub-port localization and quiet common-reference controls."""
    for case, expected in USB_MULTI_PORT_REFERENCE_EXPECTATIONS:
        report = reports[(case, "first")]
        observed = tuple(
            (item.subject, item.evidence.get("USB_port_group"))
            for item in report.findings
            if item.rule_id == "bus.usb_peer_reference_review"
        )
        if observed != expected:
            raise ValueError(f"Native {case} USB peer-reference findings differ: {observed}")

    for case in (
        "usb-multiport-peer-reference-control",
        "usb-threeport-peer-reference-control",
    ):
        report = reports[(case, "first")]
        if any(item.rule_id == "bus.usb_peer_reference_review" for item in report.findings):
            raise ValueError(f"Native common-reference {case} produced a USB peer review")
