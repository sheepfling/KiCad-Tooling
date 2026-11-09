"""Review a fitted IC whose native SWDIO and SWCLK pins share one net."""

from __future__ import annotations

from .design_lint_swd_same_net_candidate_evidence import (
    SwdIoClockSameNetCandidate,
    SwdIoClockSameNetEvidence,
)
from .netlist_contract_models import NetlistContract
from .swd_endpoint_inventory import SwdEndpointInventory


def swdio_swclk_same_net_candidates(
    observed: NetlistContract,
) -> tuple[SwdIoClockSameNetCandidate, ...]:
    """Find complete fitted-IC SWD pairs whose two role pins share one native net.

    Native pin functions establish the roles; they do not establish whether the
    interface is used. Incomplete, ambiguous, duplicated, or DNP endpoints are
    left unclassified.
    """
    findings: list[SwdIoClockSameNetCandidate] = []
    inventory = SwdEndpointInventory.from_netlist(observed)
    for endpoint in inventory.endpoint_pairs(include_same_net=True):
        if endpoint.swdio_net.casefold() != endpoint.swclk_net.casefold():
            continue
        if (
            endpoint.swdio_electrical_type.casefold() == "output"
            and endpoint.swclk_electrical_type.casefold() == "output"
        ):
            continue
        source_evidence = SwdIoClockSameNetEvidence(observed=observed, endpoint=endpoint)
        findings.append(
            SwdIoClockSameNetCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{endpoint.reference}: SWDIO {endpoint.swdio_pin} and SWCLK "
                    f"{endpoint.swclk_pin} share {endpoint.swdio_net}"
                ),
                message=(
                    f"Fitted IC {endpoint.reference} has native SWDIO pin "
                    f"{endpoint.swdio_pin} ({endpoint.swdio_function}) and native SWCLK pin "
                    f"{endpoint.swclk_pin} ({endpoint.swclk_function}) assigned to the same "
                    f"schematic net ({endpoint.swdio_net}). Review whether this is an intended "
                    "single-net mode or an accidental pin assignment. The pin functions do not "
                    "establish that this SWD interface is used or that a debug connector exists."
                ),
            )
        )
    return tuple(
        sorted(
            findings,
            key=lambda item: (item.subject.casefold(), item.subject),
        )
    )
