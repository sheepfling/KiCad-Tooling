"""Verify peer pin outlier, divergence, and cross-symbol cases."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_peer_pin_outlier_cases(ctx: ConnectorReturnFixtureContext):
    """Verify peer pin outlier, divergence, and cross-symbol cases."""
    if ctx.observed_contracts["peer-pin-outlier-control", "first"].nets.get("+5V") != (
        "J1.1",
        "J2.1",
        "J3.1",
    ):
        raise ValueError("Common generic peer-pin control lost its three native assignments")
    peer_pin_minority = ctx.reports["peer-pin-minority-fault", "first"]
    minority_findings = {finding.rule_id: finding for finding in peer_pin_minority.findings}
    if (
        peer_pin_minority.status != "REVIEW"
        or set(minority_findings) != {"connector.peer_pin_assignment_outlier"}
        or minority_findings["connector.peer_pin_assignment_outlier"].subject
        != "Lint:PeerPowerPort pin 1"
        or (
            dict(minority_findings["connector.peer_pin_assignment_outlier"].evidence)
            != {
                "J1.1": ("+5V",),
                "J2.1": ("+5V",),
                "J3.1": ("+3V3",),
                "symbol": ("Lint:PeerPowerPort",),
                "pin_number": ("1",),
                "outlier_pins": ("J3.1",),
            }
        )
    ):
        raise ValueError("Generic exact-symbol minority assignment lost its native evidence")
    peer_pin_divergence = ctx.reports["peer-pin-divergence-fault", "first"]
    divergence_findings = {finding.rule_id: finding for finding in peer_pin_divergence.findings}
    if (
        peer_pin_divergence.status != "REVIEW"
        or set(divergence_findings) != {"connector.peer_pin_assignment_divergence"}
        or divergence_findings["connector.peer_pin_assignment_divergence"].subject
        != "Lint:PeerPowerPort pin 1"
        or (
            dict(divergence_findings["connector.peer_pin_assignment_divergence"].evidence)
            != {
                "J1.1": ("+5V",),
                "J2.1": ("+3V3",),
                "J3.1": ("+12V",),
                "symbol": ("Lint:PeerPowerPort",),
                "pin_number": ("1",),
                "missing_pin_function_pins": ("J1.1", "J2.1", "J3.1"),
            }
        )
    ):
        raise ValueError("Generic exact-symbol no-majority divergence lost its native evidence")
    placeholder_divergence = ctx.reports["generic-placeholder-divergence-fault", "first"]
    placeholder_findings = {finding.rule_id: finding for finding in placeholder_divergence.findings}
    if (
        placeholder_divergence.status != "REVIEW"
        or set(placeholder_findings) != {"connector.peer_pin_assignment_divergence"}
        or placeholder_findings["connector.peer_pin_assignment_divergence"].subject
        != "Lint:PeerPowerPort pin 1"
        or (
            dict(placeholder_findings["connector.peer_pin_assignment_divergence"].evidence)
            != {
                "J1.1": ("+5V",),
                "J2.1": ("+3V3",),
                "J3.1": ("+12V",),
                "symbol": ("Lint:PeerPowerPort",),
                "pin_number": ("1",),
                "missing_pin_function_pins": ("J1.1", "J2.1", "J3.1"),
            }
        )
        or (
            ctx.observed_contracts[
                "generic-placeholder-divergence-fault", "first"
            ].pin_functions.get("J1.1")
            != "Pin_1"
        )
    ):
        raise ValueError("Generic Pin_N placeholder lost lower-confidence peer evidence")
    placeholder_control = ctx.reports["generic-placeholder-control", "first"]
    if placeholder_control.status != "PASS" or placeholder_control.findings:
        raise ValueError("Common generic Pin_N placeholder control no longer passes cleanly")
    cross_fault = ctx.reports["cross-symbol-fault", "first"]
    cross_fault_findings = tuple(
        item for item in cross_fault.findings if item.rule_id == "connector.repeated_pin_function"
    )
    cross_fault_by_subject = {item.subject: item for item in cross_fault_findings}
    if (
        cross_fault.status != "REVIEW"
        or {item.rule_id for item in cross_fault.findings} != {"connector.repeated_pin_function"}
        or set(cross_fault_by_subject)
        != {"multiple connector symbols: ground/return", "multiple connector symbols: PWR"}
        or (
            dict(cross_fault_by_subject["multiple connector symbols: ground/return"].evidence)
            != {"J1.4": ("USB_RETURN",), "J2.7": ("SERIAL_RETURN",)}
        )
        or (
            dict(cross_fault_by_subject["multiple connector symbols: PWR"].evidence)
            != {"J1.1": ("USB_SUPPLY",), "J2.9": ("SERIAL_SUPPLY",)}
        )
    ):
        raise ValueError("Mixed-symbol return/supply fault lost its exact native lint evidence")
    cross_control = ctx.reports["cross-symbol-control", "first"]
    if cross_control.status != "PASS" or cross_control.findings:
        raise ValueError("Mixed-symbol common-return/supply control no longer passes")
    cross_open = ctx.reports["cross-symbol-open", "first"]
    open_return = next(
        (
            item
            for item in cross_open.findings
            if item.subject == "multiple connector symbols: ground/return"
        ),
        None,
    )
    if (
        cross_open.status != "REVIEW"
        or {item.subject for item in cross_open.findings}
        != {"multiple connector symbols: ground/return"}
        or open_return is None
        or (dict(open_return.evidence) != {"J1.4": ("COMMON_RETURN",), "J2.7": ()})
    ):
        raise ValueError("Mixed-symbol open-return fault lost its exact native pin evidence")
