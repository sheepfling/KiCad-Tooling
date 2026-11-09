"""Review native SWDIO and SWCLK roles that share one net."""

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
from kicad_tooling.hwrepo.models import ContractCoachReport, NetlistContract
from kicad_tooling.hwrepo.swd_endpoint_inventory import swd_function_role
from kicad_tooling.hwrepo.swd_same_net import swdio_swclk_same_net_candidates
from tests.design_lint_fixtures.swd_signal_same_net import swd_signal_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.swdio_swclk_same_net"


def _report(
    netlist: NetlistContract,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    project_id = "synthetic-swd-signal-same-net"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=netlist,
        netlist_sha256="a" * 64,
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
def test_unique_native_swd_pair_on_one_net_emits_review_with_exact_evidence() -> None:
    source = swd_signal_same_net_netlist()
    candidates = swdio_swclk_same_net_candidates(source)
    findings = _findings(_report(source))

    assert len(candidates) == len(findings) == 1
    finding = findings[0]
    assert finding.subject == "U1: SWDIO U1.5 and SWCLK U1.6 share SWD_SHARED"
    assert finding.evidence == {
        "component": ("U1",),
        "SWDIO_pin": ("U1.5",),
        "SWDIO_function": ("SYS_JTMS-SWDIO",),
        "SWDIO_electrical_type": ("passive",),
        "SWCLK_pin": ("U1.6",),
        "SWCLK_function": ("SYS_JTCK-SWCLK",),
        "SWCLK_electrical_type": ("passive",),
        "shared_net": ("SWD_SHARED",),
    }
    assert finding.mode == "review"
    assert "do not establish that this SWD interface is used" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_nets_and_historical_clock_alias_are_supported_controls() -> None:
    assert swd_function_role("SYS_JTMS-SWDIO") == "swdio"
    assert swd_function_role("SYS_JTCK-SWCLK") == "swclk"
    assert swd_function_role("SWDCLK") == "swclk"
    assert swd_function_role("GPIO_SWDIO") == "swdio"
    assert swd_function_role("JTCK") is None
    assert swd_function_role("GPIO_SWDIO_SWDCLK") is None

    assert not swdio_swclk_same_net_candidates(swd_signal_same_net_netlist(shared=False))
    assert not _findings(_report(swd_signal_same_net_netlist(shared=False)))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_duplicate_open_ambiguous_and_incomplete_endpoints_are_skipped() -> None:
    source = swd_signal_same_net_netlist()
    duplicate_role = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.4": "SWDIO"}}
    )
    open_clock = source.model_copy(
        update={
            "nets": {
                name: tuple(pin for pin in pins if pin != "U1.6")
                for name, pins in source.nets.items()
                if any(pin != "U1.6" for pin in pins)
            }
        }
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "ALT": ("U1.6",)}})
    incomplete = source.model_copy(
        update={
            "pin_electrical_types": {
                pin: kind for pin, kind in source.pin_electrical_types.items() if pin != "U1.6"
            }
        }
    )

    for case in (
        swd_signal_same_net_netlist(dnp=True),
        duplicate_role,
        open_clock,
        multiply_assigned,
        incomplete,
    ):
        assert not swdio_swclk_same_net_candidates(case)
        assert not _findings(_report(case))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_native_output_types_remain_with_erc_but_one_output_is_reviewed() -> None:
    source = swd_signal_same_net_netlist()
    both_outputs = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.5": "output",
                "U1.6": "output",
            }
        }
    )
    one_output = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.5": "output",
                "U1.6": "input",
            }
        }
    )

    assert not swdio_swclk_same_net_candidates(both_outputs)
    assert not _findings(_report(both_outputs))
    assert len(_findings(_report(one_output))) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_policy_can_block_disable_or_exactly_ignore_candidate() -> None:
    source = swd_signal_same_net_netlist()
    finding = _findings(_report(source))[0]
    blocked = _report(
        source,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic project requirement review",
        ),
    )
    ignored = _report(
        source,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic reviewed debug interface",
        ),
    )
    assert _findings(blocked)[0].mode == "block"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_keeps_fingerprint_and_evidence_stable() -> None:
    source = swd_signal_same_net_netlist()
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
