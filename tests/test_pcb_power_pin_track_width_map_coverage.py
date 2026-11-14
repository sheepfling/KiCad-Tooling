"""Review native power-pin nets missing authored track-width map coverage."""

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
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.pcb_power_pin_track_width_coverage import (
    RULE_ID,
    power_pin_net_track_width_map_candidates,
)
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthMap
from kicad_tooling.hwrepo.project_models import ProjectKind
from tests.design_lint_fixtures.pcb_power_pin_track_width import (
    native_power_netlist,
    power_track_width_map,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.power_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _candidates(
    *,
    observed: NetlistContract | None = None,
    project_kind: ProjectKind | None = ProjectKind.PCB,
    track_width_map: PcbTrackWidthMap | None = None,
    netlist_sha256: str | None = "a" * 64,
):
    return power_pin_net_track_width_map_candidates(
        observed or native_power_netlist(), project_kind, track_width_map, netlist_sha256
    )


def _report(policy: DesignLintPolicy, candidates):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-power-width-map",
        project_kind=ProjectKind.PCB,
        netlist_sha256="a" * 64,
        observed=native_power_netlist(),
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


def test_unmapped_fitted_power_pin_nets_prompt_with_exact_native_evidence() -> None:
    candidates = _candidates()

    assert tuple(item.evidence["net"] for item in candidates) == (("INPUT",), ("RETURN",))
    assert candidates[0].evidence["power_pin_assignments"] == (
        "U1.1: function=VIN; type=power_in; footprint=Synthetic:QFN",
    )
    assert candidates[1].evidence["power_pin_assignments"] == (
        "U1.4: function=GND; type=power_in; footprint=Synthetic:QFN",
    )
    assert all(item.evidence["netlist_sha256"] == ("a" * 64,) for item in candidates)
    assert all(item.evidence["track_width_map_sha256"] == ("absent",) for item in candidates)
    assert all("does not estimate current" in item.message for item in candidates)


def test_exact_map_covers_only_listed_power_nets_and_wildcard_covers_all() -> None:
    (unmapped_return,) = _candidates(track_width_map=power_track_width_map("input"))
    assert unmapped_return.evidence["net"] == ("RETURN",)
    assert unmapped_return.evidence["track_width_map_sha256"] != ("absent",)

    assert _candidates(track_width_map=power_track_width_map("INPUT", "RETURN")) == ()
    assert _candidates(track_width_map=power_track_width_map("*")) == ()


@pytest.mark.parametrize(
    "observed",
    (
        native_power_netlist().model_copy(update={"dnp_components": ("U1",)}),
        native_power_netlist().model_copy(
            update={
                "components": {
                    "U1": native_power_netlist()
                    .components["U1"]
                    .model_copy(update={"footprint": ""})
                }
            }
        ),
        native_power_netlist().model_copy(update={"component_pin_numbers": {"U1": ("2", "3")}}),
        native_power_netlist().model_copy(
            update={"pin_electrical_types": {"U1.1": "passive", "U1.4": "passive"}}
        ),
        native_power_netlist().model_copy(
            update={"pin_electrical_types": {"U1.1": "power_in", "u1.1": "passive"}}
        ),
        native_power_netlist().model_copy(
            update={"nets": {"INPUT": ("U1.1",), "input": ("U1.1",)}}
        ),
    ),
    ids=(
        "dnp",
        "no-footprint",
        "pin-not-in-inventory",
        "non-power-types",
        "ambiguous-pin-type",
        "ambiguous-net-name",
    ),
)
def test_ineligible_or_ambiguous_native_assignments_stay_quiet(
    observed: NetlistContract,
) -> None:
    assert _candidates(observed=observed) == ()


def test_only_pcb_project_kinds_and_bound_netlists_are_reviewed() -> None:
    assert _candidates(project_kind=ProjectKind.SCHEMATIC) == ()
    assert _candidates(project_kind=ProjectKind.SYSTEM_WIRING) == ()
    assert _candidates(netlist_sha256=None) == ()


def test_candidate_order_and_fingerprint_ignore_native_net_mapping_order() -> None:
    original = _candidates()
    observed = native_power_netlist()
    reordered = observed.model_copy(update={"nets": dict(reversed(tuple(observed.nets.items())))})
    repeated = _candidates(observed=reordered)

    assert original == repeated
    assert tuple(map(fingerprint, original)) == tuple(map(fingerprint, repeated))


def test_rule_is_default_off_and_supports_review_block_and_exact_ignore() -> None:
    candidate = _candidates()[0]
    default = _report(DesignLintPolicy(), (candidate,))
    reviewed = _report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Review width scope"),
            )
        ),
        (candidate,),
    )
    blocked = _report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Gate width scope"),
            )
        ),
        (candidate,),
    )
    ignored = _report(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Review width scope"),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=fingerprint(candidate),
                    reason="Synthetic exact-map exception",
                ),
            ),
        ),
        (candidate,),
    )

    baseline = _report(DesignLintPolicy(), ())
    (default_finding,) = tuple(item for item in default.findings if item.rule_id == RULE_ID)
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert default.status == baseline.status
    (reviewed_finding,) = tuple(item for item in reviewed.findings if item.rule_id == RULE_ID)
    assert reviewed_finding.mode == "review"
    assert reviewed.status == "REVIEW"
    assert blocked.status == "FAIL"
    (ignored_finding,) = tuple(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
