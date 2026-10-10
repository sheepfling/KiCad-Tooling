"""Focused synthetic regressions for the numbered power rails lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def test_numbered_positive_supply_rail_names_need_review() -> None:
    observed_rails = NetlistContract(
        components={},
        nets={"+5V_1": ("J7.1",), "5V-2": ("J8.1",)},
        component_symbols={"J7": "Synthetic:UsbPower", "J8": "Synthetic:SerialPower"},
        pin_functions={"J7.1": "1", "J8.1": "1"},
    )
    report = evaluate("synthetic-numbered-power", coach(observed_rails), DesignLintPolicy())

    assert report.status == "REVIEW"
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule_id == "net.numbered_power_rails"
    assert finding.subject == "5V"
    assert finding.evidence == {"+5V_1": ("J7.1",), "5V-2": ("J8.1",)}
    assert "do not establish a required connection" in finding.message

    blocked = evaluate(
        "synthetic-numbered-power",
        coach(observed_rails),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="net.numbered_power_rails",
                    mode="block",
                    reason="Numbered external rails require explicit release review",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-numbered-power",
        coach(observed_rails),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="net.numbered_power_rails",
                    mode="off",
                    reason="This board intentionally isolates the named supply domains",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"


def test_channel_prefixed_positive_supply_rail_names_need_review() -> None:
    observed_rails = NetlistContract(
        components={},
        nets={
            "CH2_VDD": ("J1.1",),
            "CH3_VDD": ("J2.1",),
            "P1_5V": ("J3.1",),
            "P2_5.0V": ("J4.1",),
            "RAIL4_VIN": ("J5.1",),
            "RAIL5_VIN": ("J6.1",),
            "CH2_SIGNAL": ("J1.2",),
            "CH3_SIGNAL": ("J2.2",),
            "CH2_VCC": ("J7.1",),
            "CH3_VDDIO": ("J8.1",),
        },
    )
    report = evaluate("synthetic-channel-prefixed-power", coach(observed_rails), DesignLintPolicy())

    assert report.status == "REVIEW"
    findings = {finding.subject: finding for finding in report.findings}
    assert set(findings) == {"CH VDD", "P 5V", "RAIL VIN"}
    assert findings["CH VDD"].evidence == {
        "CH2_VDD": ("J1.1",),
        "CH3_VDD": ("J2.1",),
    }
    assert findings["P 5V"].evidence == {"P1_5V": ("J3.1",), "P2_5.0V": ("J4.1",)}
    assert findings["RAIL VIN"].evidence == {
        "RAIL4_VIN": ("J5.1",),
        "RAIL5_VIN": ("J6.1",),
    }
    assert all(finding.rule_id == "net.numbered_power_rails" for finding in findings.values())


@pytest.mark.parametrize(
    "observed_rails",
    [
        pytest.param(
            NetlistContract(
                components={},
                nets={"CH2_SIGNAL": ("J1.1",), "CH3_SIGNAL": ("J2.1",)},
            ),
            id="numbered-signal-labels",
        ),
        pytest.param(
            NetlistContract(
                components={},
                nets={"CH2_VDD": ("J1.1",), "CH2_VCC": ("J2.1",)},
            ),
            id="distinct-rail-families",
        ),
        pytest.param(
            NetlistContract(components={}, nets={"CH2_VDD": ("J1.1",)}),
            id="single-numbered-rail",
        ),
    ],
)
def test_channel_prefixed_power_name_controls_do_not_infer_or_merge_rails(
    observed_rails: NetlistContract,
) -> None:
    report = evaluate(
        "synthetic-channel-prefixed-power-control",
        coach(observed_rails),
        DesignLintPolicy(),
    )

    assert "net.numbered_power_rails" not in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    "observed_rails",
    [
        pytest.param(
            NetlistContract(
                components={},
                nets={"+5V_1": ("J1.1",), "1V8_2": ("J2.1",)},
                component_symbols={
                    "J1": "Synthetic:PowerIn",
                    "J2": "Synthetic:RegulatedOut",
                },
                pin_functions={"J1.1": "1", "J2.1": "1"},
            ),
            id="different-rail-values",
        ),
        pytest.param(
            NetlistContract(
                components={},
                nets={"+5V1": ("J1.1",), "+5V2": ("J2.1",)},
                component_symbols={"J1": "Synthetic:PowerIn", "J2": "Synthetic:PowerOut"},
                pin_functions={"J1.1": "1", "J2.1": "1"},
            ),
            id="ambiguous-rail-numbering",
        ),
    ],
)
def test_numbered_power_rail_controls_do_not_merge_distinct_or_ambiguous_rails(
    observed_rails: NetlistContract,
) -> None:
    report = evaluate("synthetic-numbered-power-control", coach(observed_rails), DesignLintPolicy())

    assert "net.numbered_power_rails" not in {item.rule_id for item in report.findings}
