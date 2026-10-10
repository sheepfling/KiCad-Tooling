"""Verify split/common connector return fixtures and native pin assignments."""

from __future__ import annotations

from collections.abc import Mapping

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_connector_return_distribution(
    ctx: ConnectorReturnFixtureContext,
) -> Mapping[str, tuple[str, ...]]:
    """Verify split/common connector return fixtures and native pin assignments."""
    expected_rules = {"connector.repeated_pin_function", "net.numbered_returns"}
    fault = ctx.reports["fault", "first"]
    repeated = next(
        (
            finding
            for finding in fault.findings
            if finding.rule_id == "connector.repeated_pin_function"
        ),
        None,
    )
    if (
        fault.status != "REVIEW"
        or {finding.rule_id for finding in fault.findings} != expected_rules
        or repeated is None
        or (
            dict(repeated.evidence)
            != {"J1.1": ("GND1",), "J1.2": ("GND1",), "J2.1": ("GND2",), "J2.2": ("GND2",)}
        )
    ):
        raise ValueError("Split-return fixture no longer produces its expected REVIEW evidence")
    control = ctx.reports["control", "first"]
    if control.status != "PASS" or control.findings:
        raise ValueError("Common-return control fixture no longer passes without findings")
    db9_fault = ctx.reports["four-db9-fault", "first"]
    db9_repeated = next(
        (
            finding
            for finding in db9_fault.findings
            if finding.rule_id == "connector.repeated_pin_function"
        ),
        None,
    )
    expected_db9_pins = {
        f"J{reference}.{pin}": (f"RETURN_PORT_{reference}",)
        for reference in range(1, 5)
        for pin in (7, 9)
    }
    db9_numbered = next(
        (finding for finding in db9_fault.findings if finding.rule_id == "net.numbered_returns"),
        None,
    )
    if (
        db9_fault.status != "REVIEW"
        or {finding.rule_id for finding in db9_fault.findings}
        != {"connector.repeated_pin_function", "net.numbered_returns"}
        or db9_repeated is None
        or (dict(db9_repeated.evidence) != expected_db9_pins)
        or (db9_numbered is None)
        or (
            dict(db9_numbered.evidence)
            != {
                f"RETURN_PORT_{reference}": (f"J{reference}.7", f"J{reference}.9")
                for reference in range(1, 5)
            }
        )
    ):
        actual = {
            "status": db9_fault.status,
            "findings": tuple(
                (finding.rule_id, finding.subject, dict(finding.evidence))
                for finding in db9_fault.findings
            ),
            "nets": ctx.observed_contracts["four-db9-fault", "first"].nets,
            "pin_functions": ctx.observed_contracts["four-db9-fault", "first"].pin_functions,
        }
        raise ValueError(
            f"Four-port DB9 return fault lost exact pins 7/9 REVIEW evidence: {actual!r}"
        )
    db9_control = ctx.reports["four-db9-control", "first"]
    if db9_control.status != "PASS" or db9_control.findings:
        raise ValueError("Common four-port DB9 return control no longer passes cleanly")
    db9_control_nets = ctx.observed_contracts["four-db9-control", "first"].nets
    return db9_control_nets
