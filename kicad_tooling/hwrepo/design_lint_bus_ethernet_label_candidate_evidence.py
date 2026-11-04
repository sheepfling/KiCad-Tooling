"""Source-bound evidence for Ethernet pin-function and net-label mismatches."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias

from .bus_signal_pairs import (
    complementary_pin_function_key,
    ethernet_data_pair_function_role,
    ethernet_management_function_role,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

ETHERNET_DATA_LABEL_RULE_ID: DesignLintRuleId = "bus.ethernet_data_label_mismatch"
ETHERNET_MANAGEMENT_LABEL_RULE_ID: DesignLintRuleId = "bus.ethernet_management_label_mismatch"

_ETHERNET_NET_LABEL_ROLES: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "td+": ("TX", "positive"),
        "td-": ("TX", "negative"),
        "tdp": ("TX", "positive"),
        "tdn": ("TX", "negative"),
        "tx+": ("TX", "positive"),
        "tx-": ("TX", "negative"),
        "txp": ("TX", "positive"),
        "txn": ("TX", "negative"),
        "rd+": ("RX", "positive"),
        "rd-": ("RX", "negative"),
        "rdp": ("RX", "positive"),
        "rdn": ("RX", "negative"),
        "rx+": ("RX", "positive"),
        "rx-": ("RX", "negative"),
        "rxp": ("RX", "positive"),
        "rxn": ("RX", "negative"),
    }
)
_ETHERNET_NET_LABEL_PREFIXES = ("ethernet", "eth", "mdi")
_ETHERNET_MANAGEMENT_NET_LABEL_PREFIXES = ("ethernet", "eth", "smi")


def _ethernet_net_label_key(net: str, prefixes: tuple[str, ...]) -> str:
    key = complementary_pin_function_key(net)
    for prefix in prefixes:
        if key.startswith(prefix):
            key = key.removeprefix(prefix)
            break
    return key


def ethernet_data_net_label_role(net: str) -> tuple[str, str] | None:
    """Return a bounded data-pair role identified by an Ethernet net label."""
    key = _ethernet_net_label_key(net, _ETHERNET_NET_LABEL_PREFIXES)
    return _ETHERNET_NET_LABEL_ROLES.get(key)


def ethernet_management_net_label_role(net: str) -> str | None:
    """Return a bounded MDC/MDIO role identified by a management net label."""
    key = _ethernet_net_label_key(net, _ETHERNET_MANAGEMENT_NET_LABEL_PREFIXES)
    return {"mdc": "clock", "mdio": "data"}.get(key)


def _validate_pin_label_source(
    observed: NetlistContract,
    *,
    pin: str,
    function: str,
    net: str,
) -> None:
    if observed.pin_functions.get(pin) != function:
        raise ValueError("Ethernet pin function must match the retained native netlist")
    if netlist_pin_net_index(observed).get(pin.casefold(), set()) != {net}:
        raise ValueError("Ethernet pin must retain exactly its assigned native net")
    reference, separator, _number = pin.rpartition(".")
    if not separator or reference.casefold() in {
        item.casefold() for item in observed.dnp_components
    }:
        raise ValueError("Ethernet label findings require a fitted native component pin")


@dataclass(frozen=True, slots=True)
class EthernetDataLabelMismatchEvidence:
    """A current Ethernet TX/RX pin and a uniquely assigned conflicting label."""

    observed: NetlistContract
    pin: str
    function: str
    pin_role: tuple[str, str]
    net: str
    net_role: tuple[str, str]

    def __post_init__(self) -> None:
        _validate_pin_label_source(
            self.observed,
            pin=self.pin,
            function=self.function,
            net=self.net,
        )
        if ethernet_data_pair_function_role(self.function) != self.pin_role:
            raise ValueError("Ethernet pin role must match its current native function")
        if ethernet_data_net_label_role(self.net) != self.net_role:
            raise ValueError("Ethernet label role must match the assigned native net name")
        if self.pin_role == self.net_role:
            raise ValueError("Ethernet label findings require conflicting pair roles")


@dataclass(frozen=True, slots=True)
class EthernetManagementLabelMismatchEvidence:
    """A current MDC/MDIO pin and a uniquely assigned conflicting label."""

    observed: NetlistContract
    pin: str
    function: str
    pin_role: str
    net: str
    net_role: str

    def __post_init__(self) -> None:
        _validate_pin_label_source(
            self.observed,
            pin=self.pin,
            function=self.function,
            net=self.net,
        )
        if ethernet_management_function_role(self.function) != self.pin_role:
            raise ValueError("Ethernet management role must match its current native function")
        if ethernet_management_net_label_role(self.net) != self.net_role:
            raise ValueError("Ethernet management label role must match the assigned net name")
        if self.pin_role == self.net_role:
            raise ValueError("Ethernet management findings require conflicting roles")


EthernetLabelMismatchSource: TypeAlias = (
    EthernetDataLabelMismatchEvidence | EthernetManagementLabelMismatchEvidence
)


def project_ethernet_label_mismatch_evidence(
    source: EthernetLabelMismatchSource,
) -> CandidateEvidenceProjection:
    """Project the typed pin and label roles into their existing rule fields."""
    if isinstance(source, EthernetDataLabelMismatchEvidence):
        evidence = {
            "pin": (source.pin,),
            "pin_function": (source.function,),
            "pin_direction": (source.pin_role[0],),
            "pin_side": (source.pin_role[1],),
            "net": (source.net,),
            "net_direction": (source.net_role[0],),
            "net_side": (source.net_role[1],),
        }
        rule_id = ETHERNET_DATA_LABEL_RULE_ID
    else:
        evidence = {
            "pin": (source.pin,),
            "pin_function": (source.function,),
            "pin_role": (source.pin_role,),
            "net": (source.net,),
            "net_role": (source.net_role,),
        }
        rule_id = ETHERNET_MANAGEMENT_LABEL_RULE_ID
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class EthernetLabelMismatchCandidate(Candidate):
    """Candidate retaining its current native pin and conflicting label source."""

    source_evidence: EthernetLabelMismatchSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: EthernetLabelMismatchSource,
        *,
        subject: str,
        message: str,
    ) -> EthernetLabelMismatchCandidate:
        projection = project_ethernet_label_mismatch_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_ethernet_label_mismatch_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Ethernet label candidate must match its typed source projection")
