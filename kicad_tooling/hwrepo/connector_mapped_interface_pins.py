"""Review source-mapped connector signal pins with no schematic net."""

from __future__ import annotations

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_interface_signal_unassigned"
SHIELD_RULE_ID: DesignLintRuleId = "connector.mapped_interface_shield_unassigned"
POWER_CONTACT_RULE_ID: DesignLintRuleId = "connector.mapped_interface_power_contact_unassigned"
OTHER_CONTACT_RULE_ID: DesignLintRuleId = "connector.mapped_interface_other_unassigned"


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
