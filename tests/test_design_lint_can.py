"""Focused synthetic regressions for the can lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    can_netlist,
    can_peer_netlist,
    coach,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_can_termination_hint_requires_a_direct_resistor_and_is_configurable() -> None:
    unassigned = can_netlist().model_copy(update={"nets": {}})
    unassigned_report = evaluate("synthetic-can", coach(unassigned), DesignLintPolicy())
    assert ({item.rule_id for item in unassigned_report.findings}) == ({"bus.can_unconnected_line"})
    assert ({item.subject for item in unassigned_report.findings}) == (
        {"U1.1: CANH", "U1.2: CAN_L"}
    )

    missing = evaluate("synthetic-can", coach(can_netlist()), DesignLintPolicy())
    assert (missing.status) == ("REVIEW")
    assert (len(missing.findings)) == (1)
    finding = missing.findings[0]
    assert (finding.rule_id) == ("bus.can_missing_termination")
    assert (finding.evidence) == (
        {
            "CANH": ("CAN_HIGH",),
            "CANL": ("CAN_LOW",),
            "pins": ("U1.1", "U1.2"),
            "termination": (),
        }
    )
    assert ("external or split termination") in (finding.message)

    direct_termination = evaluate("synthetic-can", coach(can_netlist("121R")), DesignLintPolicy())
    assert (direct_termination.status) == ("PASS")
    assert not (direct_termination.findings)

    dnp_termination = can_netlist("121R").model_copy(update={"dnp_components": ("R1",)})
    dnp_report = evaluate("synthetic-can", coach(dnp_termination), DesignLintPolicy())
    assert (dnp_report.findings[0].rule_id) == ("bus.can_missing_termination")

    outside_range = evaluate("synthetic-can", coach(can_netlist("100R")), DesignLintPolicy())
    assert (outside_range.status) == ("REVIEW")

    blocked = evaluate(
        "synthetic-can",
        coach(can_netlist()),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.can_missing_termination",
                    mode="block",
                    reason="This board's CAN interface requires local termination",
                ),
            ),
        ),
    )
    assert (blocked.status) == ("FAIL")


def test_can_termination_finding_is_order_stable_and_population_sensitive() -> None:
    source = can_netlist()
    original = evaluate("synthetic-can", coach(source), DesignLintPolicy())
    rule_id = "bus.can_missing_termination"
    original_finding = next(item for item in original.findings if item.rule_id == rule_id)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered = evaluate("synthetic-can", coach(reordered_source), DesignLintPolicy())
    reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
    assert ((reordered_finding.fingerprint, reordered_finding.evidence)) == (
        (original_finding.fingerprint, original_finding.evidence)
    )

    fitted = evaluate("synthetic-can", coach(can_netlist("121R")), DesignLintPolicy())
    assert (rule_id) not in ({item.rule_id for item in fitted.findings})

    dnp_source = can_netlist("121R").model_copy(update={"dnp_components": ("R1",)})
    dnp_report = evaluate("synthetic-can", coach(dnp_source), DesignLintPolicy())
    dnp_finding = next(item for item in dnp_report.findings if item.rule_id == rule_id)
    assert ((dnp_finding.fingerprint, dnp_finding.evidence)) == (
        (original_finding.fingerprint, original_finding.evidence)
    )


def test_can_peer_pair_divergence_is_a_configurable_review_hint() -> None:
    rule_id = "bus.can_peer_assignment_divergence"
    fault = evaluate(
        "synthetic-can-peers",
        coach(can_peer_netlist(divergent_peer=True)),
        DesignLintPolicy(),
    )
    findings = tuple(item for item in fault.findings if item.rule_id == rule_id)
    assert (fault.status) == ("REVIEW")
    assert (len(findings)) == (1)
    finding = findings[0]
    assert (finding.mode) == ("review")
    assert (finding.evidence) == (
        {
            "shared_role": ("CANH",),
            "shared_net": ("NET_A",),
            "complementary_role": ("CANL",),
            "complementary_nets": ("NET_B", "NET_C"),
            "participants": (
                "U1:U1.1=CANH/NET_A;U1.2=CANL/NET_B",
                "U2:U2.1=CANH/NET_A;U2.2=CANL/NET_B",
                "U3:U3.1=CANH/NET_A;U3.2=CANL/NET_C",
            ),
        }
    )
    assert ("do not establish common-bus intent") in (finding.message)

    for mode, expected_status in (("block", "FAIL"), ("off", "PASS")):
        report = evaluate(
            "synthetic-can-peers",
            coach(can_peer_netlist(divergent_peer=True)),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode=mode,
                        reason="Exercise the project-configurable review lifecycle",
                    ),
                )
            ),
        )
        assert (report.status) == (expected_status)

    ignored = evaluate(
        "synthetic-can-peers",
        coach(can_peer_netlist(divergent_peer=True)),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=rule_id,
                    fingerprint=finding.fingerprint,
                    reason="The split CAN pair is intentional in this synthetic control",
                ),
            )
        ),
    )
    assert (ignored.status) == ("PASS")
    assert (next(item for item in ignored.findings if item.rule_id == rule_id).disposition) == (
        "IGNORED"
    )

    same_bus = evaluate("synthetic-can-peers", coach(can_peer_netlist()), DesignLintPolicy())
    separate_buses = evaluate(
        "synthetic-can-peers",
        coach(can_peer_netlist(separate_buses=True)),
        DesignLintPolicy(),
    )
    assert (rule_id) not in ({item.rule_id for item in same_bus.findings})
    assert (rule_id) not in ({item.rule_id for item in separate_buses.findings})


def test_can_peer_pair_divergence_is_order_stable_and_dnp_aware() -> None:
    rule_id = "bus.can_peer_assignment_divergence"
    source = can_peer_netlist(divergent_peer=True)
    original = evaluate("synthetic-can-peers", coach(source), DesignLintPolicy())
    finding = next(item for item in original.findings if item.rule_id == rule_id)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered = evaluate("synthetic-can-peers", coach(reordered_source), DesignLintPolicy())
    reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
    assert ((reordered_finding.fingerprint, reordered_finding.evidence)) == (
        (finding.fingerprint, finding.evidence)
    )

    dnp_peer = source.model_copy(update={"dnp_components": ("U3",)})
    dnp_report = evaluate("synthetic-can-peers", coach(dnp_peer), DesignLintPolicy())
    assert (rule_id) not in ({item.rule_id for item in dnp_report.findings})

    repaired = evaluate("synthetic-can-peers", coach(can_peer_netlist()), DesignLintPolicy())
    assert (rule_id) not in ({item.rule_id for item in repaired.findings})
