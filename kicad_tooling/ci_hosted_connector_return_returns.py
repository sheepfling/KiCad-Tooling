"""Verify split/common connector return fixtures and native pin assignments."""

from __future__ import annotations

from collections.abc import Mapping

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_numbered_pwm_return_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Verify native fault/control cases for numbered 0V PWM return labels."""
    pwm_fault = ctx.reports["four-db9-pwm-fault", "first"]
    pwm_numbered = next(
        (finding for finding in pwm_fault.findings if finding.rule_id == "net.numbered_returns"),
        None,
    )
    expected_pwm_nets = {
        f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9") for reference in range(1, 5)
    }
    if (
        pwm_fault.status != "REVIEW"
        or {finding.rule_id for finding in pwm_fault.findings}
        != {"connector.repeated_pin_function", "net.numbered_returns"}
        or pwm_numbered is None
        or dict(pwm_numbered.evidence) != expected_pwm_nets
    ):
        raise ValueError(
            "Native 0V PWM return labels did not produce the expected numbered-return review"
        )

    pwm_control = ctx.reports["four-db9-pwm-control", "first"]
    pwm_control_nets = ctx.observed_contracts["four-db9-pwm-control", "first"].nets
    expected_common_pwm_pins = {
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    }
    if (
        pwm_control.status != "PASS"
        or pwm_control.findings
        or set(pwm_control_nets.get("0V PWM", ())) != expected_common_pwm_pins
    ):
        raise ValueError(
            "Native common 0V PWM return control did not preserve the expected pin membership"
        )


def verify_ret_return_label_cases(ctx: ConnectorReturnFixtureContext) -> None:
    """Verify numbered and unindexed RET label reviews against native netlists."""
    numbered = ctx.reports["ret-numbered-fault", "first"]
    numbered_findings = [
        finding for finding in numbered.findings if finding.rule_id == "net.numbered_returns"
    ]
    numbered_evidence = {
        name: pins for finding in numbered_findings for name, pins in finding.evidence.items()
    }
    expected_numbered = {
        "CAN1_GND": ("J1.1",),
        "CAN2_GND": ("J2.1",),
        "I2C1_0V": ("J3.1",),
        "I2C2_0V": ("J4.1",),
        "SPI1_RET": ("J1.2",),
        "SPI2_RET": ("J2.2",),
        "RET1": ("J1.7", "J1.9"),
        "RET2": ("J2.7", "J2.9"),
        "PORT3_RET": ("J3.7", "J3.9"),
        "PORT4_RET": ("J4.7", "J4.9"),
    }
    if (
        numbered.status != "REVIEW"
        or numbered_evidence != expected_numbered
        or any(
            finding.rule_id == "net.return_labels_without_pin_roles"
            for finding in numbered.findings
        )
    ):
        raise ValueError("Native numbered RET labels lost their exact numbered-return review")

    unindexed = ctx.reports["ret-unindexed-fault", "first"]
    unindexed_findings = [
        finding
        for finding in unindexed.findings
        if finding.rule_id == "net.return_labels_without_pin_roles"
    ]
    unindexed_evidence = {
        name: pins for finding in unindexed_findings for name, pins in finding.evidence.items()
    }
    expected_unindexed = {
        "RET_USB": ("J1.7", "J1.9"),
        "RET_SERIAL": ("J2.7", "J2.9"),
    }
    if (
        unindexed.status != "REVIEW"
        or unindexed_evidence != expected_unindexed
        or any(finding.rule_id == "net.numbered_returns" for finding in unindexed.findings)
    ):
        raise ValueError("Native unindexed RET labels lost their exact return-label review")

    control = ctx.reports["ret-control", "first"]
    return_rules = {"net.numbered_returns", "net.return_labels_without_pin_roles"}
    expected_common_pins = {f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)}
    observed_common_pins = set(ctx.observed_contracts["ret-control", "first"].nets.get("RET", ()))
    if (
        return_rules & {finding.rule_id for finding in control.findings}
        or observed_common_pins != expected_common_pins
    ):
        raise ValueError(
            "Native common RET control lost pin membership or raised return-label lint"
        )


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
    verify_numbered_pwm_return_cases(ctx)
    verify_ret_return_label_cases(ctx)

    return db9_control_nets
