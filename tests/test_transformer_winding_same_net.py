"""Synthetic regressions for review of a same-net transformer winding."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_component_transformers import (
    transformer_winding_groups_share_net_candidates,
    transformer_winding_same_net_candidates,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.transformer_winding_same_net"
GROUP_BRIDGE_RULE_ID = "component.transformer_winding_groups_share_net"
SYMBOL = "Transformer:TRANSF1"


def transformer_netlist(
    *,
    first_winding_same_net: bool = True,
    second_winding_same_net: bool = False,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    extra_pin: tuple[str, ...] = (),
    shared_winding_groups: bool = False,
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"T1": SYMBOL}
    components = {
        reference: ComponentContract(value="Synthetic 1:1 transformer", footprint="Synthetic:T")
        for reference in symbols
    }
    pin_numbers = {
        reference: ("1", "2", "3", "4", "5") if reference in extra_pin else ("1", "2", "3", "4")
        for reference in symbols
        if reference not in omit_inventory
    }
    nets: dict[str, tuple[str, ...]] = {}
    for reference in symbols:
        if reference in dnp or reference in omit_inventory:
            continue
        if shared_winding_groups:
            nets[f"WINDING_GROUPS_SHARED_{reference}"] = (
                f"{reference}.1",
                f"{reference}.3",
            )
            for number in ("2", "4"):
                if f"{reference}.{number}" not in open_pins:
                    nets[f"WINDING_{number}_{reference}"] = (f"{reference}.{number}",)
        else:
            for winding, numbers, tied in (
                ("WINDING_1", ("1", "2"), first_winding_same_net),
                ("WINDING_2", ("3", "4"), second_winding_same_net),
            ):
                if tied:
                    pins = tuple(f"{reference}.{number}" for number in numbers)
                    nets[f"{winding}_{reference}_TIED"] = pins
                else:
                    for number in numbers:
                        if f"{reference}.{number}" not in open_pins:
                            nets[f"{winding}_{reference}_{number}"] = (f"{reference}.{number}",)
        if reference in extra_pin:
            nets[f"EXTRA_{reference}"] = (f"{reference}.5",)
        if reference in ambiguous:
            nets[f"ALSO_{reference}"] = (f"{reference}.2",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint_report(observed: NetlistContract, policy: DesignLintPolicy | None = None) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-transformer-winding-review",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_supported_transformer_winding_is_reviewed() -> None:
    observed = transformer_netlist()
    candidates = transformer_winding_same_net_candidates(observed)
    assert len(candidates) == 1
    assert candidates[0].subject == "T1: winding 1 pins 1/2 share WINDING_1_T1_TIED"

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].evidence["symbol"] == (SYMBOL,)
    assert findings[0].evidence["winding"] == ("winding_1",)
    assert findings[0].evidence["pin_assignments"] == (
        "T1.1 -> WINDING_1_T1_TIED",
        "T1.2 -> WINDING_1_T1_TIED",
    )
    assert "does not establish transformer operation" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_winding_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(transformer_netlist(first_winding_same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_extra_pin_and_unconfirmed_symbols() -> None:
    cases = (
        transformer_netlist(dnp=("T1",)),
        transformer_netlist(omit_inventory=("T1",)),
        transformer_netlist(ambiguous=("T1",)),
        transformer_netlist(first_winding_same_net=False, open_pins=("T1.2",)),
        transformer_netlist(extra_pin=("T1",)),
        transformer_netlist(symbols={"T1": "Transformer:TRANSF2"}),
        transformer_netlist(symbols={"T1": "Vendor:TRANSF1"}),
    )
    for observed in cases:
        assert transformer_winding_same_net_candidates(observed) == ()
        assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_project_configurable() -> None:
    observed = transformer_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires disposition of a tied winding",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project intentionally disables it",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewer accepts this intentional winding short",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_one_winding_clears_only_its_finding() -> None:
    source = transformer_netlist(first_winding_same_net=True, second_winding_same_net=True)
    original = lint_report(source)
    reordered = lint_report(
        source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
    )
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }
    assert len(original_findings) == 2
    assert reordered_findings == original_findings

    repaired = lint_report(
        transformer_netlist(first_winding_same_net=False, second_winding_same_net=True)
    )
    assert [item.subject for item in repaired.findings if item.rule_id == RULE_ID] == [
        "T1: winding 2 pins 3/4 share WINDING_2_T1_TIED"
    ]


@pytest.mark.design_lint_rule(rule_id=GROUP_BRIDGE_RULE_ID)
def test_cross_winding_shared_net_is_reviewed_with_exact_pin_evidence() -> None:
    observed = transformer_netlist(
        first_winding_same_net=False,
        shared_winding_groups=True,
    )
    candidates = transformer_winding_groups_share_net_candidates(observed)
    assert len(candidates) == 1
    assert candidates[0].subject == "T1: winding groups share WINDING_GROUPS_SHARED_T1"

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == GROUP_BRIDGE_RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].evidence["symbol"] == (SYMBOL,)
    assert findings[0].evidence["shared_net"] == ("WINDING_GROUPS_SHARED_T1",)
    assert findings[0].evidence["first_winding_pins"] == ("T1.1",)
    assert findings[0].evidence["second_winding_pins"] == ("T1.3",)
    assert "not isolated in the netlist" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=GROUP_BRIDGE_RULE_ID)
def test_distinct_winding_groups_are_the_no_finding_control() -> None:
    observed = transformer_netlist(first_winding_same_net=False)
    assert transformer_winding_groups_share_net_candidates(observed) == ()
    assert GROUP_BRIDGE_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.design_lint_rule(rule_id=GROUP_BRIDGE_RULE_ID)
def test_cross_winding_review_policy_and_exact_ignore_are_project_configurable() -> None:
    observed = transformer_netlist(
        first_winding_same_net=False,
        shared_winding_groups=True,
    )
    finding = next(
        item for item in lint_report(observed).findings if item.rule_id == GROUP_BRIDGE_RULE_ID
    )
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=GROUP_BRIDGE_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires disposition of this cross-winding net",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=GROUP_BRIDGE_RULE_ID,
                    mode="off",
                    reason="Synthetic project intentionally shares these transformer groups",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=GROUP_BRIDGE_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewer accepts the intentional shared net",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=GROUP_BRIDGE_RULE_ID)
def test_cross_winding_review_is_order_stable_and_clears_when_net_is_split() -> None:
    source = transformer_netlist(
        first_winding_same_net=False,
        shared_winding_groups=True,
    )
    original = lint_report(source)
    reordered = lint_report(
        source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
    )
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == GROUP_BRIDGE_RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == GROUP_BRIDGE_RULE_ID
    }
    assert original_findings == reordered_findings
    assert len(original_findings) == 1

    repaired = lint_report(transformer_netlist(first_winding_same_net=False))
    assert GROUP_BRIDGE_RULE_ID not in {item.rule_id for item in repaired.findings}


@pytest.mark.design_lint_rule(rule_id=GROUP_BRIDGE_RULE_ID)
def test_cross_winding_review_skips_dnp_incomplete_ambiguous_open_extra_and_unknown() -> None:
    cases = (
        transformer_netlist(dnp=("T1",), shared_winding_groups=True),
        transformer_netlist(omit_inventory=("T1",), shared_winding_groups=True),
        transformer_netlist(ambiguous=("T1",), shared_winding_groups=True),
        transformer_netlist(open_pins=("T1.4",), shared_winding_groups=True),
        transformer_netlist(extra_pin=("T1",), shared_winding_groups=True),
        transformer_netlist(symbols={"T1": "Transformer:TRANSF2"}, shared_winding_groups=True),
    )
    for observed in cases:
        assert transformer_winding_groups_share_net_candidates(observed) == ()
        assert GROUP_BRIDGE_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}
