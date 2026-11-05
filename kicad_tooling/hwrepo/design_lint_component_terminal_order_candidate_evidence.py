"""Source-bound evidence and stable projections for component terminal order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .component_bjt_symbols import basic_bjt_role_numbers
from .component_mosfet_symbols import mosfet_channel_type, mosfet_terminal_role_numbers
from .component_named_rail_terminal import (
    NamedRailTerminalEvidence,
    normalized_pin_function_index,
    validate_named_rail_terminal,
)
from .component_rail_potentials import potential_is_lower
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

BJT_TERMINAL_ORDER_RULE_ID: DesignLintRuleId = "component.bjt_terminal_order_on_named_rails"
MOSFET_TERMINAL_ORDER_RULE_ID: DesignLintRuleId = "component.mosfet_terminal_order_on_named_rails"

BjtFamily: TypeAlias = Literal["npn", "pnp"]
MosfetChannel: TypeAlias = Literal["nmos", "pmos"]


@dataclass(frozen=True, slots=True)
class BjtTerminalOrderEvidence:
    """Current native BJT identity and uniquely assigned collector/emitter rails."""

    observed: NetlistContract
    reference: str
    symbol: str
    family: BjtFamily
    collector: NamedRailTerminalEvidence
    emitter: NamedRailTerminalEvidence

    def __post_init__(self) -> None:
        inventory = _current_component_inventory(
            self.observed,
            reference=self.reference,
            symbol=self.symbol,
        )
        family = "npn" if "q_npn_" in self.symbol.casefold() else "pnp"
        if family != self.family:
            raise ValueError("BJT family must match the current native symbol")
        roles = basic_bjt_role_numbers(
            self.reference,
            self.symbol,
            inventory,
            normalized_pin_function_index(self.observed),
        )
        if roles is None:
            raise ValueError("BJT terminal evidence requires unique native B/C/E roles")
        validate_named_rail_terminal(
            self.observed,
            self.collector,
            expected_pin=f"{self.reference}.{roles['collector']}",
        )
        validate_named_rail_terminal(
            self.observed,
            self.emitter,
            expected_pin=f"{self.reference}.{roles['emitter']}",
        )
        unusual = (
            potential_is_lower(self.collector.potential, self.emitter.potential)
            if self.family == "npn"
            else potential_is_lower(self.emitter.potential, self.collector.potential)
        )
        if not unusual:
            raise ValueError("BJT terminal-order evidence must retain the reversed rail order")


@dataclass(frozen=True, slots=True)
class MosfetTerminalOrderEvidence:
    """Current native MOSFET identity and uniquely assigned drain/source rails."""

    observed: NetlistContract
    reference: str
    symbol: str
    channel_type: MosfetChannel
    drain: NamedRailTerminalEvidence
    source: NamedRailTerminalEvidence

    def __post_init__(self) -> None:
        inventory = _current_component_inventory(
            self.observed,
            reference=self.reference,
            symbol=self.symbol,
        )
        current_channel = mosfet_channel_type(self.symbol)
        if current_channel != self.channel_type:
            raise ValueError("MOSFET channel type must match the current native symbol")
        roles = mosfet_terminal_role_numbers(
            self.reference,
            self.symbol,
            inventory,
            self.observed.pin_functions,
        )
        if roles is None:
            raise ValueError("MOSFET terminal evidence requires unique native D/G/S roles")
        validate_named_rail_terminal(
            self.observed,
            self.drain,
            expected_pin=f"{self.reference}.{roles['drain']}",
        )
        validate_named_rail_terminal(
            self.observed,
            self.source,
            expected_pin=f"{self.reference}.{roles['source']}",
        )
        unusual = (
            potential_is_lower(self.drain.potential, self.source.potential)
            if self.channel_type == "nmos"
            else potential_is_lower(self.source.potential, self.drain.potential)
        )
        if not unusual:
            raise ValueError("MOSFET terminal-order evidence must retain the reversed rail order")


ComponentTerminalOrderEvidence: TypeAlias = BjtTerminalOrderEvidence | MosfetTerminalOrderEvidence


def project_component_terminal_order_evidence(
    source: ComponentTerminalOrderEvidence,
) -> CandidateEvidenceProjection:
    """Project typed terminal observations to each rule's stable report fields."""
    if isinstance(source, BjtTerminalOrderEvidence):
        evidence: dict[str, tuple[str, ...]] = {
            "component": (source.reference,),
            "symbol": (source.symbol,),
            "transistor_family": (source.family,),
            "collector_pin": (source.collector.pin,),
            "collector_net": (source.collector.net,),
            "collector_potential_basis": source.collector.potential.evidence,
            "emitter_pin": (source.emitter.pin,),
            "emitter_net": (source.emitter.net,),
            "emitter_potential_basis": source.emitter.potential.evidence,
            "expected_lower_terminal": ("emitter" if source.family == "npn" else "collector",),
            "observed_lower_terminal": ("collector" if source.family == "npn" else "emitter",),
        }
        if source.collector.potential.value is not None:
            evidence["collector_ordering_value_volts"] = (str(source.collector.potential.value),)
        if source.emitter.potential.value is not None:
            evidence["emitter_ordering_value_volts"] = (str(source.emitter.potential.value),)
        return CandidateEvidenceProjection(rule_id=BJT_TERMINAL_ORDER_RULE_ID, evidence=evidence)

    evidence = {
        "component": (source.reference,),
        "symbol": (source.symbol,),
        "channel_type": (source.channel_type,),
        "drain_pin": (source.drain.pin,),
        "drain_net": (source.drain.net,),
        "drain_potential_basis": source.drain.potential.evidence,
        "source_pin": (source.source.pin,),
        "source_net": (source.source.net,),
        "source_potential_basis": source.source.potential.evidence,
        "expected_lower_terminal": ("source" if source.channel_type == "nmos" else "drain",),
        "observed_lower_terminal": ("drain" if source.channel_type == "nmos" else "source",),
    }
    if source.drain.potential.value is not None:
        evidence["drain_ordering_value_volts"] = (str(source.drain.potential.value),)
    if source.source.potential.value is not None:
        evidence["source_ordering_value_volts"] = (str(source.source.potential.value),)
    return CandidateEvidenceProjection(rule_id=MOSFET_TERMINAL_ORDER_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ComponentTerminalOrderCandidate(Candidate):
    """Finding whose evidence is bound to its current native terminal source."""

    source_evidence: ComponentTerminalOrderEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ComponentTerminalOrderEvidence,
        *,
        subject: str,
        message: str,
    ) -> ComponentTerminalOrderCandidate:
        projection = project_component_terminal_order_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_component_terminal_order_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Terminal-order rule must match its typed source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Terminal-order report evidence must match its typed projection")


def _current_component_inventory(
    observed: NetlistContract,
    *,
    reference: str,
    symbol: str,
) -> tuple[str, ...]:
    reference_key = reference.casefold()
    fitted = {candidate.casefold() for candidate in observed.components}
    dnp = {candidate.casefold() for candidate in observed.dnp_components}
    inventory_by_reference = {
        candidate.casefold(): tuple(numbers)
        for candidate, numbers in observed.component_pin_numbers.items()
    }
    if (
        reference_key not in fitted
        or reference_key in dnp
        or observed.component_symbols.get(reference) != symbol
    ):
        raise ValueError("Terminal-order evidence requires the current fitted native component")
    inventory = inventory_by_reference.get(reference_key)
    if inventory is None:
        raise ValueError("Terminal-order evidence requires the complete native pin inventory")
    return inventory
