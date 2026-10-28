"""Shared review of expected identity and native evidence for one PCB pad."""

from __future__ import annotations

from .pcb_connectivity_observations import PcbPadConnectivityObservation


def pcb_pad_endpoint_issues(
    pad: PcbPadConnectivityObservation | None,
    *,
    reference: str,
    expected_footprint: str,
    expected_net: str,
    role: str,
) -> list[str]:
    """Compare a mapped PCB endpoint with its observed footprint, net, and DNP state."""
    if pad is None:
        return [f"{role} pad {reference} is absent from the native PCB inventory"]
    issues: list[str] = []
    if pad.footprint != expected_footprint:
        issues.append(
            f"{role} {reference} footprint is {pad.footprint!r}; expected {expected_footprint!r}"
        )
    if pad.net != expected_net:
        issues.append(f"{role} {reference} net is {pad.net!r}; expected {expected_net!r}")
    if pad.dnp:
        issues.append(f"{role} {reference} is marked do-not-populate")
    return issues
