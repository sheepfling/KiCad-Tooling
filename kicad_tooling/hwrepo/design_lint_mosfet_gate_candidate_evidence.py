"""Typed source evidence for the distinct MOSFET gate connectivity reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .component_mosfet_symbols import (
    SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS,
    mosfet_terminal_role,
    mosfet_terminal_role_numbers,
)
from .component_pin_types import fitted_output_pins_on_net
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .resistor_paths import DirectResistor, direct_resistors

MOSFET_GATE_WITHOUT_PEER_RULE_ID: DesignLintRuleId = "component.mosfet_gate_without_peer"
MOSFET_GATE_WITHOUT_SOURCE_BIAS_RULE_ID: DesignLintRuleId = (
    "component.mosfet_gate_without_visible_source_bias"
)
MOSFET_GATE_DIRECT_DRIVE_RULE_ID: DesignLintRuleId = "component.mosfet_gate_direct_drive"


def _pin_assignments(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        net
        for net, pins in observed.nets.items()
        for member in pins
        if member.casefold() == pin.casefold()
    )


def _fitted_net_members(
    observed: NetlistContract,
    net: str,
    pin: str,
    *,
    require_pin_separator: bool,
) -> tuple[str, ...]:
    components = {reference.casefold() for reference in observed.components}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    return tuple(
        sorted(
            (
                member
                for member in observed.nets[net]
                if member.casefold() != pin.casefold()
                and (not require_pin_separator or "." in member)
                and member.rsplit(".", 1)[0].casefold() in components
                and member.rsplit(".", 1)[0].casefold() not in unpopulated
            ),
            key=str.casefold,
        )
    )


@dataclass(frozen=True, slots=True)
class SupportedMosfetGate:
    """Current fitted supported MOSFET identity and its unique native gate pin."""

    observed: NetlistContract
    reference: str
    symbol: str
    gate_pin: str
    gate_function: str

    def __post_init__(self) -> None:
        components = {reference.casefold() for reference in self.observed.components}
        if self.reference.casefold() not in components:
            raise ValueError("MOSFET gate source must retain a current component")
        if self.reference.casefold() in {
            reference.casefold() for reference in self.observed.dnp_components
        }:
            raise ValueError("MOSFET gate source must retain a fitted component")

        symbols = {
            reference.casefold(): symbol
            for reference, symbol in self.observed.component_symbols.items()
        }
        if (
            symbols.get(self.reference.casefold()) != self.symbol
            or self.symbol.casefold() not in SUPPORTED_THREE_TERMINAL_MOSFET_SYMBOLS
        ):
            raise ValueError("MOSFET gate source must retain an exact supported native symbol")

        inventories = {
            reference.casefold(): tuple(numbers)
            for reference, numbers in self.observed.component_pin_numbers.items()
        }
        pin_numbers = inventories.get(self.reference.casefold(), ())
        if len(pin_numbers) != 3 or len({number.casefold() for number in pin_numbers}) != 3:
            raise ValueError("MOSFET gate source requires a complete three-pin inventory")

        functions = {pin.casefold(): value for pin, value in self.observed.pin_functions.items()}
        gate_pins = tuple(
            f"{self.reference}.{number}"
            for number in pin_numbers
            if mosfet_terminal_role(functions.get(f"{self.reference}.{number}".casefold()))
            == "gate"
        )
        if len(gate_pins) != 1 or gate_pins[0].casefold() != self.gate_pin.casefold():
            raise ValueError("MOSFET gate source must retain its unique native gate pin")
        if functions.get(self.gate_pin.casefold()) != self.gate_function:
            raise ValueError("MOSFET gate function must match the current native netlist")
        if mosfet_terminal_role(self.gate_function) != "gate":
            raise ValueError("MOSFET gate function must remain G or Gate")


@dataclass(frozen=True, slots=True)
class MosfetGateWithoutPeerEvidence:
    """A current supported gate with no other fitted pin on its native net."""

    device: SupportedMosfetGate
    assigned_net: str | None
    other_fitted_net_members: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        assignments = _pin_assignments(self.device.observed, self.device.gate_pin)
        if len(assignments) > 1:
            raise ValueError("MOSFET gate source must retain at most one native net assignment")
        current_net = assignments[0] if assignments else None
        if current_net != self.assigned_net:
            raise ValueError("MOSFET gate assignment must match the current native netlist")
        current_peers = (
            _fitted_net_members(
                self.device.observed,
                current_net,
                self.device.gate_pin,
                require_pin_separator=False,
            )
            if current_net is not None
            else ()
        )
        if current_peers != self.other_fitted_net_members or current_peers:
            raise ValueError("No-peer MOSFET evidence requires no other fitted net members")


@dataclass(frozen=True, slots=True)
class MosfetGateWithoutSourceBiasEvidence:
    """A gate peer and source terminal with no visible direct resistor between nets."""

    device: SupportedMosfetGate
    source_pin: str
    source_function: str
    gate_net: str
    source_net: str
    fitted_gate_peers: tuple[str, ...]
    visible_source_bias_resistors: tuple[DirectResistor, ...] = ()

    def __post_init__(self) -> None:
        observed = self.device.observed
        reference_key = self.device.reference.casefold()
        inventories = {
            reference.casefold(): tuple(numbers)
            for reference, numbers in observed.component_pin_numbers.items()
        }
        functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
        source_pins = tuple(
            f"{self.device.reference}.{number}"
            for number in inventories.get(reference_key, ())
            if mosfet_terminal_role(functions.get(f"{self.device.reference}.{number}".casefold()))
            == "source"
        )
        if len(source_pins) != 1 or source_pins[0].casefold() != self.source_pin.casefold():
            raise ValueError("MOSFET source-bias evidence requires its unique native source pin")
        if functions.get(self.source_pin.casefold()) != self.source_function:
            raise ValueError("MOSFET source function must match the current native netlist")
        if mosfet_terminal_role(self.source_function) != "source":
            raise ValueError("MOSFET source function must remain S or Source")

        gate_assignments = _pin_assignments(observed, self.device.gate_pin)
        source_assignments = _pin_assignments(observed, self.source_pin)
        if len(gate_assignments) != 1 or gate_assignments[0] != self.gate_net:
            raise ValueError("MOSFET gate net must match one current native assignment")
        if len(source_assignments) != 1 or source_assignments[0] != self.source_net:
            raise ValueError("MOSFET source net must match one current native assignment")
        if self.gate_net.casefold() == self.source_net.casefold():
            raise ValueError("MOSFET gate and source must retain distinct native nets")

        current_peers = _fitted_net_members(
            observed,
            self.gate_net,
            self.device.gate_pin,
            require_pin_separator=True,
        )
        if not current_peers or current_peers != self.fitted_gate_peers:
            raise ValueError("MOSFET gate peers must match the current fitted net members")

        current_bias_resistors = tuple(
            resistor
            for resistor in direct_resistors(observed)
            if frozenset((resistor.first_net.casefold(), resistor.second_net.casefold()))
            == frozenset((self.gate_net.casefold(), self.source_net.casefold()))
        )
        if current_bias_resistors != self.visible_source_bias_resistors or current_bias_resistors:
            raise ValueError("MOSFET source-bias finding requires no direct visible resistor")


@dataclass(frozen=True, slots=True)
class MosfetGateDirectDriveEvidence:
    """A supported MOSFET gate sharing one net with output-capable fitted pins."""

    device: SupportedMosfetGate
    drain_pin: str
    source_pin: str
    gate_net: str
    output_pins: tuple[str, ...]
    output_pin_types: tuple[str, ...]

    def __post_init__(self) -> None:
        observed = self.device.observed
        inventories = {
            reference.casefold(): tuple(numbers)
            for reference, numbers in observed.component_pin_numbers.items()
        }
        roles = mosfet_terminal_role_numbers(
            self.device.reference,
            self.device.symbol,
            inventories.get(self.device.reference.casefold(), ()),
            observed.pin_functions,
        )
        if roles is None:
            raise ValueError("Direct-drive evidence requires unique native D/G/S pin roles")
        if (
            f"{self.device.reference}.{roles.gate}".casefold() != self.device.gate_pin.casefold()
            or f"{self.device.reference}.{roles.drain}".casefold() != self.drain_pin.casefold()
            or f"{self.device.reference}.{roles.source}".casefold() != self.source_pin.casefold()
        ):
            raise ValueError("Direct-drive terminal pins must match the current MOSFET roles")

        gate_assignments = _pin_assignments(observed, self.device.gate_pin)
        if len(gate_assignments) != 1 or gate_assignments[0] != self.gate_net:
            raise ValueError("Direct-drive gate net must match one current native assignment")
        output_peers = fitted_output_pins_on_net(
            observed,
            self.gate_net,
            excluded_references=(self.device.reference,),
        )
        current_output_pins = tuple(pin for pin, _pin_type in output_peers)
        current_output_pin_types = tuple(f"{pin}={pin_type}" for pin, pin_type in output_peers)
        if not current_output_pins:
            raise ValueError("Direct-drive evidence requires an output-capable fitted peer")
        if (
            self.output_pins != current_output_pins
            or self.output_pin_types != current_output_pin_types
        ):
            raise ValueError("Direct-drive output pins must match current fitted native peers")


MosfetGateCandidateEvidence: TypeAlias = (
    MosfetGateWithoutPeerEvidence
    | MosfetGateWithoutSourceBiasEvidence
    | MosfetGateDirectDriveEvidence
)


def project_mosfet_gate_candidate_evidence(
    source: MosfetGateCandidateEvidence,
) -> CandidateEvidenceProjection:
    """Project either typed MOSFET gate source into its existing report fields."""
    device = source.device
    if isinstance(source, MosfetGateWithoutPeerEvidence):
        return CandidateEvidenceProjection(
            rule_id=MOSFET_GATE_WITHOUT_PEER_RULE_ID,
            evidence={
                "component": (device.reference,),
                "symbol": (device.symbol,),
                "gate_pin": (device.gate_pin,),
                "gate_function": (device.gate_function,),
                "assigned_net": (source.assigned_net or "<unassigned>",),
                "other_fitted_net_members": source.other_fitted_net_members,
            },
        )
    if isinstance(source, MosfetGateWithoutSourceBiasEvidence):
        return CandidateEvidenceProjection(
            rule_id=MOSFET_GATE_WITHOUT_SOURCE_BIAS_RULE_ID,
            evidence={
                "component": (device.reference,),
                "symbol": (device.symbol,),
                "gate_pin": (device.gate_pin,),
                "gate_net": (source.gate_net,),
                "source_pin": (source.source_pin,),
                "source_net": (source.source_net,),
                "fitted_gate_peers": source.fitted_gate_peers,
                "visible_source_bias_resistors": (),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=MOSFET_GATE_DIRECT_DRIVE_RULE_ID,
        evidence={
            "component": (device.reference,),
            "symbol": (device.symbol,),
            "gate_pin": (device.gate_pin,),
            "gate_net": (source.gate_net,),
            "output_pins": source.output_pins,
            "output_pin_types": source.output_pin_types,
        },
    )


@dataclass(frozen=True, slots=True)
class MosfetGateCandidate(Candidate):
    """Candidate with a typed source variant for its gate-topology rule."""

    source_evidence: MosfetGateCandidateEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MosfetGateCandidateEvidence,
        *,
        subject: str,
        message: str,
    ) -> MosfetGateCandidate:
        projection = project_mosfet_gate_candidate_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mosfet_gate_candidate_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("MOSFET gate candidate must match its typed source projection")
