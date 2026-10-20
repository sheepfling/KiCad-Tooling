"""Review named native power-output contacts open across connector aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import lint_report, peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_named_power_output_open_outlier"


def _named_power_output_peer_netlist(
    *,
    anchor_assignments: tuple[str | None, str | None] = ("GND", "GND"),
    target_assignments: tuple[str | None, str | None] = ("VOUT", None),
    function: str = "BIAS_OUT",
    electrical_type: str = "power_out",
    dnp: tuple[str, ...] = (),
    part_id: str | None = None,
):
    return peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        functions=("GND", function),
        electrical_types=("passive", electrical_type),
        dnp=dnp,
        part_id=part_id,
    )


def test_named_power_output_contact_open_on_one_alias_is_reviewed() -> None:
    report = lint_report(_named_power_output_peer_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert {item.rule_id for item in report.findings} == {RULE_ID}
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2 "
        "(BIAS_OUT): named power-output contact is open on a similar connector peer"
    )
    assert finding.evidence["assignments"] == ("J1.2=VOUT", "J2.2=<unassigned>")
    assert finding.evidence["open_pins"] == ("J2.2",)
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert finding.evidence["pin_electrical_type"] == ("power_out",)
    assert finding.evidence["peer_identity_basis"] == ("footprint_value",)
    assert "do not establish" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    assert coverage.footprint_alias_coverage.open_peer_pin_group_count == 1
    assert coverage.footprint_alias_coverage.open_outlier_finding_count == 1


def test_common_named_power_output_peer_is_quiet() -> None:
    report = lint_report(
        _named_power_output_peer_netlist(
            target_assignments=("VOUT", "VOUT"),
        )
    )

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.connector_peer_pin_coverage is not None
    assert report.connector_peer_pin_coverage.footprint_alias_coverage.open_outlier_finding_count == 0


def test_named_power_output_open_requires_common_anchor_and_one_assigned_net() -> None:
    controls = (
        _named_power_output_peer_netlist(anchor_assignments=("GND_A", "GND_B")),
        peer_netlist(
            assignments=(("GND", "GND"), ("VOUT_A", "VOUT_B")),
            functions=("GND", "BIAS_OUT"),
            electrical_types=("passive", "power_out"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), (None, None)),
            functions=("GND", "BIAS_OUT"),
            electrical_types=("passive", "power_out"),
        ),
        _named_power_output_peer_netlist(function="VDD"),
        _named_power_output_peer_netlist(function="GND"),
        _named_power_output_peer_netlist(function="Pin_2"),
        _named_power_output_peer_netlist(electrical_type="power_in"),
        _named_power_output_peer_netlist(electrical_type="input"),
        _named_power_output_peer_netlist(electrical_type="output"),
        _named_power_output_peer_netlist(electrical_type="passive"),
        _named_power_output_peer_netlist(dnp=("J2",)),
        _named_power_output_peer_netlist(part_id="SYNTHETIC-PART-OUTPUT-001"),
    )
    for source in controls:
        report = lint_report(source)
        assert RULE_ID not in {item.rule_id for item in report.findings}

    unanchored = lint_report(controls[0])
    assert unanchored.connector_peer_pin_coverage is not None
    assert (
        unanchored.connector_peer_pin_coverage.footprint_alias_coverage
        .unanchored_open_peer_pin_group_count
        == 1
    )


def test_named_power_output_open_is_stable_under_mapping_order() -> None:
    source = _named_power_output_peer_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    second = next(item for item in lint_report(reordered).findings if item.rule_id == RULE_ID)

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)


def test_named_power_output_open_obeys_project_policy_and_exact_ignore() -> None:
    source = _named_power_output_peer_netlist()
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires an explicit disposition for this output pin",
                ),
            )
        ),
    )
    ignored = lint_report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review records an intentionally unused output contact",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings)
