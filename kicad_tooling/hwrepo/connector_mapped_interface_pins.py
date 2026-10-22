"""Review source-mapped connector signal pins with no schematic net."""

from __future__ import annotations

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_interface_signal_unassigned"


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
