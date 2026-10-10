"""Verify power-domain expectations across peer connectors."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_peer_power_inputs(ctx: ConnectorReturnFixtureContext):
    """Verify power-domain expectations across peer connectors."""
    peer_power_fault = ctx.reports["peer-power-fault", "first"]
    peer_power_findings = {finding.rule_id: finding for finding in peer_power_fault.findings}
    if (
        peer_power_fault.status != "REVIEW"
        or set(peer_power_findings)
        != {"connector.repeated_pin_function", "net.numbered_power_rails"}
        or dict(peer_power_findings["connector.repeated_pin_function"].evidence)
        != {"J1.1": ("+5V_1",), "J2.1": ("5V-2",), "J3.1": ()}
        or (
            dict(peer_power_findings["net.numbered_power_rails"].evidence)
            != {"+5V_1": ("J1.1",), "5V-2": ("J2.1",)}
        )
    ):
        raise ValueError("Generic peer power fault lost its exact open-pin REVIEW evidence")
    peer_power_control = ctx.reports["peer-power-control", "first"]
    if peer_power_control.status != "PASS" or peer_power_control.findings:
        raise ValueError("Common generic peer power control no longer passes cleanly")
    if ctx.observed_contracts["peer-power-control", "first"].nets.get("+5V") != (
        "J1.1",
        "J2.1",
        "J3.1",
    ):
        raise ValueError("Common generic peer power control lost its three native pin assignments")
    peer_pin_fault = ctx.reports["peer-pin-outlier-fault", "first"]
    peer_pin_findings = {finding.rule_id: finding for finding in peer_pin_fault.findings}
    if (
        peer_pin_fault.status != "REVIEW"
        or set(peer_pin_findings) != {"connector.peer_pin_assignment_outlier"}
        or peer_pin_findings["connector.peer_pin_assignment_outlier"].subject
        != "Lint:PeerPowerPort pin 1"
        or (
            dict(peer_pin_findings["connector.peer_pin_assignment_outlier"].evidence)
            != {
                "J1.1": ("+5V",),
                "J2.1": ("+5V",),
                "J3.1": (),
                "symbol": ("Lint:PeerPowerPort",),
                "pin_number": ("1",),
                "outlier_pins": ("J3.1",),
            }
        )
    ):
        raise ValueError("Generic exact-symbol peer pin fault lost its exact native evidence")
    peer_pin_control = ctx.reports["peer-pin-outlier-control", "first"]
    if peer_pin_control.status != "PASS" or peer_pin_control.findings:
        raise ValueError("Common generic exact-symbol peer pin control no longer passes cleanly")
