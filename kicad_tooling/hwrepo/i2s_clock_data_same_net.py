"""Review a fitted IC whose native I2S bit clock and serial data share a net."""

from __future__ import annotations

from .design_lint_i2s_clock_data_candidate_evidence import (
    I2sClockDataSameNetCandidate,
    I2sClockDataSameNetEvidence,
)
from .i2s_endpoint_inventory import I2sEndpointInventory
from .netlist_contract_models import NetlistContract


def i2s_clock_data_same_net_candidates(
    observed: NetlistContract,
) -> tuple[I2sClockDataSameNetCandidate, ...]:
    """Find fitted-IC I2S bit-clock/data roles on one exact native net.

    The bounded native function names are candidate evidence, not proof that
    the device uses I2S. Incomplete, ambiguous, duplicated, open, multiply
    assigned, or DNP endpoints remain unclassified; two output pins remain
    with ERC.
    """
    findings: list[I2sClockDataSameNetCandidate] = []
    for endpoint in I2sEndpointInventory.from_netlist(observed).clock_data_endpoints():
        if endpoint.bit_clock_net.casefold() != endpoint.data_net.casefold():
            continue
        if (
            endpoint.bit_clock_electrical_type.casefold() == "output"
            and endpoint.data_electrical_type.casefold() == "output"
        ):
            continue
        source_evidence = I2sClockDataSameNetEvidence(observed=observed, endpoint=endpoint)
        findings.append(
            I2sClockDataSameNetCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{endpoint.reference}: I2S bit clock {endpoint.bit_clock_pin} and serial "
                    f"data {endpoint.data_pin} share {endpoint.bit_clock_net}"
                ),
                message=(
                    f"Fitted IC {endpoint.reference} has native I2S bit-clock pin "
                    f"{endpoint.bit_clock_pin} ({endpoint.bit_clock_function}) and serial-data "
                    f"pin {endpoint.data_pin} ({endpoint.data_function}) assigned to the same "
                    f"schematic net ({endpoint.bit_clock_net}). Review whether this is an "
                    "intended alternate mode or an accidental pin assignment. Native function "
                    "names do not establish that the project uses I2S or requires separate nets."
                ),
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
