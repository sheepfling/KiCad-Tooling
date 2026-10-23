"""Review source-mapped connector supply domains that share a native net."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_types import Candidate
from .models import NetlistContract


def mapped_supply_domains_shared_net_candidates(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Review distinct mapped supply domains assigned to the same exact net.

    Only unambiguous pins from complete, source-matched connector entries are
    considered. Domain names classify authored map entries; they do not imply
    that the named domains have different voltages or must remain separate.
    """
    if coverage is None:
        return ()

    mapped_pins = source_matched_connector_pin_evidence(observed, coverage)
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    domains_by_net: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for pin, mapped in sorted(mapped_pins.items()):
        reference = pin.rsplit(".", 1)[0]
        if (
            reference.casefold() in unpopulated
            or mapped.role != "supply"
            or mapped.voltage_domain is None
            or mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
        ):
            continue
        domains_by_net[mapped.nets[0]][str(mapped.voltage_domain)].append(pin)

    candidates: list[Candidate] = []
    for net, domains in sorted(domains_by_net.items()):
        if len(domains) < 2:
            continue
        ordered_domains = tuple(sorted(domains))
        ordered_pins = tuple((domain, tuple(sorted(domains[domain]))) for domain in ordered_domains)
        evidence: dict[str, tuple[str, ...]] = {
            "native_shared_net": (net,),
            "reviewed_voltage_domains": ordered_domains,
            "mapped_supply_assignments": tuple(
                f"{pin}={net}; voltage_domain={domain}"
                for domain, pins in ordered_pins
                for pin in pins
            ),
            "role_classification_sources": tuple(
                (
                    f"{pin}: source-matched project interface role=supply; "
                    f"voltage_domain={domain}; signal={mapped_pins[pin].interface_signal}; "
                    f"native function={mapped_pins[pin].symbol_function or '<unnamed>'}"
                )
                for domain, pins in ordered_pins
                for pin in pins
            ),
            "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
        }
        if coverage.interface_catalog_path is not None:
            evidence["interface_catalog_path"] = (str(coverage.interface_catalog_path),)
        evidence.update({pin: (net,) for _, pins in ordered_pins for pin in pins})
        candidates.append(
            Candidate(
                rule_id="connector.mapped_supply_domains_share_net",
                subject=f"{net}: mapped connector supply domains share one native net",
                message=(
                    "Complete, source-matched project interface entries classify these connector "
                    "pins as supplies in distinct voltage_domain groups assigned to the same "
                    "schematic net. Review whether the entries should share this node or whether "
                    "the mapping needs clarification. Distinct domain identifiers do not establish "
                    "different nominal voltages or electrical incompatibility, and this heuristic "
                    "does not prove a physical board fault."
                ),
                evidence=evidence,
            )
        )
    return tuple(candidates)
