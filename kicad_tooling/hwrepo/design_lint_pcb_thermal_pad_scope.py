"""Prompt for project review of explicitly named schematic thermal pads."""

from __future__ import annotations

from .design_lint_pcb_thermal_pad_scope_evidence import (
    PcbExplicitThermalPadScopeCandidate,
    PcbExplicitThermalPadScopeEvidence,
    is_explicit_thermal_pad_function,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .pcb_thermal_via_models import PcbThermalViaMap

RULE_ID: DesignLintRuleId = "pcb.explicit_thermal_pad_scope_unreviewed"


def explicit_thermal_pad_scope_candidates(
    observed: NetlistContract,
    thermal_via_map: PcbThermalViaMap | None,
) -> tuple[Candidate, ...]:
    """Prompt only for exact exported EP-like pins lacking a mapped via scope.

    This is a review prompt. It does not infer that a pad needs vias, and the
    mapped via-count rule remains the only place that evaluates authored via
    geometry or connectivity requirements.
    """
    mapped_pads: set[str] = (
        {item.pad.casefold() for item in thermal_via_map.requirements}
        if thermal_via_map is not None
        else set()
    )
    dnp_components = {reference.casefold() for reference in observed.dnp_components}
    components = {reference.casefold(): item for reference, item in observed.components.items()}
    findings: list[PcbExplicitThermalPadScopeCandidate] = []
    for pin, function in sorted(
        observed.pin_functions.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        reference, separator, number = pin.rpartition(".")
        if not separator or not reference or not number:
            continue
        component = components.get(reference.casefold())
        if (
            component is None
            or not component.footprint.strip()
            or reference.casefold() in dnp_components
            or not is_explicit_thermal_pad_function(function)
            or pin.casefold() in mapped_pads
        ):
            continue
        findings.append(
            PcbExplicitThermalPadScopeCandidate.from_source_evidence(
                PcbExplicitThermalPadScopeEvidence(
                    observed=observed,
                    thermal_via_map=thermal_via_map,
                    pin=pin,
                    function=function,
                    footprint=component.footprint,
                )
            )
        )
    return tuple(findings)
