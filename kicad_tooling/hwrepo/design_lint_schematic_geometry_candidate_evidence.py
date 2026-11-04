"""Typed source projections for schematic geometry candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .schematic_geometry_types import (
    LabelNearWireEndpoint,
    PinTipOnWireInterior,
    SchematicGeometryScan,
    UnmarkedTJunction,
    UnmarkedWireCrossing,
    WireEndOnPinLine,
    WireEndpointNearPinTip,
)

_WIRE_END_ON_PIN_LINE: DesignLintRuleId = "schematic.wire_end_on_pin_line"
_PIN_TIP_ON_WIRE_INTERIOR: DesignLintRuleId = "schematic.pin_tip_on_wire_interior"
_WIRE_ENDPOINT_NEAR_PIN_TIP: DesignLintRuleId = "schematic.wire_endpoint_near_pin_tip"
_UNMARKED_WIRE_CROSSING: DesignLintRuleId = "schematic.unmarked_wire_crossing"
_UNMARKED_T_JUNCTION: DesignLintRuleId = "schematic.unmarked_t_junction"
_LABEL_NEAR_WIRE_ENDPOINT: DesignLintRuleId = "schematic.label_near_wire_endpoint"


@dataclass(frozen=True, slots=True)
class WireEndOnPinLineSource:
    """One endpoint-on-pin observation retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: WireEndOnPinLine

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.findings):
            raise ValueError("Pin-line finding must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class PinTipOnWireInteriorSource:
    """One pin-tip-on-wire observation retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: PinTipOnWireInterior

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.pin_tip_on_wire_interiors):
            raise ValueError("Pin-tip finding must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class WireEndpointNearPinTipSource:
    """One near-endpoint observation retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: WireEndpointNearPinTip

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.wire_endpoints_near_pin_tips):
            raise ValueError("Near-endpoint finding must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class UnmarkedWireCrossingSource:
    """One unmarked wire crossing retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: UnmarkedWireCrossing

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.unmarked_wire_crossings):
            raise ValueError("Crossing must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class UnmarkedTJunctionSource:
    """One unmarked wire T-junction retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: UnmarkedTJunction

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.unmarked_t_junctions):
            raise ValueError("T-junction must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class LabelNearWireEndpointSource:
    """One near-wire label observation retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: LabelNearWireEndpoint

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.labels_near_wire_endpoints):
            raise ValueError("Label finding must be an observation from its source scan")


SchematicPinGeometrySource = (
    WireEndOnPinLineSource | PinTipOnWireInteriorSource | WireEndpointNearPinTipSource
)
SchematicWireTopologySource = UnmarkedWireCrossingSource | UnmarkedTJunctionSource


def schematic_mm_box(box: tuple[float, float, float, float]) -> str:
    """Format an axis-aligned schematic box for the existing candidate wire fields."""
    return ",".join(f"{value:.6f}" for value in box)


def schematic_mm_segment(
    start: tuple[float, float], end: tuple[float, float]
) -> str:
    """Format a source segment in its established four-coordinate field."""
    return ",".join(f"{value:.6f}" for value in (*start, *end))


def schematic_geometry_evidence(
    scan: SchematicGeometryScan, sheet_instance_path: str
) -> dict[str, tuple[str, ...]]:
    """Bind geometry evidence to its exact sheet occurrence and source bytes."""
    binding = next(
        (item for item in scan.source_bindings if item.sheet_instance_path == sheet_instance_path),
        None,
    )
    source_path = scan.source_path if binding is None else binding.source_path
    source_sha256 = scan.source_sha256 if binding is None else binding.source_sha256
    return {
        "schematic": (source_path,),
        "schematic_sha256": (source_sha256,),
        "sheet_instance_path": (sheet_instance_path,),
        "sheet_path": (" / ".join(binding.sheet_path) if binding is not None else "",),
        "schematic_root": (scan.source_path,),
        "schematic_root_sha256": (scan.source_sha256,),
        "schematic_tree_sha256": (scan.source_tree_sha256 or scan.source_sha256,),
    }


def project_schematic_pin_geometry_evidence(
    source: SchematicPinGeometrySource,
) -> CandidateEvidenceProjection:
    """Project a retained pin/wire source observation into stable report fields."""
    scan = source.scan
    evidence = schematic_geometry_evidence(scan, source.finding.sheet_instance_path)
    evidence["kicad_version"] = (scan.kicad_version,)

    if isinstance(source, WireEndOnPinLineSource):
        item = source.finding
        endpoint_x, endpoint_y = item.wire_endpoint_mm
        evidence.update(
            {
                "symbol": (item.symbol_library_id,),
                "symbol_uuid": (item.symbol_uuid,),
                "pin": (f"{item.reference}.{item.pin_number}",),
                "pin_uuid": (item.pin_uuid or "<unavailable>",),
                "pin_tip_mm": (f"{item.pin_tip_mm[0]:.6f},{item.pin_tip_mm[1]:.6f}",),
                "wire_uuid": (item.wire_uuid,),
                "wire_endpoint_mm": (f"{endpoint_x:.6f},{endpoint_y:.6f}",),
                "distance_to_pin_tip_mm": (f"{item.distance_to_pin_tip_mm:.6f}",),
                "distance_along_pin_mm": (f"{item.distance_along_pin_mm:.6f}",),
            }
        )
        rule_id = _WIRE_END_ON_PIN_LINE
    elif isinstance(source, PinTipOnWireInteriorSource):
        item = source.finding
        start_x, start_y = item.wire_segment_start_mm
        end_x, end_y = item.wire_segment_end_mm
        evidence.update(
            {
                "symbol": (item.symbol_library_id,),
                "symbol_uuid": (item.symbol_uuid,),
                "pin": (f"{item.reference}.{item.pin_number}",),
                "pin_uuid": (item.pin_uuid or "<unavailable>",),
                "pin_tip_mm": (f"{item.pin_tip_mm[0]:.6f},{item.pin_tip_mm[1]:.6f}",),
                "wire_uuid": (item.wire_uuid,),
                "wire_segment_start_mm": (f"{start_x:.6f},{start_y:.6f}",),
                "wire_segment_end_mm": (f"{end_x:.6f},{end_y:.6f}",),
                "distance_to_wire_mm": (f"{item.distance_to_wire_mm:.6f}",),
            }
        )
        rule_id = _PIN_TIP_ON_WIRE_INTERIOR
    else:
        item = source.finding
        endpoint_x, endpoint_y = item.wire_endpoint_mm
        evidence.update(
            {
                "symbol": (item.symbol_library_id,),
                "symbol_uuid": (item.symbol_uuid,),
                "pin": (f"{item.reference}.{item.pin_number}",),
                "pin_uuid": (item.pin_uuid or "<unavailable>",),
                "pin_tip_mm": (f"{item.pin_tip_mm[0]:.6f},{item.pin_tip_mm[1]:.6f}",),
                "wire_uuid": (item.wire_uuid,),
                "wire_endpoint_mm": (f"{endpoint_x:.6f},{endpoint_y:.6f}",),
                "distance_to_pin_tip_mm": (f"{item.distance_to_pin_tip_mm:.6f}",),
            }
        )
        rule_id = _WIRE_ENDPOINT_NEAR_PIN_TIP

    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


def project_schematic_wire_topology_evidence(
    source: SchematicWireTopologySource,
) -> CandidateEvidenceProjection:
    """Project a retained crossing or T-junction into stable report fields."""
    scan = source.scan
    evidence = schematic_geometry_evidence(scan, source.finding.sheet_instance_path)
    evidence["kicad_version"] = (scan.kicad_version,)

    if isinstance(source, UnmarkedWireCrossingSource):
        finding = source.finding
        evidence.update(
            {
                "crossing_mm": (f"{finding.crossing_mm[0]:.6f},{finding.crossing_mm[1]:.6f}",),
                "wire_uuids": finding.wire_uuids,
            }
        )
        rule_id = _UNMARKED_WIRE_CROSSING
    else:
        finding = source.finding
        evidence.update(
            {
                "junction_mm": (f"{finding.junction_mm[0]:.6f},{finding.junction_mm[1]:.6f}",),
                "endpoint_wire_uuid": (finding.endpoint_wire_uuid,),
                "interior_wire_uuid": (finding.interior_wire_uuid,),
            }
        )
        rule_id = _UNMARKED_T_JUNCTION

    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


def project_schematic_label_endpoint_evidence(
    source: LabelNearWireEndpointSource,
) -> CandidateEvidenceProjection:
    """Project a retained label and its exact nearby wire endpoints."""
    scan = source.scan
    finding = source.finding
    evidence = schematic_geometry_evidence(scan, finding.sheet_instance_path)
    evidence.update(
        {
            "label_kind": (finding.label_kind,),
            "label_text": (finding.text,),
            "label_uuid": (finding.label_uuid,),
            "label_anchor_mm": (f"{finding.anchor_mm[0]:.6f},{finding.anchor_mm[1]:.6f}",),
            "near_wire_endpoints": tuple(
                f"{candidate.wire_uuid}@{candidate.wire_endpoint_mm[0]:.6f},"
                f"{candidate.wire_endpoint_mm[1]:.6f} ({candidate.distance_mm:.6f} mm)"
                for candidate in finding.candidates
            ),
            "kicad_version": (scan.kicad_version,),
        }
    )
    return CandidateEvidenceProjection(
        rule_id=_LABEL_NEAR_WIRE_ENDPOINT,
        evidence=evidence,
    )


def _candidate_text(source: SchematicPinGeometrySource) -> tuple[str, str]:
    if isinstance(source, WireEndOnPinLineSource):
        item = source.finding
        message = (
            "The native netlist marks this pin unconnected, while a wire endpoint lies along its "
            "transformed pin segment. Review the schematic and intended connection before "
            "changing the drawing."
        )
        return f"{item.reference}.{item.pin_number}: wire endpoint on pin segment", message
    if isinstance(source, PinTipOnWireInteriorSource):
        item = source.finding
        message = (
            "The native netlist marks this pin unconnected, although its tip lies on the interior "
            "of a wire segment. Review whether a junction or explicit connection is intended; "
            "the lint does not edit schematic geometry."
        )
        return f"{item.reference}.{item.pin_number}: pin tip on wire interior", message
    item = source.finding
    message = (
        "The native netlist marks this pin unconnected, and a wire endpoint is "
        f"{item.distance_to_pin_tip_mm:.3f} mm from its tip. Review this near miss and the native "
        "ERC finding; the lint does not connect or repair the schematic."
    )
    return f"{item.reference}.{item.pin_number}: wire endpoint near pin tip", message


def _wire_topology_candidate_text(source: SchematicWireTopologySource) -> tuple[str, str]:
    if isinstance(source, UnmarkedWireCrossingSource):
        finding = source.finding
        x, y = finding.crossing_mm
        message = (
            "Two wire interiors cross without a junction marker. Review whether the signals "
            "should connect; intentional unconnected crossings are valid and will also be "
            "reported."
        )
        return (
            f"unmarked orthogonal wire crossing at {x:.3f},{y:.3f} mm",
            message,
        )
    finding = source.finding
    x, y = finding.junction_mm
    message = (
        "A wire endpoint touches the interior of another wire without a junction marker. Review "
        "whether the branch should connect; this geometry hint does not join or repair nets."
    )
    return (
        f"unmarked T-junction at {x:.3f},{y:.3f} mm",
        message,
    )


def _label_endpoint_candidate_text(source: LabelNearWireEndpointSource) -> tuple[str, str]:
    finding = source.finding
    message = (
        "This label anchor misses nearby wire geometry but lies within the heuristic's 1.27 mm "
        "review radius of a wire endpoint. Review whether the label or wire should meet; the "
        "lint does not change the drawing."
    )
    return (
        f"{finding.label_kind} {finding.text!r}: near wire endpoint",
        message,
    )


@dataclass(frozen=True, slots=True)
class SchematicPinGeometryCandidate(Candidate):
    """A pin/wire candidate whose report fields match its retained scan record."""

    source_evidence: SchematicPinGeometrySource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicPinGeometrySource,
    ) -> SchematicPinGeometryCandidate:
        projection = project_schematic_pin_geometry_evidence(source_evidence)
        subject, message = _candidate_text(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_pin_geometry_evidence(self.source_evidence)
        subject, message = _candidate_text(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != subject
            or self.message != message
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic pin fields must match their typed source projection")


@dataclass(frozen=True, slots=True)
class SchematicWireTopologyCandidate(Candidate):
    """A wire-topology candidate whose report fields match its scan observation."""

    source_evidence: SchematicWireTopologySource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicWireTopologySource,
    ) -> SchematicWireTopologyCandidate:
        projection = project_schematic_wire_topology_evidence(source_evidence)
        subject, message = _wire_topology_candidate_text(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_wire_topology_evidence(self.source_evidence)
        subject, message = _wire_topology_candidate_text(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != subject
            or self.message != message
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic topology fields must match their typed source projection")


@dataclass(frozen=True, slots=True)
class SchematicLabelEndpointCandidate(Candidate):
    """A label candidate whose report fields match its retained scan record."""

    source_evidence: LabelNearWireEndpointSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: LabelNearWireEndpointSource,
    ) -> SchematicLabelEndpointCandidate:
        projection = project_schematic_label_endpoint_evidence(source_evidence)
        subject, message = _label_endpoint_candidate_text(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_label_endpoint_evidence(self.source_evidence)
        subject, message = _label_endpoint_candidate_text(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != subject
            or self.message != message
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic label fields must match their typed source projection")
