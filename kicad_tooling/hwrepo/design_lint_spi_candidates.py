"""Translate SPI chip-select bias observations."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_bias_heuristics import spi_active_low_chip_selects_without_pullups
from .spi_peer_reference_scan import SpiPeerReferenceScan, scan_spi_peer_references


def spi_bias_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Build SPI chip-select bias review prompts."""
    found: list[Candidate] = []
    for gap in spi_active_low_chip_selects_without_pullups(observed):
        found.append(
            Candidate(
                rule_id="bus.spi_active_low_chip_select_without_pullup",
                subject=f"{gap.net}: active-low SPI chip-select bias",
                message=(
                    "This assigned active-low chip-select input has no visible 1 kΩ–100 kΩ "
                    "resistor path to a recognized positive rail. Review the device's reset-time "
                    "state and any internal or off-board bias; the pin name alone does not "
                    "establish that an external pull-up is required."
                ),
                evidence={
                    "net": (gap.net,),
                    "active_low_chip_select_pins": gap.pins,
                    "recognized_positive_rails": gap.positive_rails,
                    "visible_pullup_paths": (),
                },
            )
        )
    return tuple(found)


def spi_peer_reference_candidates(
    observed: NetlistContract,
    scan: SpiPeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
) -> tuple[Candidate, ...]:
    """Build split-reference prompts not already covered by component-peer review."""
    reference_scan = scan or scan_spi_peer_references(observed)
    component_reference_assignments: set[tuple[str, str]] = set()
    for finding in component_peer_findings:
        if (
            finding.rule_id != "component.peer_power_pin_assignment_divergence"
            or finding.evidence.get("peer_role") != ("ground/return",)
        ):
            continue
        for pin, nets in finding.evidence.items():
            if "." not in pin or len(nets) != 1:
                continue
            component_reference_assignments.add((pin.casefold(), nets[0].casefold()))

    found: list[Candidate] = []
    for bus in reference_scan.reviews:
        expected_assignments = {
            (pin.pin.casefold(), pin.net.casefold())
            for endpoint in bus.endpoints
            for pin in endpoint.reference_pins
        }
        if (
            bus.disposition == "SPLIT_REFERENCE_REVIEW"
            and expected_assignments
            and expected_assignments <= component_reference_assignments
            and len({net for _, net in expected_assignments}) > 1
        ):
            continue

        references = tuple(item.reference for item in bus.endpoints)
        assignments = tuple(
            f"{item.reference}: {item.clock_pin} on {item.clock_net}; "
            + (
                f"{', '.join(pin.pin for pin in item.reference_pins)} on {item.reference_net}"
                if item.reference_net is not None
                else "reference assignment incomplete"
            )
            for item in bus.endpoints
        )
        evidence = {
            "SCK": (bus.clock_net,),
            "participants": references,
            "clock_pins": tuple(item.clock_pin for item in bus.endpoints),
            "reference_assignments": assignments,
        }
        if bus.incomplete_references:
            evidence["incomplete_reference_evidence"] = bus.incomplete_references
        found.append(
            Candidate(
                rule_id="bus.spi_peer_reference_review",
                subject=f"SCK {bus.clock_net}: {', '.join(references)}",
                message=(
                    "Fitted ICs share the same native SPI clock net, and at least two peers "
                    "have explicit reference pins on separate nets. Review the approved "
                    "reference, isolation, or bond policy; this heuristic does not require "
                    "a common return or prove a physical return path."
                ),
                evidence=evidence,
            )
        )
    return tuple(found)
