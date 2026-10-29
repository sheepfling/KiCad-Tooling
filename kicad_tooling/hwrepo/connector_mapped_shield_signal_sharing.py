"""Review mapped connector shields sharing a net with mapped signal contacts."""

from __future__ import annotations

from collections import defaultdict

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.mapped_shield_signal_share_net"


def mapped_shields_sharing_signal_nets(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Prompt when a current, complete connector map puts shield and signal on one net."""
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    by_net: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(
        lambda: {"shield": [], "signal": []}
    )
    for pin, mapped in sorted(source_matched_connector_pin_evidence(observed, coverage).items()):
        reference, separator, _pin_number = pin.rpartition(".")
        if (
            not separator
            or mapped.role not in {"shield", "signal"}
            or mapped.unconnected_reason is not None
            or reference.casefold() in dnp_references
            or len(mapped.nets) != 1
        ):
            continue
        by_net[mapped.nets[0]][mapped.role].append((pin, mapped.interface_signal))

    candidates: list[Candidate] = []
    for net_name, roles in sorted(by_net.items()):
        shields = roles["shield"]
        signals = roles["signal"]
        if not shields or not signals:
            continue
        shield_pins = tuple(sorted(pin for pin, _signal in shields))
        signal_pins = tuple(sorted(pin for pin, _signal in signals))
        shield_names = tuple(sorted({signal for _pin, signal in shields}, key=str.casefold))
        signal_names = tuple(sorted({signal for _pin, signal in signals}, key=str.casefold))
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"mapped shield contacts {', '.join(shield_pins)} and signal contacts "
                    f"{', '.join(signal_pins)} share native net {net_name}"
                ),
                message=(
                    f"The source-matched connector map identifies {', '.join(shield_names)} as "
                    f"shield contacts and {', '.join(signal_names)} as signal contacts, while "
                    f"the native netlist assigns both roles to {net_name}. Review whether this "
                    "direct connection is intentional. Shield bonding can be valid, but this "
                    "heuristic does not decide the intended bond, inspect intervening circuitry, "
                    "or establish PCB copper continuity or external chassis bonding."
                ),
                evidence={
                    "shield_component_pin": shield_pins,
                    "shield_interface_signal": shield_names,
                    "signal_component_pin": signal_pins,
                    "signal_interface_signal": signal_names,
                    "assigned_net": (net_name,),
                    "interface_catalog_sha256": (str(coverage.interface_catalog_sha256),),
                },
            )
        )
    return tuple(candidates)
