"""Review repeated mapped signal contacts assigned to separate schematic nets."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_signals_split_nets"


def mapped_repeated_signal_contacts_split_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review repeated source-mapped signal contacts assigned to different nets."""
    if (
        coverage is None
        or coverage.status != "COMPLETE"
        or coverage.interface_catalog_sha256 is None
    ):
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    contacts_by_signal: dict[tuple[str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
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
        contacts_by_signal[(reference.casefold(), signal_name.casefold())].append(
            (reference, pin, signal_name, mapped.nets[0])
        )

    candidates: list[Candidate] = []
    for (_reference_key, _signal_key), contacts in sorted(contacts_by_signal.items()):
        pins = tuple(sorted({pin for _reference, pin, _signal_name, _net in contacts}))
        nets = tuple(sorted({net for _reference, _pin, _signal_name, net in contacts}))
        if len(pins) < 2 or len(nets) < 2:
            continue

        reference = min({item[0] for item in contacts}, key=lambda item: (item.casefold(), item))
        signal_name = min(
            {item[2] for item in contacts},
            key=lambda item: (item.casefold(), item),
        )
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{reference}: mapped signal {signal_name} spans native nets {', '.join(nets)}"
                ),
                message=(
                    f"The source-matched connector map assigns {signal_name} to contacts "
                    f"{', '.join(pins)}, while the native netlist places those contacts on "
                    f"different nets ({', '.join(nets)}). Review whether the contacts are "
                    "intentionally split, connected through an explicit circuit, or expected "
                    "to share one schematic net. A repeated map name is a review clue, not "
                    "proof that direct commoning is required, and this check does not establish "
                    "PCB copper continuity."
                ),
                evidence={
                    "component_reference": (reference,),
                    "component_pin": pins,
                    "interface_signal": (signal_name,),
                    "interface_role": ("signal",),
                    "assigned_nets": nets,
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(candidates)
