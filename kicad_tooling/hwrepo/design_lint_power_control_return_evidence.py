"""Source-bound evidence for fixed enable controls on return-like net labels."""

from __future__ import annotations

from dataclasses import dataclass

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .return_nets import is_return_like_net_name, is_vss_prefixed_net_name


@dataclass(frozen=True, slots=True)
class EnableControlReturnEvidence:
    """One fitted simple enable input with one exact return-like net assignment."""

    observed: NetlistContract
    pin: str
    function: str
    net: str

    def __post_init__(self) -> None:
        if lookup_unique_casefold(self.observed.pin_functions, self.pin) != self.function:
            raise ValueError("Enable-control evidence must match the current native function")
        reference, separator, _ = self.pin.rpartition(".")
        if not separator or reference.startswith("#"):
            raise ValueError("Enable-control evidence requires a component pin")
        if lookup_unique_casefold(self.observed.components, reference) is None:
            raise ValueError("Enable-control evidence requires an inventoried component")
        if reference.casefold() in {item.casefold() for item in self.observed.dnp_components}:
            raise ValueError("Enable-control evidence requires a fitted component")
        if self.function.strip().casefold() not in {"en", "enable"}:
            raise ValueError(
                "Enable-control evidence requires an unqualified EN or ENABLE function"
            )
        if lookup_unique_casefold(self.observed.pin_electrical_types, self.pin) != "input":
            raise ValueError("Enable-control evidence requires a native input electrical type")
        assignments = netlist_pin_net_index(self.observed).get(self.pin.casefold(), set())
        if len(assignments) != 1 or next(iter(assignments)) != self.net:
            raise ValueError("Enable-control evidence must match one exact net assignment")
        if not is_return_like_net_name(self.net) or is_vss_prefixed_net_name(self.net):
            raise ValueError("Enable-control evidence requires an unambiguous return-like label")
