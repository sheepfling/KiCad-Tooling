"""Focused synthetic regressions for the open control inputs lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import coach, control_input_pins

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def test_unconnected_reset_enable_and_boot_inputs_are_review_candidates() -> None:
    report = evaluate("synthetic-control-inputs", coach(control_input_pins()), DesignLintPolicy())
    findings = [
        item for item in report.findings if item.rule_id == "control.unconnected_control_input"
    ]

    assert report.status == "REVIEW"
    assert {item.subject for item in findings} == {
        "U1.1: ~{RESET}",
        "U1.2: EN",
        "U1.3: BOOT0",
        "U1.8: RST#",
        "U1.9: BOOT_A",
        "U1.10: IOEXP_RST_N",
        "U1.11: JTAG_EN",
        "U1.12: nRPIBOOT",
        "U1.13: PERST",
    }
    assert {item.evidence["family"] for item in findings} == {
        ("reset",),
        ("enable",),
        ("boot/strap",),
    }
    assert all("no net assignment" in item.message for item in findings)

    connected = evaluate(
        "synthetic-control-inputs",
        coach(control_input_pins(connected=True)),
        DesignLintPolicy(),
    )
    assert connected.status == "PASS"
    assert not connected.findings

    dnp = evaluate(
        "synthetic-control-inputs",
        coach(control_input_pins(dnp=True)),
        DesignLintPolicy(),
    )
    assert dnp.status == "PASS"
    assert not dnp.findings

    blocked = evaluate(
        "synthetic-control-inputs",
        coach(control_input_pins()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="control.unconnected_control_input",
                    mode="block",
                    reason="This project requires every reset and boot pin to be reviewed",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-control-inputs",
        coach(control_input_pins()),
        DesignLintPolicy(
            ignores=tuple(
                DesignLintIgnore(
                    rule_id=item.rule_id,
                    fingerprint=item.fingerprint,
                    reason="Synthetic control intentionally leaves this optional input unused",
                )
                for item in findings
            )
        ),
    )
    assert ignored.status == "PASS"
    assert all(item.disposition == "IGNORED" for item in ignored.findings)
