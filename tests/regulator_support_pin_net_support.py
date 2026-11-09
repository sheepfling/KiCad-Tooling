"""Synthetic authored net maps and native observations for active support pins."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.regulator_support_models import (
    RegulatorSupportNetComponentRequirement,
    RegulatorSupportPinNetExpectation,
    RegulatorSupportPinNetMap,
    RegulatorSupportPinNetTopologyRequirement,
)
from tests.test_regulator_support_pin_roles import (
    support_map,
)
from tests.test_regulator_support_pin_roles import (
    support_netlist as support_role_netlist,
)

_EXPECTED_NETS = {
    "U2.1": "PRIMARY_FEEDBACK",
    "U2.2": "ISOLATOR_OUTPUT",
    "U3.1": "SECONDARY_OUTPUT",
    "U3.2": "SECONDARY_RETURN",
    "U3.3": "SECONDARY_FEEDBACK",
}


def support_pin_net_map() -> RegulatorSupportPinNetMap:
    """Declare exact active-support pin assignments for the synthetic fixture."""
    role_map = support_map()
    return RegulatorSupportPinNetMap(
        basis="Synthetic independently reviewed active-support pin-to-net map",
        requirements=tuple(
            RegulatorSupportPinNetTopologyRequirement(
                id=topology.id,
                basis=topology.basis,
                regulator_reference=topology.regulator_reference,
                components=tuple(
                    RegulatorSupportNetComponentRequirement(
                        role=component.role,
                        reference=component.reference,
                        value=component.value,
                        symbol=component.symbol,
                        footprint=component.footprint,
                        part_id=component.part_id,
                        pins=tuple(
                            RegulatorSupportPinNetExpectation(
                                pin=pin.pin,
                                expected_net=_EXPECTED_NETS[pin.pin],
                            )
                            for pin in component.pins
                        ),
                    )
                    for component in topology.components
                ),
            )
            for topology in role_map.requirements
        ),
    )


def support_pin_netlist(*, fault: str | None = None) -> NetlistContract:
    """Add the declared active-support nets and one isolated synthetic fault."""
    source = support_role_netlist()
    nets = dict(source.nets)
    for pin, net in _EXPECTED_NETS.items():
        if fault == "wrong-net" and pin == "U2.1":
            nets["OTHER_PRIMARY_FEEDBACK"] = (pin,)
        elif fault == "unconnected" and pin == "U3.3":
            continue
        else:
            nets[net] = (pin,)
    return source.model_copy(update={"nets": nets})
