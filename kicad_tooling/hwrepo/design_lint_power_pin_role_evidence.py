"""Source-bound evidence for native power-pin role and rail findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_identity import (
    connector_candidate_references,
    is_return_function,
    power_function_key,
)
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .power_rails import negative_voltage_rail_key
from .return_nets import is_return_like_net_name

NetRole = Literal["return", "positive"]


def opposite_net_role_sources(
    observed: NetlistContract,
    net: str,
    *,
    role: NetRole,
    exclude_pin: str,
) -> tuple[str, ...]:
    """Return bounded label and peer-pin evidence for one apparent net role."""
    if role == "return":
        if power_function_key(net) is not None:
            return ()
        if is_return_like_net_name(net):
            return ("net_name=return_like",)
        return tuple(
            sorted(
                f"{pin}:native_function={observed.pin_functions[pin]}"
                for pin in observed.nets.get(net, ())
                if pin.casefold() != exclude_pin.casefold()
                and is_return_function(observed.pin_functions.get(pin, ""))
            )
        )
    if is_return_like_net_name(net):
        return ()
    supply_key = power_function_key(net)
    if supply_key is not None:
        return (f"net_name=positive_supply:{supply_key}",)
    return tuple(
        sorted(
            f"{pin}:native_function={observed.pin_functions[pin]}"
            for pin in observed.nets.get(net, ())
            if pin.casefold() != exclude_pin.casefold()
            and power_function_key(observed.pin_functions.get(pin, "")) is not None
        )
    )


def _require_current_fitted_pin(
    observed: NetlistContract,
    *,
    pin: str,
    function: str,
) -> str:
    """Check that a source pin still has its recorded function and is populated."""
    if observed.pin_functions.get(pin) != function:
        raise ValueError("Power-pin evidence must match the current native pin function")
    reference = pin.rsplit(".", 1)[0]
    if reference.startswith("#"):
        raise ValueError("Power-pin evidence requires a component pin")
    if reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        raise ValueError("Power-pin evidence requires a fitted component")
    return reference


def _require_unique_pin_net(
    observed: NetlistContract,
    *,
    pin: str,
    net: str,
) -> None:
    assignments = netlist_pin_net_index(observed).get(pin.casefold(), set())
    if len(assignments) != 1 or next(iter(assignments)) != net:
        raise ValueError("Power-pin evidence must match one exact current net assignment")


@dataclass(frozen=True, slots=True)
class NamedSupplyPinNegativeRailEvidence:
    """One fitted supply-function pin on a recognized negative-voltage rail."""

    observed: NetlistContract
    pin: str
    function: str
    net: str

    def __post_init__(self) -> None:
        _require_current_fitted_pin(self.observed, pin=self.pin, function=self.function)
        _require_unique_pin_net(self.observed, pin=self.pin, net=self.net)
        if power_function_key(self.function) is None:
            raise ValueError("Negative-rail evidence requires a recognized supply function")
        if negative_voltage_rail_key(self.net) is None:
            raise ValueError("Negative-rail evidence requires a recognized negative rail")

    @property
    def supply_function_key(self) -> str:
        """Return the current bounded native supply-function key."""
        key = power_function_key(self.function)
        if key is None:
            raise ValueError("Negative-rail evidence requires a recognized supply function")
        return key

    @property
    def negative_rail_key(self) -> str:
        """Return the current bounded negative-voltage rail key."""
        key = negative_voltage_rail_key(self.net)
        if key is None:
            raise ValueError("Negative-rail evidence requires a recognized negative rail")
        return key


@dataclass(frozen=True, slots=True)
class NamedPowerPinNetRoleConflictEvidence:
    """One fitted native power pin whose assigned net has a conflicting role."""

    observed: NetlistContract
    pin: str
    function: str
    net: str
    reviewed_connector_references: tuple[str, ...] = ()
    opposite_role_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewed_connector_references",
            tuple(self.reviewed_connector_references),
        )
        object.__setattr__(self, "opposite_role_sources", tuple(self.opposite_role_sources))
        reference = _require_current_fitted_pin(
            self.observed,
            pin=self.pin,
            function=self.function,
        )
        _require_unique_pin_net(self.observed, pin=self.pin, net=self.net)
        supply_key = power_function_key(self.function)
        is_return = is_return_function(self.function)
        if supply_key is None and not is_return:
            raise ValueError("Power-role evidence requires a recognized native pin role")
        connector_references = connector_candidate_references(
            self.observed,
            self.reviewed_connector_references,
        )
        if is_return and reference.casefold() in {item.casefold() for item in connector_references}:
            raise ValueError("Connector return pins are owned by connector-specific findings")
        role: NetRole = "return" if supply_key is not None else "positive"
        current_role_sources = opposite_net_role_sources(
            self.observed,
            self.net,
            role=role,
            exclude_pin=self.pin,
        )
        if not current_role_sources or self.opposite_role_sources != current_role_sources:
            raise ValueError("Power-role evidence requires current conflicting net-role evidence")

    @property
    def pin_role(self) -> str:
        """Return the bounded role string used by the existing report projection."""
        supply_key = power_function_key(self.function)
        return f"positive_supply:{supply_key}" if supply_key is not None else "return"
