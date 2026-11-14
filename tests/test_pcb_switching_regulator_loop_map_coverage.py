"""Default-off source review for unmapped switching-regulator pads."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_component_coverage import ComponentMapCoverageInputs
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate_request
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import ProjectKind
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_switching_loop_map_coverage import (
    RULE_ID,
    switching_regulator_loop_map_candidates,
)
from kicad_tooling.hwrepo.pcb_switching_loop_models import PcbSwitchingLoopMap
from tests.design_lint_fixtures.pcb_switching_regulator_loop_map import (
    loop_map,
    regulator_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.switching_regulator_loop_map_coverage"),
    pytest.mark.pcb_lint,
    pytest.mark.power_lint,
]


def _candidates(
    *,
    observed: NetlistContract | None = None,
    project_kind: ProjectKind | None = ProjectKind.PCB,
    authored_map: PcbSwitchingLoopMap | None = None,
):
    return switching_regulator_loop_map_candidates(
        observed or regulator_netlist(),
        project_kind,
        authored_map,
        "a" * 64,
    )


def _report(policy: DesignLintPolicy, candidates: tuple[Candidate, ...]):
    observed = regulator_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-switching-regulator",
        project_kind=ProjectKind.PCB,
        netlist_sha256="a" * 64,
        observed=observed,
    )
    return evaluate_request(
        DesignLintEvaluationRequest(
            project_id=coach.project_id,
            coach=coach,
            policy=policy,
            component_map_coverage=ComponentMapCoverageInputs(),
            pcb_source_candidates=tuple(candidates),
        )
    )


def test_unmapped_fitted_switching_regulator_prompts_with_exact_pad_evidence() -> None:
    (candidate,) = _candidates()

    assert candidate.rule_id == RULE_ID
    assert candidate.evidence["component_symbol"] == ("Regulator_Switching:SyntheticBuck",)
    assert candidate.evidence["switch_node_pins"] == ("U1.2", "U1.3")
    assert candidate.evidence["unmapped_switch_node_pins"] == ("U1.2", "U1.3")
    assert candidate.evidence["switch_node_nets"] == (
        "U1.2 -> SWITCH_A",
        "U1.3 -> SWITCH_B",
    )
    assert "does not assert a defect" in candidate.message


def test_partial_and_complete_maps_report_only_unmapped_switch_pads() -> None:
    (partial,) = _candidates(authored_map=loop_map(("U1.2",)))
    assert partial.evidence["mapped_switch_node_pins"] == ("U1.2",)
    assert partial.evidence["unmapped_switch_node_pins"] == ("U1.3",)
    assert _candidates(authored_map=loop_map(("U1.2", "U1.3"))) == ()


@pytest.mark.parametrize(
    "observed",
    (
        regulator_netlist(symbol="Device:SyntheticBuck"),
        regulator_netlist(dnp=True),
        regulator_netlist(footprint=""),
        regulator_netlist(missing_function_pin="U1.4"),
        regulator_netlist(missing_type_pin="U1.4"),
        regulator_netlist(open_switch_pin="U1.3"),
        regulator_netlist(ambiguous_switch_pin="U1.2"),
        regulator_netlist(missing_function_pin="U1.2"),
        regulator_netlist(function_overrides={"U1.2": "SW_NODE", "U1.3": "BOOTSTRAP"}),
    ),
    ids=(
        "other-symbol-library",
        "dnp",
        "missing-footprint",
        "incomplete-function-inventory",
        "incomplete-electrical-type-inventory",
        "open-switch-node",
        "multiply-assigned-switch-node",
        "unidentified-switch-function",
        "unbounded-switch-node-aliases",
    ),
)
def test_ambiguous_or_out_of_scope_symbol_data_stays_quiet(observed: NetlistContract) -> None:
    assert _candidates(observed=observed) == ()


@pytest.mark.parametrize("project_kind", (None, ProjectKind.SCHEMATIC, ProjectKind.SYSTEM_WIRING))
def test_non_pcb_project_kinds_stay_quiet(project_kind: ProjectKind | None) -> None:
    assert _candidates(project_kind=project_kind) == ()


def test_candidate_order_and_fingerprint_ignore_native_mapping_order() -> None:
    original = _candidates()[0]
    netlist = regulator_netlist()
    reordered = netlist.model_copy(update={"nets": dict(reversed(tuple(netlist.nets.items())))})
    repeated = _candidates(observed=reordered)[0]

    assert original == repeated
    assert fingerprint(original) == fingerprint(repeated)


def test_rule_policy_defaults_off_and_supports_review_block_off_and_exact_ignore() -> None:
    candidate = _candidates()[0]
    disabled = _report(DesignLintPolicy(), (candidate,))
    reviewed = _report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic review opt-in",
                ),
            )
        ),
        (candidate,),
    )
    blocked = _report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic release gate opt-in",
                ),
            )
        ),
        (candidate,),
    )
    exact_ignore = _report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic review opt-in",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="Synthetic reviewed exception",
                ),
            ),
        ),
        (candidate,),
    )

    (disabled_finding,) = (item for item in disabled.findings if item.rule_id == RULE_ID)
    assert disabled_finding.disposition == "RULE_OFF"
    assert next(item for item in reviewed.findings if item.rule_id == RULE_ID).mode == "review"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    (ignored,) = (item for item in exact_ignore.findings if item.rule_id == RULE_ID)
    assert ignored.disposition == "IGNORED"
