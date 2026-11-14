"""Review split generic power contacts on unanchored connector aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_footprint_generic_power_pin_split import (
    ConnectorFootprintGenericPowerPinSplitEvidence,
)
from kicad_tooling.hwrepo.connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.connector_footprint_peer_support import peer_netlist
from tests.connector_peer_unanchored_scope_support import lint_report, reviewed_coverage

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.footprint_peer_generic_power_pin_unanchored_split"


def _source(
    *,
    power_type: str = "power_in",
    power_function: str = "Pin_1",
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("POWER_A", "POWER_B"),
        ("SIGNAL_A", "SIGNAL_B"),
    ),
):
    return peer_netlist(
        assignments=assignments,
        functions=(power_function, "Pin_2"),
        electrical_types=(power_type, "passive"),
    )


def _three_peer_source() -> NetlistContract:
    references = ("J1", "J2", "J3")
    components = {
        reference: ComponentContract(
            value="Synthetic three-contact connector",
            footprint="Synthetic:Connector_2x1",
        )
        for reference in references
    }
    nets = {
        f"{role}_{index}": (f"{reference}.{pin_number}",)
        for pin_number, role in (("1", "POWER"), ("2", "SIGNAL"))
        for index, reference in enumerate(references, start=1)
    }
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={
            reference: f"Synthetic:GenericPortAlias{index}"
            for index, reference in enumerate(references, start=1)
        },
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            f"{reference}.{pin_number}": f"Pin_{pin_number}"
            for reference in references
            for pin_number in ("1", "2")
        },
        pin_electrical_types={
            **{f"{reference}.1": "power_in" for reference in references},
            **{f"{reference}.2": "passive" for reference in references},
        },
    )


def _rule_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("power_type", ("power_in", "power_out"))
def test_unanchored_generic_power_pins_on_similar_connectors_are_reviewed(
    power_type: str,
) -> None:
    report = lint_report(_source(power_type=power_type))

    assert report.status == "REVIEW"
    (finding,) = _rule_findings(report)
    assert finding.mode == "review"
    assert finding.evidence["pin_number"] == ("1",)
    assert finding.evidence["pin_electrical_type"] == (power_type,)
    assert finding.evidence["assignments"] == ("J1.1=POWER_A", "J2.1=POWER_B")
    assert finding.evidence["common_anchor_pin_numbers"] == ()
    assert "does not establish that the nets should be joined" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_three_unanchored_power_peers_produce_one_localized_pin_prompt() -> None:
    (finding,) = _rule_findings(lint_report(_three_peer_source()))

    assert finding.evidence["assignments"] == (
        "J1.1=POWER_1",
        "J2.1=POWER_2",
        "J3.1=POWER_3",
    )
    assert finding.evidence["pin_number"] == ("1",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        pytest.param(
            _source(assignments=(("POWER", "POWER"), ("SIGNAL_A", "SIGNAL_B"))),
            id="power-pin-common",
        ),
        pytest.param(
            _source(assignments=(("POWER_A", "POWER_B"), ("COMMON_SIGNAL", "COMMON_SIGNAL"))),
            id="separate-common-net-anchor",
        ),
        pytest.param(
            _source(power_function="VBUS"),
            id="meaningful-function-owned-by-named-rules",
        ),
        pytest.param(
            _source(power_type="passive"),
            id="passive-contact",
        ),
        pytest.param(
            _source(power_type="input"),
            id="signal-input-contact",
        ),
    ),
)
def test_common_or_non_power_peer_contacts_are_controls(source) -> None:
    assert not _rule_findings(lint_report(source))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mismatched_native_power_types_and_separate_peer_groups_stay_quiet() -> None:
    source = _source()
    mismatched = source.model_copy(
        update={"pin_electrical_types": {**source.pin_electrical_types, "J2.1": "passive"}}
    )
    separate = reviewed_coverage(source, groups=("port-a", "port-b"))

    assert not _rule_findings(lint_report(mismatched))
    assert not _rule_findings(lint_report(source, separate))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_current_shared_peer_scope_leaves_split_to_scoped_assignment_rule() -> None:
    source = _source()
    report = lint_report(source, reviewed_coverage(source))

    assert not _rule_findings(report)
    assert any(
        item.rule_id == "connector.footprint_peer_pin_unanchored_assignment_divergence"
        and item.evidence["pin_number"] == ("1",)
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_turn_off_the_power_split_review() -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Synthetic test of a project-owned review decision.",
            ),
        )
    )

    (finding,) = _rule_findings(lint_report(_source(), policy=policy))
    assert finding.mode == "off"
    assert finding.disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_native_mapping_reordering() -> None:
    source = _source()
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
    first = _rule_findings(lint_report(source))
    second = _rule_findings(lint_report(reordered))

    assert tuple((item.fingerprint, item.evidence) for item in first) == tuple(
        (item.fingerprint, item.evidence) for item in second
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_evidence_rejects_a_power_type_that_disagrees_with_native_pins() -> None:
    scan = scan_connector_footprint_peer_pin_assignments(_source())
    divergence = scan.unanchored_divergences[0]

    with pytest.raises(ValueError, match="native peer pin types"):
        ConnectorFootprintGenericPowerPinSplitEvidence(
            scan=scan,
            divergence=divergence,
            pin_electrical_type="passive",
        )
