"""Focused synthetic regressions for the named pairs lint theme."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
    PcbDifferentialPairRuleMap,
    PcbDifferentialPairRuleRequirement,
    PcbDrcMinMaxRequirement,
)
from tests.design_lint_fixtures import (
    coach,
    complementary_usb_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_named_complementary_nets_prompt_for_reviewed_pair_requirements() -> None:
    source = complementary_usb_netlist()
    default = evaluate("synthetic-usb-pair", coach(source), DesignLintPolicy())
    assert default.status == "REVIEW"
    finding = next(
        item
        for item in default.findings
        if item.rule_id == "signal.named_pair_without_reviewed_requirement"
    )
    assert finding.subject == "USB_DP / USB_DM"
    assert finding.evidence["naming_pattern"] == ("_DP/_DM",)
    assert finding.evidence["positive_references"] == ("J1.1",)
    assert "does not establish pair intent" in finding.message

    plus_minus_sources = (
        NetlistContract(
            components={},
            nets={"USB_D+": ("J1.1",), "USB_D-": ("J1.2",)},
        ),
        NetlistContract(
            components={
                "R1": ComponentContract(value="22R", footprint=""),
                "R2": ComponentContract(value="22R", footprint=""),
            },
            nets={
                "USB_D+": ("J1.1", "R1.1"),
                "USB_DP_PHY": ("R1.2",),
                "USB_D-": ("J1.2", "R2.1"),
                "USB_DM_PHY": ("R2.2",),
            },
            component_symbols={
                "J1": "Connector:USB_A",
                "R1": "Device:R",
                "R2": "Device:R",
            },
            pin_functions={
                "J1.1": "D+",
                "J1.2": "D-",
                "R1.1": "1",
                "R1.2": "2",
                "R2.1": "1",
                "R2.2": "2",
            },
            component_pin_numbers={
                "J1": ("1", "2"),
                "R1": ("1", "2"),
                "R2": ("1", "2"),
            },
        ),
    )
    for index, plus_minus_source in enumerate(plus_minus_sources):
        plus_minus_report = evaluate(
            f"synthetic-usb-plus-minus-{index}",
            coach(plus_minus_source),
            DesignLintPolicy(),
        )
        plus_minus_finding = next(
            item
            for item in plus_minus_report.findings
            if item.rule_id == "signal.named_pair_without_reviewed_requirement"
        )
        assert plus_minus_finding.subject == "USB_D+ / USB_D-"

    requirement_map = PcbDifferentialPairRuleMap(
        basis="Synthetic reviewed interface requirement",
        requirements=(
            PcbDifferentialPairRuleRequirement(
                id="usb-data",
                basis="Synthetic pair geometry requirement",
                positive_net="USB_DP",
                negative_net="USB_DM",
                pair_selector="USB_",
                track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
            ),
        ),
    )
    assert not any(
        item.rule_id == "signal.named_pair_without_reviewed_requirement"
        for item in candidates(source, pcb_differential_pair_rule_map=requirement_map)
    )

    blocking = evaluate(
        "synthetic-usb-pair",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="signal.named_pair_without_reviewed_requirement",
                    mode="block",
                    reason="Review every named complementary net pair",
                ),
            )
        ),
    )
    assert blocking.status == "FAIL"

    disabled = evaluate(
        "synthetic-usb-pair",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="signal.named_pair_without_reviewed_requirement",
                    mode="off",
                    reason="This project tracks pair limits in a separate review record",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    off_finding = next(
        item
        for item in disabled.findings
        if item.rule_id == "signal.named_pair_without_reviewed_requirement"
    )
    assert off_finding.disposition == "RULE_OFF"

    ignored = evaluate(
        "synthetic-usb-pair",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="The synthetic low-speed pair has a reviewed exception",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    ignored_finding = next(
        item
        for item in ignored.findings
        if item.rule_id == "signal.named_pair_without_reviewed_requirement"
    )
    assert ignored_finding.disposition == "IGNORED"

    assert not any(
        item.rule_id == "signal.named_pair_without_reviewed_requirement"
        for item in candidates(
            NetlistContract(
                components={},
                nets={"VIP": ("U1.1",), "VIN": ("U1.2",)},
            )
        )
    )


def test_named_pair_hint_is_stable_and_reviewed_map_suppresses_only_the_hint() -> None:
    rule_id = "signal.named_pair_without_reviewed_requirement"
    source = complementary_usb_netlist()
    requirements = (
        PcbDifferentialPairRuleRequirement(
            id="usb-data",
            basis="Synthetic USB pair geometry requirement",
            positive_net="USB_DP",
            negative_net="USB_DM",
            pair_selector="USB_",
            track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
        ),
        PcbDifferentialPairRuleRequirement(
            id="can-data",
            basis="Synthetic CAN pair geometry requirement",
            positive_net="CANH",
            negative_net="CANL",
            pair_selector="CAN",
            track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
        ),
    )
    requirement_map = PcbDifferentialPairRuleMap(
        basis="Synthetic reviewed interface requirements",
        requirements=requirements,
    )
    reordered_map = requirement_map.model_copy(
        update={"requirements": tuple(reversed(requirement_map.requirements))}
    )

    def lint(
        netlist: NetlistContract,
        pair_map: PcbDifferentialPairRuleMap | None = None,
    ) -> tuple[str, DesignLintReport]:
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        report = evaluate(
            "synthetic-usb-pair",
            coach(netlist, source_hash),
            DesignLintPolicy(pcb_differential_pair_rule_map=pair_map),
        )
        return source_hash, report

    source_hash, original = lint(source)
    original_finding = next(item for item in original.findings if item.rule_id == rule_id)
    reordered_source = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    reordered_hash, reordered = lint(reordered_source)
    reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
    assert source_hash != reordered_hash
    assert original.netlist_sha256 == source_hash
    assert reordered.netlist_sha256 == reordered_hash
    assert (
        reordered_finding.subject,
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    ) == (original_finding.subject, original_finding.fingerprint, original_finding.evidence)

    reviewed_hash, reviewed = lint(source, requirement_map)
    reviewed_coverage = reviewed.pcb_differential_pair_rules
    expected_map_hash = hashlib.sha256(
        requirement_map.model_dump_json().encode("utf-8")
    ).hexdigest()
    assert reviewed.netlist_sha256 == reviewed_hash
    assert rule_id not in {item.rule_id for item in reviewed.findings}
    assert reviewed_coverage.status == "BLOCKED"
    assert reviewed_coverage.map_sha256 == expected_map_hash
    assert "native DRC rule evidence was not supplied" in (reviewed_coverage.issue or "")

    reordered_source_hash, reordered_reviewed = lint(reordered_source, reordered_map)
    reordered_map_hash = hashlib.sha256(reordered_map.model_dump_json().encode("utf-8")).hexdigest()
    assert reordered_reviewed.netlist_sha256 == reordered_source_hash
    assert expected_map_hash != reordered_map_hash
    assert rule_id not in {item.rule_id for item in reordered_reviewed.findings}
    assert reordered_reviewed.pcb_differential_pair_rules.map_sha256 == reordered_map_hash

    unavailable = ContractCoachReport(
        status="BLOCKED",
        project_id="synthetic-ports",
        issues=("Synthetic native evidence unavailable",),
    )
    unavailable_report = evaluate(
        "synthetic-usb-pair",
        unavailable,
        DesignLintPolicy(pcb_differential_pair_rule_map=requirement_map),
    )
    assert unavailable_report.status == "BLOCKED"
    assert unavailable_report.pcb_differential_pair_rules.status == "BLOCKED"
    assert unavailable_report.pcb_differential_pair_rules.map_sha256 == expected_map_hash

    disabled_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.differential_pair_rule_coverage",
                mode="off",
                reason="Synthetic control for the explicit pair-map lifecycle",
            ),
        ),
        pcb_differential_pair_rule_map=requirement_map,
    )
    disabled = evaluate(
        "synthetic-usb-pair",
        coach(source),
        disabled_policy,
    )
    assert disabled.pcb_differential_pair_rules.status == "DISABLED"
    assert disabled.pcb_differential_pair_rules.map_sha256 == expected_map_hash

    unavailable_disabled = evaluate("synthetic-usb-pair", unavailable, disabled_policy)
    assert unavailable_disabled.pcb_differential_pair_rules.status == "DISABLED"
    assert unavailable_disabled.pcb_differential_pair_rules.map_sha256 == expected_map_hash
