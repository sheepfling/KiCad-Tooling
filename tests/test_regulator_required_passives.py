"""Regressions for project-authored regulator passive topology checks."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_power_regulator_passives import (
    regulator_required_passive_candidates,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.regulator_passive_models import (
    RegulatorPassiveComponentRequirement,
    RegulatorPassivePinRequirement,
    RegulatorPassiveTopologyAlternative,
    RegulatorPassiveTopologyMap,
    RegulatorPassiveTopologyRequirement,
    RegulatorRequiredPassive,
)
from tests.test_regulator_feedback import regulator_feedback_map, regulator_netlist
from tests.test_regulator_feedback import report as feedback_report

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

RULE_ID = "power.regulator_required_passive_topology_mismatch"


def topology_map(*, include_alternative: bool = False) -> RegulatorPassiveTopologyMap:
    return RegulatorPassiveTopologyMap(
        basis="Synthetic reviewed regulator application schematic",
        requirements=(
            RegulatorPassiveTopologyRequirement(
                id="main-regulator",
                basis="Synthetic reviewed compensation topology",
                regulator=RegulatorPassiveComponentRequirement(
                    reference="U1",
                    value="SYNTH-ADJ",
                    symbol="Synthetic:AdjustableRegulator",
                    footprint="Synthetic:SOIC-8",
                    pins=(
                        RegulatorPassivePinRequirement(pin="U1.1", net="REG_OUT"),
                        RegulatorPassivePinRequirement(pin="U1.2", net="FB"),
                        RegulatorPassivePinRequirement(pin="U1.3", net="VIN"),
                        RegulatorPassivePinRequirement(pin="U1.4", net="GND"),
                        *(
                            RegulatorPassivePinRequirement(pin=f"U1.{pin}", net=None)
                            for pin in range(5, 9)
                        ),
                    ),
                ),
                required_passives=(
                    RegulatorRequiredPassive(
                        role="feedback-compensation",
                        component=RegulatorPassiveComponentRequirement(
                            reference="C1",
                            value="100pF",
                            symbol="Device:C",
                            footprint="Synthetic:0603",
                            pins=(
                                RegulatorPassivePinRequirement(pin="C1.1", net="REG_OUT"),
                                RegulatorPassivePinRequirement(pin="C1.2", net="FB"),
                            ),
                        ),
                    ),
                ),
                approved_alternatives=(
                    (
                        RegulatorPassiveTopologyAlternative(
                            id="alternate-compensation",
                            basis="Synthetic reviewed alternate compensation population",
                            required_passives=(
                                RegulatorRequiredPassive(
                                    role="feedback-compensation",
                                    component=RegulatorPassiveComponentRequirement(
                                        reference="C2",
                                        value="10pF",
                                        symbol="Device:C",
                                        footprint="Synthetic:0603",
                                        pins=(
                                            RegulatorPassivePinRequirement(
                                                pin="C2.1", net="REG_OUT"
                                            ),
                                            RegulatorPassivePinRequirement(pin="C2.2", net="FB"),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    )
                    if include_alternative
                    else ()
                ),
            ),
        ),
    )


def lint(netlist, *, mode: str | None = None):
    policy = DesignLintPolicy(
        regulator_passive_topology_map=topology_map(),
        rules=()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic policy exercise",
            ),
        ),
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-regulator",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate("synthetic-regulator", coach, policy)


def catalog_reachable_rule_ids() -> set[str]:
    return {
        item.rule_id
        for item in regulator_required_passive_candidates(regulator_netlist(), topology_map())
    }


def with_alternate_passive(source):
    components = dict(source.components)
    components["C2"] = ComponentContract(value="10pF", footprint="Synthetic:0603")
    nets = dict(source.nets)
    nets["REG_OUT"] = (*nets["REG_OUT"], "C2.1")
    nets["FB"] = (*nets["FB"], "C2.2")
    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": {**source.component_symbols, "C2": "Device:C"},
            "component_pin_numbers": {**source.component_pin_numbers, "C2": ("1", "2")},
        }
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_missing_required_compensation_passive_is_reviewed() -> None:
    source = regulator_netlist()
    baseline = feedback_report(source, regulator_feedback_map())
    assert not any(
        item.rule_id == "power.regulator_feedback_mismatch" for item in baseline.findings
    )
    result = lint(source)
    finding = next(item for item in result.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"
    assert "C1 is absent" in finding.message
    assert "not verified by this check" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_present_topology_is_a_valid_control() -> None:
    report = lint(regulator_netlist(with_compensation_capacitor=True))
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicitly_approved_alternative_topology_is_a_valid_control() -> None:
    alternate = with_alternate_passive(regulator_netlist())
    dnp_primary = with_alternate_passive(
        regulator_netlist(with_compensation_capacitor=True)
    ).model_copy(update={"dnp_components": ("C1",)})
    report = evaluate(
        "synthetic-regulator",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator",
            observed=alternate,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(regulator_passive_topology_map=topology_map(include_alternative=True)),
    )
    assert not any(item.rule_id == RULE_ID for item in report.findings)
    dnp_report = evaluate(
        "synthetic-regulator",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator",
            observed=dnp_primary,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(regulator_passive_topology_map=topology_map(include_alternative=True)),
    )
    assert not any(item.rule_id == RULE_ID for item in dnp_report.findings)

    mixed = with_alternate_passive(regulator_netlist(with_compensation_capacitor=True))
    mixed_report = evaluate(
        "synthetic-regulator",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-regulator",
            observed=mixed,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(regulator_passive_topology_map=topology_map(include_alternative=True)),
    )
    assert any(item.rule_id == RULE_ID for item in mixed_report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_or_wrong_net_required_passive_is_reported_and_can_block() -> None:
    source = regulator_netlist(with_compensation_capacitor=True)
    dnp_source = source.model_copy(update={"dnp_components": ("C1",)})
    wrong_net_source = source.model_copy(
        update={
            "nets": {
                **source.nets,
                "REG_OUT": tuple(pin for pin in source.nets["REG_OUT"] if pin != "C1.1"),
                "OTHER": ("C1.1",),
            }
        }
    )
    assert any(item.rule_id == RULE_ID for item in lint(dnp_source).findings)
    blocked = lint(wrong_net_source, mode="block")
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    disabled = lint(wrong_net_source, mode="off")
    finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert finding.disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_output_is_order_stable() -> None:
    source = regulator_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
        }
    )
    assert lint(source).findings == lint(reordered).findings
