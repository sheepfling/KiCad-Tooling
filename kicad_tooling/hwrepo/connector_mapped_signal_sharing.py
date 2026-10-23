"""Review distinct mapped connector signals assigned to one native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_signals_share_net"


def mapped_distinct_signal_contacts_sharing_net(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review distinct mapped signal names that share one schematic net."""
    if coverage is None or coverage.status != "COMPLETE":
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    contacts_by_reference_and_net: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference, separator, _pin_number = pin.rpartition(".")
        if (
            not separator
            or mapped.role != "signal"
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or not pin_function_is_generic(mapped.symbol_function)
            or len(mapped.nets) != 1
        ):
            continue

        signal_name = mapped.interface_signal.strip()
        if not signal_name:
            continue
        contacts_by_reference_and_net[(reference, mapped.nets[0])].append((pin, signal_name))

    candidates: list[Candidate] = []
    for (reference, net_name), contacts in sorted(contacts_by_reference_and_net.items()):
        signals_by_key: dict[str, str] = {}
        for _pin, signal_name in contacts:
            key = signal_name.casefold()
            current = signals_by_key.get(key)
            if current is None or signal_name < current:
                signals_by_key[key] = signal_name
        signal_names = tuple(
            sorted(signals_by_key.values(), key=lambda name: (name.casefold(), name))
        )
        if len(signal_names) < 2:
            continue

        pins = tuple(sorted(pin for pin, _signal_name in contacts))
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{reference}: distinct mapped signals {', '.join(signal_names)} "
                    f"share native net {net_name}"
                ),
                message=(
                    f"The source-matched connector map names {', '.join(signal_names)} as distinct "
                    f"signal contacts, while the native netlist assigns them to the same net "
                    f"({net_name}). Review whether the signals are intentionally tied or whether "
                    "the map or net assignment needs correction. Distinct map names do not prove "
                    "that the signals must be electrically separate; this review does not infer "
                    "signal direction, voltage, or PCB copper continuity."
                ),
                evidence={
                    "component_reference": (reference,),
                    "component_pin": pins,
                    "interface_signal": signal_names,
                    "interface_role": ("signal",),
                    "assigned_nets": (net_name,),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(candidates)
