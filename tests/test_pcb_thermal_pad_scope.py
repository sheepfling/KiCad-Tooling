"""Exact exported pin-function prompts for unmapped exposed pads."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import scan_candidates
from kicad_tooling.hwrepo.design_lint_pcb_thermal_pad_scope import (
    explicit_thermal_pad_scope_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_thermal_pad_scope_evidence import (
    PcbExplicitThermalPadScopeCandidate,
)
from kicad_tooling.hwrepo.design_lint_policy_models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.project_models import ProjectKind
from tests.design_lint_candidate_inputs_support import candidate_inputs
from tests.design_lint_fixtures import coach
from tests.pcb_thermal_vias_support import mapping, requirement

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def observed_netlist() -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Controller", footprint="Synthetic:QFN"),
            "U2": ComponentContract(value="Regulator", footprint="Synthetic:DFN"),
            "U3": ComponentContract(value="DNP controller", footprint="Synthetic:QFN"),
            "U4": ComponentContract(value="Unassigned controller", footprint=""),
        },
        nets={},
        dnp_components=("U3",),
        pin_functions={
            "U1.9": "EP",
            "U1.8": "THERMAL_ALERT",
            "U2.5": "Exposed Pad",
            "U3.9": "EPAD",
            "U4.9": "THERMAL_PAD",
        },
    )


def test_unmapped_explicit_exposed_pads_prompt_review_but_do_not_infer_vias() -> None:
    found = explicit_thermal_pad_scope_candidates(observed_netlist(), None)

    assert tuple(item.subject for item in found) == (
        "U1.9: EP (Synthetic:QFN)",
        "U2.5: Exposed Pad (Synthetic:DFN)",
    )
    assert all(item.rule_id == "pcb.explicit_thermal_pad_scope_unreviewed" for item in found)
    assert "does not imply that vias are required or adequate" in found[0].message
    assert found[0].evidence["review_state"] == (
        "no exact thermal-via requirement covers this pin",
    )


def test_exact_project_map_scope_suppresses_only_the_mapped_pin() -> None:
    thermal_map = mapping(requirement(pad="u1.9"))

    found = explicit_thermal_pad_scope_candidates(observed_netlist(), thermal_map)

    assert tuple(item.evidence["pin"] for item in found) == (("U2.5",),)


def test_candidate_retains_source_and_rejects_a_tampered_report_projection() -> None:
    observed = observed_netlist()
    candidate = explicit_thermal_pad_scope_candidates(observed, None)[0]

    assert isinstance(candidate, PcbExplicitThermalPadScopeCandidate)
    assert candidate.source_evidence.observed is observed
    assert candidate.source_evidence.thermal_via_map is None
    assert tuple(candidate.evidence) == (
        "pin",
        "pin_function",
        "footprint",
        "review_state",
        "review_boundary",
    )
    with pytest.raises(ValueError, match="source projection"):
        replace(candidate, evidence={"pin": ("U1.8",)})


def test_function_matching_is_exact_after_separator_and_case_normalization() -> None:
    observed = observed_netlist().model_copy(
        update={
            "pin_functions": {
                "U1.9": "eXpOsEd_PaD",
                "U1.8": "THERMAL_ALERT",
                "U2.5": "THERMAL-PAD",
                "U3.9": "Exposed pad",
            }
        }
    )

    found = explicit_thermal_pad_scope_candidates(observed, None)

    assert tuple(item.evidence["pin"] for item in found) == (("U1.9",), ("U2.5",))


def test_dnp_and_unassigned_footprints_are_controls() -> None:
    observed = observed_netlist().model_copy(
        update={"pin_functions": {"U3.9": "EP", "U4.9": "EXPOSED_PAD"}}
    )

    assert explicit_thermal_pad_scope_candidates(observed, None) == ()


def test_candidate_scanner_routes_the_prompt_and_is_order_independent() -> None:
    observed = observed_netlist()
    inputs = candidate_inputs(observed)
    inputs = replace(
        inputs,
        pcb=replace(
            inputs.pcb,
            is_pcb_project=True,
            thermal_via_map=mapping(requirement(pad="U1.9")),
        ),
    )
    reversed_observed = observed.model_copy(
        update={
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "components": dict(reversed(tuple(observed.components.items()))),
        }
    )
    reversed_inputs = replace(inputs, observed=reversed_observed)
    reversed_inputs = replace(
        reversed_inputs,
        bus=replace(reversed_inputs.bus, observed=reversed_observed),
        control=replace(reversed_inputs.control, observed=reversed_observed),
    )

    first = tuple(
        item
        for item in scan_candidates(inputs)
        if item.rule_id == "pcb.explicit_thermal_pad_scope_unreviewed"
    )
    second = tuple(
        item
        for item in scan_candidates(reversed_inputs)
        if item.rule_id == "pcb.explicit_thermal_pad_scope_unreviewed"
    )

    assert first == second
    assert tuple(item.evidence["pin"] for item in first) == (("U2.5",),)


def test_candidate_scanner_requires_authoritative_pcb_project_kind() -> None:
    inputs = candidate_inputs(observed_netlist())

    assert not any(
        item.rule_id == "pcb.explicit_thermal_pad_scope_unreviewed"
        for item in scan_candidates(inputs)
    )


def test_project_override_and_exact_ignore_control_the_review_prompt() -> None:
    observed = observed_netlist()
    pcb_coach = coach(observed).model_copy(update={"project_kind": ProjectKind.PCB})
    baseline = evaluate("synthetic-thermal-pad", pcb_coach, DesignLintPolicy())
    (baseline_finding,) = tuple(
        item
        for item in baseline.findings
        if item.rule_id == "pcb.explicit_thermal_pad_scope_unreviewed"
        and item.evidence["pin"] == ("U1.9",)
    )
    blocked = evaluate(
        "synthetic-thermal-pad",
        pcb_coach,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.explicit_thermal_pad_scope_unreviewed",
                    mode="block",
                    reason="Exercise explicit exposed-pad scope for this synthetic board",
                ),
            )
        ),
    )
    off = evaluate(
        "synthetic-thermal-pad",
        pcb_coach,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.explicit_thermal_pad_scope_unreviewed",
                    mode="off",
                    reason="The project has reviewed this rule as not applicable",
                ),
            )
        ),
    )
    ignored = evaluate(
        "synthetic-thermal-pad",
        pcb_coach,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=baseline_finding.rule_id,
                    fingerprint=baseline_finding.fingerprint,
                    reason="The synthetic project documents that no via requirement applies",
                ),
            )
        ),
    )

    assert baseline_finding.mode == "review"
    assert baseline_finding.disposition == "OPEN"
    assert (
        next(
            item for item in blocked.findings if item.fingerprint == baseline_finding.fingerprint
        ).mode
        == "block"
    )
    assert (
        next(
            item for item in off.findings if item.fingerprint == baseline_finding.fingerprint
        ).disposition
        == "RULE_OFF"
    )
    assert (
        next(
            item for item in ignored.findings if item.fingerprint == baseline_finding.fingerprint
        ).disposition
        == "IGNORED"
    )
