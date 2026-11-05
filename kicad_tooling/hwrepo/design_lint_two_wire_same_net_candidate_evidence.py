"""Typed source evidence for I2C and I3C same-net role pairs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from .bus_signal_roles import i3c_signal_identity
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2c_addressing import i2c_signal_role
from .netlist_contract_models import NetlistContract

I2C_SAME_NET_RULE_ID: DesignLintRuleId = "bus.i2c_sda_scl_same_net"
I3C_SAME_NET_RULE_ID: DesignLintRuleId = "bus.i3c_sda_scl_same_net"


@dataclass(frozen=True, slots=True)
class TwoWirePinEvidence:
    """One role-mapped two-wire pin with its current native function."""

    pin: str
    function: str

    @classmethod
    def from_native_pin_map(cls, observed: NetlistContract, pin: str) -> TwoWirePinEvidence:
        """Bind one role pin to its unique current native function."""
        function = lookup_unique_casefold(observed.pin_functions, pin)
        if function is None:
            raise ValueError("Two-wire evidence requires one current native pin function")
        return cls(pin=pin, function=function)


def _current_reference(observed: NetlistContract, reference: str) -> str:
    references = tuple(
        item for item in observed.components if item.casefold() == reference.casefold()
    )
    if len(references) != 1:
        raise ValueError("Two-wire evidence requires one current component")
    current = references[0]
    if not is_integrated_circuit_reference(current):
        raise ValueError("Two-wire evidence requires an integrated circuit")
    if current.casefold() in {item.casefold() for item in observed.dnp_components}:
        raise ValueError("Two-wire evidence requires a fitted component")
    return current


def _assignments(observed: NetlistContract, pin: str) -> tuple[str, ...]:
    nets = {
        net
        for net, pins in observed.nets.items()
        if any(current_pin.casefold() == pin.casefold() for current_pin in pins)
    }
    return tuple(sorted(nets, key=lambda item: (item.casefold(), item)))


def _validate_pair(
    observed: NetlistContract,
    *,
    reference: str,
    channel: str | None,
    sda: TwoWirePinEvidence,
    scl: TwoWirePinEvidence,
    net: str,
    identify_role: Callable[[str], tuple[str | None, str] | None],
) -> None:
    current_reference = _current_reference(observed, reference)
    if current_reference != reference:
        raise ValueError("Two-wire component reference must preserve native spelling")

    inventories = tuple(
        numbers
        for key, numbers in observed.component_pin_numbers.items()
        if key.casefold() == reference.casefold()
    )
    if len(inventories) != 1 or not inventories[0]:
        raise ValueError("Two-wire evidence requires a unique native pin inventory")
    inventory = {number.casefold() for number in inventories[0]}

    roles: dict[tuple[str | None, str], list[tuple[TwoWirePinEvidence, tuple[str, ...]]]] = {}
    for pin, function in observed.pin_functions.items():
        pin_reference, separator, number = pin.rpartition(".")
        if not separator or pin_reference.casefold() != reference.casefold():
            continue
        identity = identify_role(function)
        if identity is None:
            continue
        if not inventory or number.casefold() not in inventory:
            raise ValueError("Two-wire role pins must match the current native inventory")
        canonical_pin = TwoWirePinEvidence(f"{current_reference}.{number}", function)
        roles.setdefault(identity, []).append((canonical_pin, _assignments(observed, pin)))

    sda_matches = roles.get((channel, "SDA"), ())
    scl_matches = roles.get((channel, "SCL"), ())
    if len(sda_matches) != 1 or len(scl_matches) != 1:
        raise ValueError("Two-wire evidence requires one current SDA/SCL pair per channel")
    if sda_matches[0][0] != sda or scl_matches[0][0] != scl:
        raise ValueError("Two-wire endpoints must match their current native roles")

    sda_assignments = sda_matches[0][1]
    scl_assignments = scl_matches[0][1]
    if (
        sda_assignments != (net,)
        or scl_assignments != (net,)
        or sda_assignments[0].casefold() != scl_assignments[0].casefold()
    ):
        raise ValueError("Two-wire net must match both exact current assignments")

    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    if pin_types.get(sda.pin.casefold()) == pin_types.get(scl.pin.casefold()) == "output":
        raise ValueError("Two native outputs are excluded from the two-wire same-net finding")


@dataclass(frozen=True, slots=True)
class I2cSameNetEvidence:
    """One fitted native I2C SDA/SCL pair assigned to the same net."""

    observed: NetlistContract
    reference: str
    sda: TwoWirePinEvidence
    scl: TwoWirePinEvidence
    net: str

    def __post_init__(self) -> None:
        _validate_pair(
            self.observed,
            reference=self.reference,
            channel=None,
            sda=self.sda,
            scl=self.scl,
            net=self.net,
            identify_role=lambda function: (
                (None, role) if (role := i2c_signal_role(function)) is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class I3cSameNetEvidence:
    """One fitted native I3C channel's SDA/SCL pair assigned to the same net."""

    observed: NetlistContract
    reference: str
    channel: str | None
    sda: TwoWirePinEvidence
    scl: TwoWirePinEvidence
    net: str

    def __post_init__(self) -> None:
        _validate_pair(
            self.observed,
            reference=self.reference,
            channel=self.channel,
            sda=self.sda,
            scl=self.scl,
            net=self.net,
            identify_role=lambda function: (
                (identity.channel, identity.role)
                if (identity := i3c_signal_identity(function)) is not None
                else None
            ),
        )


TwoWireSameNetEvidence: TypeAlias = I2cSameNetEvidence | I3cSameNetEvidence


def project_two_wire_same_net_evidence(
    source: TwoWireSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Project source-checked I2C/I3C pairs into their existing rule fields."""
    if isinstance(source, I2cSameNetEvidence):
        return CandidateEvidenceProjection(
            rule_id=I2C_SAME_NET_RULE_ID,
            evidence={
                "component": (source.reference,),
                "SDA_pin": (source.sda.pin,),
                "SCL_pin": (source.scl.pin,),
                "net": (source.net,),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=I3C_SAME_NET_RULE_ID,
        evidence={
            "component": (source.reference,),
            "channel": (source.channel or "unindexed",),
            "SDA_pin": (source.sda.pin,),
            "SCL_pin": (source.scl.pin,),
            "net": (source.net,),
        },
    )


@dataclass(frozen=True, slots=True)
class TwoWireSameNetCandidate(Candidate):
    """Candidate whose I2C/I3C pair is bound to its current netlist."""

    source_evidence: TwoWireSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: TwoWireSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> TwoWireSameNetCandidate:
        projection = project_two_wire_same_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_two_wire_same_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Two-wire fields must match their typed source projection")
