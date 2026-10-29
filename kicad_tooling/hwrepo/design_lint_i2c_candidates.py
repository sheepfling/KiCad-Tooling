"""Translate I2C pull-up and address-map review observations."""

from __future__ import annotations

from collections.abc import Sequence

from .design_lint_types import Candidate
from .i2c_address_models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cResponderAddressCoverageEntry,
)
from .i2c_addressing import format_i2c_address, unmapped_i2c_responders
from .i2c_peer_reference_scan import I2cPeerReferenceScan, scan_i2c_peer_references
from .i2c_pullup_inputs import I2cPullupSnifferInput
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import NetlistContract


def _i2c_address_evidence(
    entries: Sequence[I2cResponderAddressCoverageEntry],
) -> dict[str, tuple[str, ...]]:
    evidence: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        evidence[f"{entry.reference}.symbol"] = (
            f"expected {entry.expected_symbol}; observed {entry.observed_symbol or 'unknown'}",
        )
        evidence[f"{entry.reference}.SDA"] = (
            f"{entry.sda_pin} -> {', '.join(entry.sda_nets) or 'unconnected'}",
        )
        evidence[f"{entry.reference}.SCL"] = (
            f"{entry.scl_pin} -> {', '.join(entry.scl_nets) or 'unconnected'}",
        )
        address_evidence = (
            f"expected {format_i2c_address(entry.expected_address)}; "
            f"observed {format_i2c_address(entry.observed_address)}"
        )
        evidence[f"{entry.reference}.address"] = (address_evidence,)
        for bit in entry.address_bits:
            bit_evidence = (
                f"{bit.pin} function {bit.observed_function or 'unknown'}; "
                f"nets {', '.join(bit.nets) or 'unconnected'}; "
                f"resolved {bit.resolved_value if bit.resolved_value is not None else 'unknown'}"
            )
            evidence[f"{entry.reference}.bit{bit.bit}"] = (bit_evidence,)
        evidence[f"{entry.reference}.basis"] = (entry.basis,)
    return evidence


def i2c_pullup_candidates(
    observed: NetlistContract,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
) -> tuple[Candidate, ...]:
    """Compatibility adapter for the explicitly typed I2C pull-up theme input."""
    from .design_lint_i2c_pullup_candidates import i2c_pullup_theme_candidates

    return i2c_pullup_theme_candidates(
        I2cPullupSnifferInput.from_legacy_arguments(observed, i2c_pullup_heuristic_coverage)
    )


