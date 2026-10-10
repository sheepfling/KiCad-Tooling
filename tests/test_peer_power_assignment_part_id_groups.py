"""Part-ID component peer power assignment applicability and stability cases."""

from __future__ import annotations

import pytest

from tests.component_peer_power_assignment_support import RULE_ID, lint_report, peer_power_netlist

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint, pytest.mark.power_lint]


def test_shared_part_id_symbol_aliases_prompt_for_split_power_and_return_assignments() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "synthetic-power-001"}
    )

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 2
    assert {item.evidence["peer_role"] for item in findings} == {
        ("ground/return",),
        ("supply",),
    }
    for finding in findings:
        assert finding.mode == "review"
        assert finding.evidence["peer_identity_basis"] == ("part_id",)
        assert finding.evidence["peer_identity"] == ("SYNTHETIC-POWER-001",)
        assert finding.evidence["peer_symbols"] == (
            "Synthetic:PowerModuleAlias1",
            "Synthetic:PowerModuleAlias2",
        )
        assert "do not prove the nets should be common" in finding.message


def test_common_power_and_return_assignments_clear_part_id_peer_prompts() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "SYNTHETIC-POWER-001"},
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", "GND"),
    )

    report = lint_report(observed)

    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_shared_part_id_group_covers_exact_symbol_subgroups_once() -> None:
    observed = peer_power_netlist(
        references=("U1", "U2", "U3"),
        symbols={
            "U1": "Synthetic:PowerModuleA",
            "U2": "Synthetic:PowerModuleA",
            "U3": "Synthetic:PowerModuleB",
        },
        part_ids={
            "U1": "SYNTHETIC-POWER-001",
            "U2": "SYNTHETIC-POWER-001",
            "U3": "SYNTHETIC-POWER-001",
        },
        supply_nets=("+3V3", "+3V3", "+5V"),
        return_nets=("GND", "GND", "AGND"),
    )

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 2
    assert {item.evidence["peer_role"] for item in findings} == {
        ("ground/return",),
        ("supply",),
    }
    for finding in findings:
        pin_number = "1" if finding.evidence["peer_role"] == ("supply",) else "2"
        assert all(f"U{reference}.{pin_number}" in finding.evidence for reference in range(1, 4))
    assert all(item.evidence["peer_identity_basis"] == ("part_id",) for item in findings)


def test_part_id_peer_findings_are_stable_under_input_mapping_order() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "SYNTHETIC-POWER-001"}
    )
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    original_findings = [item for item in lint_report(observed).findings if item.rule_id == RULE_ID]
    reordered_findings = [
        item for item in lint_report(reordered).findings if item.rule_id == RULE_ID
    ]

    assert [(item.evidence, item.fingerprint) for item in reordered_findings] == [
        (item.evidence, item.fingerprint) for item in original_findings
    ]


@pytest.mark.parametrize(
    "changes",
    (
        pytest.param({"part_ids": {}}, id="missing-part-id"),
        pytest.param(
            {"part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-2"}},
            id="different-part-ids",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "values": {"U2": "Different value"},
            },
            id="different-values",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "footprints": {"U2": "Package:Different"},
            },
            id="different-footprints",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "incomplete_inventory": ("U2",),
            },
            id="incomplete-inventory",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "pin_functions": {"U1": ("VDD", "GND"), "U2": ("AVDD", "GND")},
            },
            id="different-pin-function",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "pin_types": {
                    "U1": ("power_in", "power_in"),
                    "U2": ("power_in", "passive"),
                },
            },
            id="different-pin-type",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "dnp": ("U2",),
            },
            id="dnp-peer",
        ),
        pytest.param(
            {
                "part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
                "supply_nets": ("+3V3", None),
                "return_nets": ("GND", "GND"),
            },
            id="open-power-pin",
        ),
    ),
)
def test_part_id_alias_comparison_requires_complete_matching_peer_identity(
    changes: dict[str, object],
) -> None:
    defaults: dict[str, object] = {"part_ids": {"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"}}
    defaults.update(changes)

    report = lint_report(peer_power_netlist(**defaults))

    assert RULE_ID not in {item.rule_id for item in report.findings}


def test_ambiguous_net_assignment_is_not_compared_as_peer_divergence() -> None:
    observed = peer_power_netlist(
        part_ids={"U1": "SYNTHETIC-1", "U2": "SYNTHETIC-1"},
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", "GND"),
        ambiguous_pins=("U2.2",),
    )

    report = lint_report(observed)

    assert RULE_ID not in {item.rule_id for item in report.findings}
