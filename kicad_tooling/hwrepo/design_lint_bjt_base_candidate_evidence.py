"""Typed source evidence and wire projection for BJT base review findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_bjt_symbols import basic_bjt_role_numbers
from .component_pin_types import fitted_output_pins_on_net
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .resistor_paths import direct_resistors

BJT_BASE_DIRECT_DRIVE_RULE_ID: DesignLintRuleId = "component.bjt_base_direct_drive"
BJT_BASE_WITHOUT_EMITTER_BIAS_RULE_ID: DesignLintRuleId = (
    "component.bjt_base_without_visible_emitter_bias"
)


def _pin_assignments(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    return tuple(
        net
        for net, pins in observed.nets.items()
        for member in pins
        if member.casefold() == pin.casefold()
    )


def _bjt_base_pin(
    observed: NetlistContract,
    *,
    reference: str,
    symbol: str,
) -> str:
    component = lookup_unique_casefold(observed.components, reference)
    current_symbol = lookup_unique_casefold(observed.component_symbols, reference)
    inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
    if (
        component is None
        or reference.casefold() in {item.casefold() for item in observed.dnp_components}
        or current_symbol != symbol
        or inventory is None
    ):
        raise ValueError("BJT base evidence requires a current fitted native component")

    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    roles = basic_bjt_role_numbers(reference, symbol, inventory, functions)
    if roles is None:
        raise ValueError(
            "BJT base evidence requires exact native base, collector, and emitter roles"
        )
    return f"{reference}.{roles['base']}"


def _base_net_peers(
    observed: NetlistContract,
    *,
    base_pin: str,
    base_net: str,
) -> tuple[str, ...]:
    pin_members = lookup_unique_casefold(observed.nets, base_net)
    if pin_members is None:
        raise ValueError("BJT base evidence requires a unique current base net")
    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    return tuple(
        sorted(
            (
                pin
                for pin in pin_members
                if pin.casefold() != base_pin.casefold()
                and "." in pin
                and pin.rsplit(".", 1)[0].casefold() in fitted
                and pin.rsplit(".", 1)[0].casefold() not in dnp
            ),
            key=str.casefold,
        )
    )


@dataclass(frozen=True, slots=True)
class BjtBaseDirectDriveEvidence:
    """A supported fitted BJT base and its exact output-capable net peers."""

    observed: NetlistContract
    reference: str
    symbol: str
    base_pin: str
    base_net: str
    output_peers: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        current_base_pin = _bjt_base_pin(
            self.observed,
            reference=self.reference,
            symbol=self.symbol,
        )
        if self.base_pin.casefold() != current_base_pin.casefold():
            raise ValueError("BJT base pin must match its current native role")
        if _pin_assignments(self.observed, self.base_pin) != (self.base_net,):
            raise ValueError("BJT base net must match its unique current native assignment")
        current_output_peers = fitted_output_pins_on_net(
            self.observed,
            self.base_net,
            excluded_references=(self.reference,),
        )
        if not current_output_peers or self.output_peers != current_output_peers:
            raise ValueError("BJT output peers must match the current base net")


@dataclass(frozen=True, slots=True)
class BjtBaseBiasEvidence:
    """A supported BJT base without an observed direct base-emitter resistor."""

    observed: NetlistContract
    reference: str
    symbol: str
    base_pin: str
    base_net: str
    emitter_pin: str
    emitter_net: str
    fitted_base_net_peers: tuple[str, ...]

    def __post_init__(self) -> None:
        current_base_pin = _bjt_base_pin(
            self.observed,
            reference=self.reference,
            symbol=self.symbol,
        )
        inventory = lookup_unique_casefold(self.observed.component_pin_numbers, self.reference)
        assert inventory is not None
        functions = {pin.casefold(): value for pin, value in self.observed.pin_functions.items()}
        roles = basic_bjt_role_numbers(self.reference, self.symbol, inventory, functions)
        assert roles is not None
        current_emitter_pin = f"{self.reference}.{roles['emitter']}"

        if self.base_pin.casefold() != current_base_pin.casefold():
            raise ValueError("BJT base pin must match its current native role")
        if self.emitter_pin.casefold() != current_emitter_pin.casefold():
            raise ValueError("BJT emitter pin must match its current native role")
        if _pin_assignments(self.observed, self.base_pin) != (self.base_net,):
            raise ValueError("BJT base net must match its unique current native assignment")
        if _pin_assignments(self.observed, self.emitter_pin) != (self.emitter_net,):
            raise ValueError("BJT emitter net must match its unique current native assignment")
        if self.base_net.casefold() == self.emitter_net.casefold():
            raise ValueError("BJT base-bias evidence requires distinct base and emitter nets")

        current_peers = _base_net_peers(
            self.observed,
            base_pin=self.base_pin,
            base_net=self.base_net,
        )
        if not current_peers or self.fitted_base_net_peers != current_peers:
            raise ValueError("BJT base peers must match the current fitted net members")
        output_peers = fitted_output_pins_on_net(
            self.observed,
            self.base_net,
            excluded_references=(self.reference,),
        )
        if output_peers:
            raise ValueError("Direct output peers belong to the BJT base-drive finding")

        bias_nets = frozenset((self.base_net.casefold(), self.emitter_net.casefold()))
        if any(
            frozenset((item.first_net.casefold(), item.second_net.casefold())) == bias_nets
            for item in direct_resistors(self.observed)
        ):
            raise ValueError("Visible base-emitter resistors exclude the BJT base-bias finding")


BjtBaseEvidence: TypeAlias = BjtBaseDirectDriveEvidence | BjtBaseBiasEvidence


def project_bjt_base_evidence(source: BjtBaseEvidence) -> CandidateEvidenceProjection:
    """Project BJT source records into their existing rule-specific wire fields."""
    if isinstance(source, BjtBaseDirectDriveEvidence):
        return CandidateEvidenceProjection(
            rule_id=BJT_BASE_DIRECT_DRIVE_RULE_ID,
            evidence={
                "component": (source.reference,),
                "symbol": (source.symbol,),
                "base_pin": (source.base_pin,),
                "base_net": (source.base_net,),
                "output_pins": tuple(pin for pin, _ in source.output_peers),
                "output_pin_types": tuple(
                    f"{pin}={pin_type}" for pin, pin_type in source.output_peers
                ),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=BJT_BASE_WITHOUT_EMITTER_BIAS_RULE_ID,
        evidence={
            "component": (source.reference,),
            "symbol": (source.symbol,),
            "base_pin": (source.base_pin,),
            "base_net": (source.base_net,),
            "emitter_pin": (source.emitter_pin,),
            "emitter_net": (source.emitter_net,),
            "fitted_base_net_peers": source.fitted_base_net_peers,
            "visible_base_emitter_bias_resistors": (),
        },
    )


@dataclass(frozen=True, slots=True)
class BjtBaseCandidate(Candidate):
    """Candidate whose evidence remains bound to one current BJT netlist."""

    source_evidence: BjtBaseEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: BjtBaseEvidence,
        *,
        subject: str,
        message: str,
    ) -> BjtBaseCandidate:
        projection = project_bjt_base_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_bjt_base_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("BJT base fields must match their typed source projection")
