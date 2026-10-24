"""Review source-mapped connector signal pins with no schematic net."""

from __future__ import annotations

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_roles import named_rail_role_clue

RULE_ID: DesignLintRuleId = "connector.mapped_interface_signal_unassigned"
SHIELD_RULE_ID: DesignLintRuleId = "connector.mapped_interface_shield_unassigned"
POWER_CONTACT_RULE_ID: DesignLintRuleId = "connector.mapped_interface_power_contact_unassigned"
OTHER_CONTACT_RULE_ID: DesignLintRuleId = "connector.mapped_interface_other_unassigned"
OTHER_NAMED_RAIL_RULE_ID: DesignLintRuleId = "connector.mapped_interface_other_named_rail"
SUPPLY_RETURN_NET_RULE_ID: DesignLintRuleId = "connector.mapped_interface_supply_on_return_net"
SIGNAL_NAMED_RAIL_RULE_ID: DesignLintRuleId = "connector.mapped_interface_signal_on_named_rail"
SHIELD_RETURN_NET_RULE_ID: DesignLintRuleId = "connector.mapped_interface_shield_on_return_net"
SHIELD_SUPPLY_RAIL_RULE_ID: DesignLintRuleId = "connector.mapped_interface_shield_on_supply_rail"


def unassigned_mapped_interface_signal_pins(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt on open generic signal contacts in complete, source-matched interfaces."""
    if coverage is None:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        electrical_type = observed.pin_electrical_types.get(pin)
        if (
            mapped.role != "signal"
            or mapped.nets
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or electrical_type in {"power_in", "power_out"}
        ):
            continue

        results.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: reviewed signal contact has no net assignment",
                message=(
                    f"The source-matched interface maps this pin to {mapped.interface_signal}, "
                    "but the native netlist assigns it to no net. Review whether the contact "
                    "needs a board connection or is intentionally open; record an explicit "
                    "unconnected-pin reason for an intentional open. This check does not prove "
                    "the chosen net is electrically correct or that PCB copper is continuous."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("signal",),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "native_pin_electrical_type": (electrical_type or "<missing>",),
                    "assigned_nets": (),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def unassigned_mapped_interface_power_contacts(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    *,
    excluded_pins: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Prompt on open generic supply/return contacts in current mapped interfaces."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        electrical_type = observed.pin_electrical_types.get(pin)
        if (
            mapped.role not in {"supply", "return"}
            or mapped.nets
            or mapped.unconnected_reason is not None
            or pin.casefold() in excluded_pins
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
        ):
            continue

        role = str(mapped.role)
        results.append(
            Candidate(
                rule_id=POWER_CONTACT_RULE_ID,
                subject=f"{pin}: reviewed {role} contact has no net assignment",
                message=(
                    f"The source-matched interface maps this generic contact to "
                    f"{mapped.interface_signal} as a {role} contact, but the native netlist "
                    "assigns it to no net. Review whether the contact needs a board connection "
                    "or is intentionally open; record an explicit unconnected-pin reason for "
                    "an intentional open. This check does not infer the correct net, require "
                    "different contacts to share a net, or establish PCB copper continuity."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": (role,),
                    "interface_voltage_domain": (str(mapped.voltage_domain or "<missing>"),),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "native_pin_electrical_type": (electrical_type or "<missing>",),
                    "assigned_nets": (),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def unassigned_mapped_interface_shield_pins(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt when a reviewed shield contact has neither a net nor an open reason."""
    if coverage is None:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        electrical_type = observed.pin_electrical_types.get(pin)
        if (
            mapped.role != "shield"
            or mapped.nets
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
        ):
            continue

        results.append(
            Candidate(
                rule_id=SHIELD_RULE_ID,
                subject=f"{pin}: reviewed shield contact has no net assignment",
                message=(
                    f"The source-matched interface maps this pin to {mapped.interface_signal} "
                    "as a shield contact, but the native netlist assigns it to no net. Review "
                    "whether the shield needs an intentional board bond or should remain "
                    "isolated; record an explicit unconnected-pin reason for an intentional "
                    "open. This check does not establish the correct bond point or PCB copper "
                    "continuity."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("shield",),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "native_pin_electrical_type": (electrical_type or "<missing>",),
                    "assigned_nets": (),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def unassigned_mapped_interface_other_pins(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review open generic contacts mapped as other without an open disposition."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            mapped.role != "other"
            or mapped.nets
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
        ):
            continue

        results.append(
            Candidate(
                rule_id=OTHER_CONTACT_RULE_ID,
                subject=f"{pin}: reviewed connector contact has no net or open disposition",
                message=(
                    f"The source-matched interface maps this generic contact to "
                    f"{mapped.interface_signal} with role=other, but the native netlist assigns "
                    "it to no net and the map has no intentional-open reason. Review its role "
                    "and decide whether it needs a connection or is intentionally unused. This "
                    "check does not infer the contact's electrical function or select a net."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("other",),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "assigned_nets": (),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def mapped_other_contacts_on_named_rails(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review generic contacts mapped as other when assigned to a named rail-like net."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            mapped.role != "other"
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or len(mapped.nets) != 1
        ):
            continue

        net_name = mapped.nets[0]
        label_clue = named_rail_role_clue(net_name)
        if label_clue is None:
            continue

        results.append(
            Candidate(
                rule_id=OTHER_NAMED_RAIL_RULE_ID,
                subject=f"{pin}: generic other contact is assigned to {label_clue} net {net_name}",
                message=(
                    f"The source-matched interface maps this generic contact to "
                    f"{mapped.interface_signal} with role=other, while its single native net "
                    f"label ({net_name}) is recognized as {label_clue}. Review the pin map "
                    "and assignment: a label is a review clue and does not prove the pin's "
                    "electrical role, required connection, voltage, or intended reference. "
                    "This check does not choose a net, require separate contacts to share a "
                    "net, or establish PCB copper continuity."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("other",),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "assigned_nets": (net_name,),
                    "net_label_role_clue": (f"{label_clue} label",),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def mapped_supply_contacts_on_return_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review generic mapped supply contacts assigned to return-labeled nets."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            mapped.role != "supply"
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or len(mapped.nets) != 1
        ):
            continue

        net_name = mapped.nets[0]
        if named_rail_role_clue(net_name) != "return-like":
            continue

        results.append(
            Candidate(
                rule_id=SUPPLY_RETURN_NET_RULE_ID,
                subject=f"{pin}: mapped supply contact is assigned to return-like net {net_name}",
                message=(
                    f"The source-matched interface maps this generic contact to "
                    f"{mapped.interface_signal} as a supply contact, while its single native "
                    f"net label ({net_name}) is recognized as return-like. Review the pin map, "
                    "voltage domain, and net assignment. The map and label are review clues; "
                    "they do not prove electrical potential, an actual mismatch, or required "
                    "connectivity, and this check does not establish PCB copper continuity."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("supply",),
                    "interface_voltage_domain": (str(mapped.voltage_domain or "<missing>"),),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "assigned_nets": (net_name,),
                    "net_label_role_clue": ("return-like label",),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def mapped_signal_contacts_on_named_rails(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review generic mapped signal contacts assigned to named rail-like nets."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            mapped.role != "signal"
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or len(mapped.nets) != 1
        ):
            continue

        net_name = mapped.nets[0]
        label_clue = named_rail_role_clue(net_name)
        if label_clue is None:
            continue

        results.append(
            Candidate(
                rule_id=SIGNAL_NAMED_RAIL_RULE_ID,
                subject=f"{pin}: mapped signal contact is assigned to {label_clue} net {net_name}",
                message=(
                    f"The source-matched interface maps this generic contact to "
                    f"{mapped.interface_signal} as a signal contact, while its single native "
                    f"net label ({net_name}) is recognized as {label_clue}. Review whether the "
                    "signal is intentionally tied to this rail or the map/assignment needs a "
                    "correction. The map and label do not prove electrical potential or an "
                    "actual defect; this check does not assess intervening components or PCB "
                    "copper continuity."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("signal",),
                    "interface_voltage_domain": (str(mapped.voltage_domain or "<missing>"),),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "assigned_nets": (net_name,),
                    "net_label_role_clue": (f"{label_clue} label",),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def mapped_shield_contacts_on_return_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review mapped connector shields assigned to return-labeled nets."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            mapped.role != "shield"
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or len(mapped.nets) != 1
        ):
            continue

        net_name = mapped.nets[0]
        if named_rail_role_clue(net_name) != "return-like":
            continue

        results.append(
            Candidate(
                rule_id=SHIELD_RETURN_NET_RULE_ID,
                subject=f"{pin}: mapped shield contact is assigned to return-like net {net_name}",
                message=(
                    f"The source-matched interface maps this contact to "
                    f"{mapped.interface_signal} as a shield, while its single native net label "
                    f"({net_name}) is recognized as return-like. Review whether bonding this "
                    "connecting this shield to the return-labeled net is intentional. The "
                    "interface map and net label do not prove a required bond or electrical "
                    "relationship, and this check does "
                    "not establish PCB copper continuity, external wiring, or chassis bonding."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("shield",),
                    "interface_voltage_domain": (str(mapped.voltage_domain or "<missing>"),),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "assigned_nets": (net_name,),
                    "net_label_role_clue": ("return-like label",),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)


def mapped_shield_contacts_on_supply_rails(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review mapped connector shields assigned to named supply-like rails."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    results: list[Candidate] = []
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            mapped.role != "shield"
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or len(mapped.nets) != 1
        ):
            continue

        net_name = mapped.nets[0]
        if named_rail_role_clue(net_name) != "supply-like":
            continue

        results.append(
            Candidate(
                rule_id=SHIELD_SUPPLY_RAIL_RULE_ID,
                subject=f"{pin}: mapped shield contact is assigned to supply-like net {net_name}",
                message=(
                    f"The source-matched interface maps this contact to "
                    f"{mapped.interface_signal} as a shield, while its single native net label "
                    f"({net_name}) is recognized as supply-like. Review whether the shield is "
                    "intentionally assigned to this rail or the interface map/assignment needs "
                    "correction. The map and label do not prove actual voltage or a wiring "
                    "defect; this check does not prescribe shield bonding or establish PCB "
                    "copper continuity."
                ),
                evidence={
                    "component_pin": (pin,),
                    "interface_pin_number": (str(mapped.interface_pin_number),),
                    "interface_signal": (str(mapped.interface_signal),),
                    "interface_role": ("shield",),
                    "interface_voltage_domain": (str(mapped.voltage_domain or "<missing>"),),
                    "native_pin_function": (mapped.symbol_function or "<missing>",),
                    "assigned_nets": (net_name,),
                    "net_label_role_clue": ("supply-like label",),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(results)
