"""Review fitted-IC I2S bit-clock and serial-data same-net assignments."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.i2s_clock_data_same_net import i2s_clock_data_same_net_candidates
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract
from tests.design_lint_fixtures.i2s_clock_data_same_net import i2s_clock_data_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i2s_clock_data_same_net"


def _report(
    netlist: NetlistContract,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    project_id = "synthetic-i2s-clock-data-same-net"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=netlist,
        netlist_sha256="c" * 64,
    )
    return evaluate(
        project_id,
        coach,
        DesignLintPolicy(
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_shared_native_i2s_clock_and_data_roles_emit_review_with_exact_evidence() -> None:
    source = i2s_clock_data_netlist()
    candidates = i2s_clock_data_same_net_candidates(source)
    findings = _findings(_report(source))

    assert len(candidates) == len(findings) == 1
    finding = findings[0]
    assert finding.subject == "U1: I2S bit clock U1.1 and serial data U1.3 share I2S_SHARED"
    assert finding.evidence == {
        "component": ("U1",),
        "bit_clock_pin": ("U1.1",),
        "bit_clock_function": ("I2S_BCLK",),
        "bit_clock_electrical_type": ("passive",),
        "data_pin": ("U1.3",),
        "data_function": ("I2S_DATA",),
        "data_electrical_type": ("passive",),
        "shared_net": ("I2S_SHARED",),
    }
    assert finding.mode == "review"
    assert "do not establish that the project uses I2S" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_nets_and_bounded_data_aliases_are_controls() -> None:
    assert not i2s_clock_data_same_net_candidates(i2s_clock_data_netlist(shared=False))

    source = i2s_clock_data_netlist()
    bounded_aliases = source.model_copy(
        update={
            "pin_functions": {
                **source.pin_functions,
                "U1.1": "I2S_SCK",
                "U1.3": "I2S_DIN",
            }
        }
    )
    unrelated_sdo = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.1": "SCK", "U1.3": "SDO"}}
    )

    assert len(i2s_clock_data_same_net_candidates(bounded_aliases)) == 1
    assert not i2s_clock_data_same_net_candidates(unrelated_sdo)
    assert not _findings(_report(i2s_clock_data_netlist(shared=False)))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_duplicate_ambiguous_open_and_incomplete_endpoints_are_quiet() -> None:
    source = i2s_clock_data_netlist()
    duplicate_clock = source.model_copy(
        update={
            "component_pin_numbers": {"U1": ("1", "2", "3", "4", "5")},
            "pin_functions": {**source.pin_functions, "U1.5": "I2S_BCLK"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.5": "passive"},
            "nets": {**source.nets, "I2S_EXTRA_CLOCK": ("U1.5",)},
        }
    )
    ambiguous_clock = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.1": "I2S_BCLK_LRCLK"}}
    )
    ambiguous_clock_data_pin = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.1": "I2S_BCLK_DATA"}}
    )
    open_data = source.model_copy(
        update={
            "nets": {
                name: tuple(pin for pin in pins if pin != "U1.3")
                for name, pins in source.nets.items()
                if any(pin != "U1.3" for pin in pins)
            }
        }
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "ALT": ("U1.3",)}})
    incomplete = source.model_copy(
        update={
            "pin_electrical_types": {
                pin: kind for pin, kind in source.pin_electrical_types.items() if pin != "U1.3"
            }
        }
    )

    for case in (
        i2s_clock_data_netlist(dnp=True),
        duplicate_clock,
        ambiguous_clock,
        ambiguous_clock_data_pin,
        open_data,
        multiply_assigned,
        incomplete,
    ):
        assert not i2s_clock_data_same_net_candidates(case)
        assert not _findings(_report(case))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_native_output_types_remain_with_erc_but_one_output_is_reviewed() -> None:
    source = i2s_clock_data_netlist()
    both_outputs = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.1": "output",
                "U1.3": "output",
            }
        }
    )
    one_output = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.1": "output",
                "U1.3": "input",
            }
        }
    )

    assert not i2s_clock_data_same_net_candidates(both_outputs)
    assert not _findings(_report(both_outputs))
    assert len(_findings(_report(one_output))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_candidate() -> None:
    source = i2s_clock_data_netlist()
    finding = _findings(_report(source))[0]
    blocked = _report(
        source,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic reviewed I2S interface requirement",
        ),
    )
    disabled = _report(
        source,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic intentional shared-pin operating mode",
        ),
    )
    ignored = _report(
        source,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic reviewed alternate function",
        ),
    )

    assert _findings(blocked)[0].mode == "block"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_keeps_fingerprint_and_evidence_stable() -> None:
    source = i2s_clock_data_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "components": dict(reversed(tuple(source.components.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    first = _findings(_report(source))[0]
    second = _findings(_report(reordered))[0]

    assert second.fingerprint == first.fingerprint
    assert second.evidence == first.evidence
