"""Deterministic, source-bound touch-pad to reference-copper clearance checks."""

from __future__ import annotations

import hashlib

from .contracts import model_json_bytes
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_pad_net_comparison import schematic_pad_net_assignments
from .pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageEntry,
    PcbTouchPadClearanceCoverageReport,
    PcbTouchPadClearanceMap,
    PcbTouchPadClearanceRequestSet,
)


def touch_pad_clearance_entries(
    authored: PcbTouchPadClearanceMap,
    snapshot: PcbConnectivitySnapshot,
    netlist: NetlistContract,
) -> tuple[PcbTouchPadClearanceCoverageEntry, ...]:
    """Match native geometry and schematic pad assignment to the authored requirement."""
    observations = {
        item.requirement_id.casefold(): item for item in snapshot.touch_pad_clearance_observations
    }
    schematic_nets = schematic_pad_net_assignments(netlist)
    request_set = PcbTouchPadClearanceRequestSet(requests=authored.requirements)
    expected_request_sha256 = hashlib.sha256(model_json_bytes(request_set)).hexdigest()
    entries: list[PcbTouchPadClearanceCoverageEntry] = []
    for requirement in sorted(authored.requirements, key=lambda item: item.id.casefold()):
        issues: list[str] = []
        observation = observations.get(requirement.id.casefold())
        reference, _separator, pin_number = requirement.pad.rpartition(".")
        schematic_net = schematic_nets.get((reference.casefold(), pin_number))
        if schematic_net is None:
            issues.append("source-bound native netlist has no assigned schematic net for this pad")
        elif schematic_net != requirement.expected_pad_net:
            issues.append("authored touch-pad net differs from the native schematic netlist")
        if snapshot.schema_version not in {"14", "15", "16", "17", "18"} or (
            "touch_pad_clearance_observations" not in snapshot.model_fields_set
        ):
            issues.append("exact native touch-pad clearance observations are unavailable")
        elif snapshot.touch_pad_clearance_requests_sha256 != expected_request_sha256:
            issues.append("native touch-pad request digest differs from the current authored map")
        elif observation is None:
            issues.append("native probe omitted this mapped touch-pad requirement")
        else:
            if (
                observation.pad.casefold() != requirement.pad.casefold()
                or observation.expected_pad_net != requirement.expected_pad_net
                or observation.reference_net != requirement.reference_net
                or observation.layer.casefold() != requirement.layer.casefold()
            ):
                issues.append("native touch-pad observation does not match the authored request")
            if observation.status != "MEASURED":
                issues.append(f"native touch-pad measurement is {observation.status}")
            if observation.observed_pad_net != requirement.expected_pad_net:
                issues.append("native touch-pad net differs from the independently authored net")
        measured = (
            None
            if observation is None or observation.status != "MEASURED"
            else observation.distance_nm
        )
        zone_uuid = (
            None
            if observation is None or observation.status != "MEASURED"
            else observation.closest_zone_uuid
        )
        complete = not issues and measured is not None and zone_uuid is not None
        if not complete and not issues:
            issues.append("native touch-pad measurement lacks an exact clearance or zone identity")
        entries.append(
            PcbTouchPadClearanceCoverageEntry(
                requirement_id=requirement.id,
                basis=authored.basis,
                pad=requirement.pad,
                expected_pad_net=requirement.expected_pad_net,
                schematic_pad_net=schematic_net,
                observed_pad_net=None if observation is None else observation.observed_pad_net,
                reference_net=requirement.reference_net,
                layer=requirement.layer,
                minimum_clearance_nm=requirement.minimum_clearance_nm,
                measured_clearance_nm=measured,
                closest_zone_uuid=zone_uuid,
                status="COMPLETE" if complete else "INCOMPLETE",
                issues=tuple(issues),
            )
        )
    return tuple(entries)


def touch_pad_clearance_violations(
    coverage: PcbTouchPadClearanceCoverageReport,
) -> tuple[Candidate, ...]:
    """Compatibility adapter for the typed touch-pad candidate owner."""
    from .design_lint_pcb_touch_pad_clearance_candidate_evidence import (
        touch_pad_clearance_violations as project_touch_pad_findings,
    )

    return project_touch_pad_findings(coverage)
