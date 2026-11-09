"""Review a fitted IC whose native I2S bit clock and word select share a net."""

from __future__ import annotations

from .design_lint_i2s_same_net_candidate_evidence import (
    I2sClockFrameSameNetCandidate,
    I2sClockFrameSameNetEvidence,
)
from .i2s_endpoint_inventory import I2sEndpointInventory
from .netlist_contract_models import NetlistContract


def i2s_clock_frame_same_net_candidates(
    observed: NetlistContract,
) -> tuple[I2sClockFrameSameNetCandidate, ...]:
    """Find complete fitted-IC I2S role pairs assigned to one exact native net.

    Native function names identify a bounded signal pair, not the interface's
    use or intended clocking. Incomplete, ambiguous, duplicated, or DNP
    endpoints are left unclassified; two output pins remain with ERC.
    """
    findings: list[I2sClockFrameSameNetCandidate] = []
    for endpoint in I2sEndpointInventory.from_netlist(observed).clock_frame_endpoints():
        if endpoint.bit_clock_net.casefold() != endpoint.word_select_net.casefold():
            continue
        if (
            endpoint.bit_clock_electrical_type.casefold() == "output"
            and endpoint.word_select_electrical_type.casefold() == "output"
        ):
            continue
        source_evidence = I2sClockFrameSameNetEvidence(observed=observed, endpoint=endpoint)
        findings.append(
            I2sClockFrameSameNetCandidate.from_source_evidence(
                source_evidence,
                subject=(
                    f"{endpoint.reference}: I2S bit clock {endpoint.bit_clock_pin} and word "
                    f"select {endpoint.word_select_pin} share {endpoint.bit_clock_net}"
                ),
                message=(
                    f"Fitted IC {endpoint.reference} has native I2S bit-clock pin "
                    f"{endpoint.bit_clock_pin} ({endpoint.bit_clock_function}) and word-select "
                    f"pin {endpoint.word_select_pin} ({endpoint.word_select_function}) assigned "
                    f"to the same schematic net ({endpoint.bit_clock_net}). Review whether "
                    "this is an intended alternate mode or an accidental pin assignment. The "
                    "native functions do not establish that this I2S interface is used or that "
                    "the project requires separate clocks."
                ),
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
