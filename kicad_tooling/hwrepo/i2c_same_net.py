"""Review fitted I2C SDA/SCL pin pairs that share one schematic net."""

from __future__ import annotations

from .design_lint_two_wire_same_net_candidate_evidence import (
    I2cSameNetEvidence,
    TwoWirePinEvidence,
    TwoWireSameNetCandidate,
)
from .design_lint_types import Candidate
from .i2c_signal_endpoints import i2c_signal_endpoints
from .netlist_contract_models import NetlistContract

RULE_ID = "bus.i2c_sda_scl_same_net"


def i2c_sda_scl_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted ICs with one uniquely assigned native SDA/SCL pair on one net.

    The check uses the bounded I2C function aliases shared by other I2C checks.
    It requires both role pins to occur in the exported component pin inventory
    and excludes ambiguous, open, DNP, and multi-port cases.
    """
    findings: list[Candidate] = []
    for endpoint in i2c_signal_endpoints(observed):
        if (
            endpoint.sda_net.casefold() != endpoint.scl_net.casefold()
            or endpoint.sda_net != endpoint.scl_net
        ):
            continue
        if endpoint.sda_type == endpoint.scl_type == "output":
            continue

        findings.append(
            TwoWireSameNetCandidate.from_source_evidence(
                I2cSameNetEvidence(
                    observed=observed,
                    reference=endpoint.reference,
                    sda=TwoWirePinEvidence.from_native_pin_map(observed, endpoint.sda_pin),
                    scl=TwoWirePinEvidence.from_native_pin_map(observed, endpoint.scl_pin),
                    net=endpoint.sda_net,
                ),
                subject=f"{endpoint.reference}: I2C SDA/SCL pins share {endpoint.sda_net}",
                message=(
                    f"The bounded native I2C SDA pin {endpoint.sda_pin} and SCL pin "
                    f"{endpoint.scl_pin} on {endpoint.reference} share one schematic net "
                    f"({endpoint.sda_net}). Review whether this "
                    "is intentional. Function names are clues only; this check does not prove "
                    "the part implements standard I2C or establish the intended topology."
                ),
            )
        )
    return tuple(findings)
