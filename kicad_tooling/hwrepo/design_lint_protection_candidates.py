"""Build protection-coverage review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import ExternalProtectionCoverageReport


def protection_candidates(
    external_protection_coverage: ExternalProtectionCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if external_protection_coverage is not None:
        for entry in external_protection_coverage.entries:
            if entry.status == "UNDECLARED":
                found.append(
                    Candidate(
                        rule_id="protection.unreviewed_interface_pin",
                        subject=(
                            f"{entry.connector_pin}: "
                            f"{entry.interface_signal or 'external interface signal'}"
                        ),
                        message=(
                            "This project-reviewed connector pin has no protection applicability "
                            "decision. Map the required protector channel or record a reasoned "
                            "not-required decision; the rule does not assume protection is needed."
                        ),
                        evidence={
                            "connector": (entry.connector_reference,),
                            "signal": (entry.interface_signal or "unknown",),
                            "net": entry.observed_nets,
                        },
                    )
                )
            elif entry.status in {"INCOMPLETE", "STALE"}:
                found.append(
                    Candidate(
                        rule_id="protection.mapped_device_mismatch",
                        subject=f"{entry.connector_pin}: mapped protection requirement",
                        message=(
                            "The project-mapped protection identity or pin/net assignment differs "
                            "from source-bound native evidence. Review the connector map and device "
                            "pinout."
                        ),
                        evidence={
                            "connector": (entry.connector_reference,),
                            "signal": (entry.interface_signal or "unknown",),
                            "expected_net": (entry.signal_net or "<not declared>",),
                            "observed_nets": entry.observed_nets,
                            "protection_devices": entry.device_references,
                            "issues": entry.issues,
                        },
                    )
                )
    return tuple(found)
