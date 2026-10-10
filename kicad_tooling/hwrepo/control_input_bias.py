"""Resolve control-input heuristic candidates against authored bias contracts."""

from __future__ import annotations

from typing import Literal

from .control_input_checks import control_input_checks
from .control_input_inventory import connected_control_inputs_without_visible_rail_resistor
from .models import (
    ControlExternalBiasRequirement,
    ControlInputBiasHeuristicCoverage,
    ControlInputBiasHeuristicEntry,
    ControlInputsAnalysis,
    ControlInternalBiasRequirement,
    ControlNoBiasRequirement,
    NetlistContract,
)


def control_input_bias_heuristic_coverage(
    observed: NetlistContract,
    *,
    netlist_sha256: str,
    source_path: str | None,
    source_sha256: str | None,
    state: str,
    spec: ControlInputsAnalysis | None = None,
) -> ControlInputBiasHeuristicCoverage:
    """Resolve heuristic prompts only with exact, passing project-authored requirements."""
    gaps = connected_control_inputs_without_visible_rail_resistor(observed)
    entries: list[ControlInputBiasHeuristicEntry] = []
    if spec is None:
        reason = {
            "pending": "Project control-input review is pending; no bias decision can resolve this prompt.",
            "not_applicable": "The project marks control-input analysis not applicable; no net-specific bias decision resolves this prompt.",
        }.get(state, "No project-authored control-input requirement covers this candidate.")
        entries.extend(
            ControlInputBiasHeuristicEntry(
                net=gap.net,
                control_pins=tuple(item.pin for item in gap.controls),
                status="OPEN",
                issues=(reason,),
            )
            for gap in gaps
        )
        coverage_status: Literal[
            "NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"
        ]
        if state == "pending":
            coverage_status = "PENDING"
        elif state == "not_applicable":
            coverage_status = "NOT_APPLICABLE"
        elif state == "blocked":
            coverage_status = "BLOCKED"
        else:
            coverage_status = "NOT_CONFIGURED"
        return ControlInputBiasHeuristicCoverage(
            status=coverage_status,
            source_path=source_path,
            source_sha256=source_sha256,
            netlist_sha256=netlist_sha256 if gaps else None,
            entries=tuple(entries),
            issue=(
                "Could not load the project control-input contract." if state == "blocked" else None
            ),
        )

    checks_by_id = {item.id: item for item in control_input_checks(spec, observed)}
    for gap in gaps:
        candidate_pins = {item.pin.casefold() for item in gap.controls}
        matching = [
            signal
            for signal in spec.signals
            if signal.signal_net.casefold() == gap.net.casefold()
            and candidate_pins
            <= {
                endpoint.pin.casefold()
                for endpoint in signal.endpoints
                if endpoint.role == "controlled_input"
            }
        ]
        if len(matching) != 1:
            issue = (
                "No unique control-input requirement names this exact signal net and every detected input pin."
                if not matching
                else "More than one control-input requirement matches this signal net and input set."
            )
            entries.append(
                ControlInputBiasHeuristicEntry(
                    net=gap.net,
                    control_pins=tuple(item.pin for item in gap.controls),
                    status="OPEN",
                    issues=(issue,),
                )
            )
            continue

        signal = matching[0]
        prefix = f"control-inputs/{signal.id}/"
        relevant = {
            key.rsplit("/", maxsplit=1)[-1]: value
            for key, value in checks_by_id.items()
            if key.startswith(prefix)
        }
        issues = tuple(
            f"{name}: {check.detail}"
            for name, check in sorted(relevant.items())
            if (name == "endpoints" and check.status != "PASS")
            or (name == "drivers" and check.status != "PASS")
            or (name == "bias" and check.status not in {"PASS", "NOT_APPLICABLE"})
        )
        bias = signal.bias
        bias_reason = (
            bias.reason
            if isinstance(
                bias,
                (
                    ControlInternalBiasRequirement,
                    ControlExternalBiasRequirement,
                    ControlNoBiasRequirement,
                ),
            )
            else None
        )
        entries.append(
            ControlInputBiasHeuristicEntry(
                net=gap.net,
                control_pins=tuple(item.pin for item in gap.controls),
                signal_id=signal.id,
                bias_mode=bias.mode,
                bias_basis=bias.basis,
                bias_reason=bias_reason,
                status="OPEN" if issues else "COVERED",
                issues=issues,
            )
        )

    status: Literal["OPEN", "COMPLETE"] = (
        "OPEN" if any(item.status == "OPEN" for item in entries) else "COMPLETE"
    )
    return ControlInputBiasHeuristicCoverage(
        status=status,
        source_path=source_path,
        source_sha256=source_sha256,
        netlist_sha256=netlist_sha256 if gaps else None,
        entries=tuple(entries),
    )