def i2c_address_candidates(
    i2c_address_coverage: I2cAddressCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Build I2C address mismatch and collision prompts from declared coverage."""
    found: list[Candidate] = []
    if i2c_address_coverage is not None:
        for entry in i2c_address_coverage.entries:
            if (
                entry.status == "COMPLETE"
                and entry.mode == "strapped"
                and entry.expected_address != entry.observed_address
            ):
                found.append(
                    Candidate(
                        rule_id="bus.i2c_address_mismatch",
                        subject=(
                            f"{entry.reference} on {entry.segment_id}: "
                            f"{format_i2c_address(entry.observed_address)}"
                        ),
                        message=(
                            "Source-bound address-pin nets resolve to a different static I2C "
                            "address than the project map declares. Review the strap wiring, "
                            "device profile, or approved address."
                        ),
                        evidence={
                            "segment": (entry.segment_id,),
                            **_i2c_address_evidence((entry,)),
                        },
                    )
                )
        address_groups: dict[tuple[str, int], list[I2cResponderAddressCoverageEntry]] = {}
        for entry in i2c_address_coverage.entries:
            if entry.status == "COMPLETE" and entry.observed_address is not None:
                address_groups.setdefault((entry.segment_id, entry.observed_address), []).append(
                    entry
                )
        for (segment_id, address), entries in sorted(address_groups.items()):
            if len(entries) < 2:
                continue
            references = tuple(sorted(entry.reference for entry in entries))
            found.append(
                Candidate(
                    rule_id="bus.i2c_address_collision",
                    subject=f"{segment_id}: {', '.join(references)} at {format_i2c_address(address)}",
                    message=(
                        "Multiple fitted responders on this declared I2C segment resolve to the "
                        "same static address. Review the address map or any mux isolation not "
                        "represented by the declared segment."
                    ),
                    evidence={
                        "segment": (segment_id,),
                        "address": (format_i2c_address(address),),
                        **_i2c_address_evidence(entries),
                    },
                )
            )
    return tuple(found)


def i2c_responder_coverage_candidates(
    observed: NetlistContract,
    i2c_address_map: I2cAddressMap | None,
) -> tuple[Candidate, ...]:
    """Prompt review of I2C responders absent from the project address map."""
    found: list[Candidate] = []
    for responder in unmapped_i2c_responders(observed, i2c_address_map):
        net_pairs = tuple(f"{sda} / {scl}" for sda, scl in responder.signal_pairs)
        has_map = i2c_address_map is not None
        found.append(
            Candidate(
                rule_id="bus.i2c_unmapped_responder",
                subject=f"{responder.reference}: I2C address-map coverage",
                message=(
                    f"{responder.reference} has assigned native SDA/SCL pin functions but "
                    + (
                        "is not listed as a responder in the project address map. "
                        if has_map
                        else "no project I2C address map is configured. "
                    )
                    + "Review whether it is a static or dynamic responder, or intentionally "
                    "outside address checking."
                ),
                evidence={
                    "SDA_pins": responder.sda_pins,
                    "SCL_pins": responder.scl_pins,
                    "assigned_net_pairs": net_pairs,
                    "address_map": (("configured",) if has_map else ("not_configured",)),
                },
            )
        )
    return tuple(found)


def i2c_peer_reference_candidates(
    observed: NetlistContract,
    scan: I2cPeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
) -> tuple[Candidate, ...]:
    """Build split-reference prompts not already covered by component-peer review."""
    found: list[Candidate] = []
    reference_scan = scan or scan_i2c_peer_references(observed)
    component_reference_assignments: dict[str, set[str]] = {}
    for finding in component_peer_findings:
        if (
            finding.rule_id != "component.peer_power_pin_assignment_divergence"
            or finding.evidence.get("peer_role") != ("ground/return",)
        ):
            continue
        for pin, nets in finding.evidence.items():
            if "." not in pin or len(nets) != 1:
                continue
            component_reference_assignments.setdefault(pin.casefold(), set()).add(
                nets[0].casefold()
            )

    for bus in reference_scan.reviews:
        covered_references: dict[str, set[str]] = {}
        for endpoint in bus.endpoints:
            for pin in endpoint.reference_pins:
                if pin.net.casefold() in component_reference_assignments.get(
                    pin.pin.casefold(), set()
                ):
                    covered_references.setdefault(endpoint.reference.casefold(), set()).add(
                        pin.net.casefold()
                    )
        if (
            len(covered_references) == len(bus.endpoints)
            and len({net for nets in covered_references.values() for net in nets}) > 1
        ):
            continue

        references = tuple(item.reference for item in bus.endpoints)
        assignments = tuple(
            f"{item.reference}: {item.sda_pin} on {item.sda_net}; "
            f"{item.scl_pin} on {item.scl_net}; "
            + (
                f"{', '.join(pin.pin for pin in item.reference_pins)} on {item.reference_net}"
                if item.reference_net is not None
                else "reference assignment incomplete"
            )
            for item in bus.endpoints
        )
        evidence = {
            "SDA": (bus.sda_net,),
            "SCL": (bus.scl_net,),
            "participants": references,
            "signal_pins": tuple(
                pin for item in bus.endpoints for pin in (item.sda_pin, item.scl_pin)
            ),
            "reference_assignments": assignments,
        }
        if bus.incomplete_references:
            evidence["incomplete_reference_evidence"] = bus.incomplete_references
        found.append(
            Candidate(
                rule_id="bus.i2c_peer_reference_review",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}: {', '.join(references)}",
                message=(
                    "Fitted ICs share the same native I2C SDA and SCL nets, and at least two "
                    "peers have explicit reference pins on separate nets. Review the approved reference or bond "
                    "policy; this heuristic does not require common grounding or prove a "
                    "physical return path."
                ),
                evidence=evidence,
            )
        )
    return tuple(found)
