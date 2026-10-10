"""Verify neutral DB9 return fault and control behavior."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_db9_neutral_return_cases(ctx: ConnectorReturnFixtureContext):
    """Verify neutral DB9 return fault and control behavior."""
    db9_neutral_fault = ctx.reports["four-db9-neutral-fault", "first"]
    db9_neutral_findings = {
        finding.subject: finding
        for finding in db9_neutral_fault.findings
        if finding.rule_id == "connector.repeated_pin_function"
    }
    expected_neutral_fault_pins = {
        f"J{reference}.{pin}": (f"NET_{chr(64 + reference)}",)
        for reference in range(1, 5)
        for pin in (7, 9)
    }
    if (
        db9_neutral_fault.status != "REVIEW"
        or {finding.rule_id for finding in db9_neutral_fault.findings}
        != {"connector.repeated_pin_function", "connector.no_connected_return"}
        or set(db9_neutral_findings) != {"Lint:DB9: 7", "Lint:DB9: 9"}
        or (
            {
                finding.subject
                for finding in db9_neutral_fault.findings
                if finding.rule_id == "connector.no_connected_return"
            }
            != {f"J{reference}: no connected return" for reference in range(1, 5)}
        )
        or (
            {
                pin: assignment
                for finding in db9_neutral_findings.values()
                for (pin, assignment) in finding.evidence.items()
            }
            != expected_neutral_fault_pins
        )
        or (
            ctx.observed_contracts["four-db9-neutral-fault", "first"].pin_functions.get("J1.7")
            != "7"
        )
        or (
            ctx.observed_contracts["four-db9-neutral-fault", "first"].pin_functions.get("J1.9")
            != "9"
        )
    ):
        actual = {
            "status": db9_neutral_fault.status,
            "findings": tuple(
                (finding.rule_id, finding.subject, dict(finding.evidence))
                for finding in db9_neutral_fault.findings
            ),
            "nets": ctx.observed_contracts["four-db9-neutral-fault", "first"].nets,
            "pin_functions": ctx.observed_contracts[
                "four-db9-neutral-fault", "first"
            ].pin_functions,
        }
        raise ValueError(f"Numeric DB9 neutral-net fixture lost exact REVIEW evidence: {actual!r}")
    db9_neutral_control = ctx.reports["four-db9-neutral-control", "first"]
    if (
        db9_neutral_control.status != "REVIEW"
        or {finding.rule_id for finding in db9_neutral_control.findings}
        != {"connector.no_connected_return"}
        or {finding.subject for finding in db9_neutral_control.findings}
        != {f"J{reference}: no connected return" for reference in range(1, 5)}
    ):
        raise ValueError("Neutral common-net control lost its return-role coverage prompts")
    if ctx.observed_contracts["four-db9-neutral-control", "first"].nets.get("NET_COMMON") != tuple(
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    ):
        raise ValueError("Common neutral-net DB9 control lost its eight native pin assignments")
