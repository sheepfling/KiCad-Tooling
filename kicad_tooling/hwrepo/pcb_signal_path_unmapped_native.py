"""Find exact native path-rule nets omitted from a PCB signal-path map."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .pcb_drc_conditions import native_exact_from_to_condition, native_exact_net_condition
from .pcb_drc_rule_parser import NativeRuleConstraint, drc_pad_selector
from .pcb_drc_source_evidence import BoundDrcEvidence
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap

LENGTH_RULE_ID: DesignLintRuleId = "pcb.signal_path_unmapped_native_rule"
EDGE_CLEARANCE_RULE_ID: DesignLintRuleId = "pcb.signal_path_unmapped_edge_clearance_rule"
FROM_TO_LENGTH_RULE_ID: DesignLintRuleId = "pcb.signal_path_unmapped_from_to_length_rule"


def _unmapped_signal_path_rule_candidates(
    requirements: PcbSignalPathRuleMap,
    constraints: tuple[NativeRuleConstraint, ...],
    evidence: BoundDrcEvidence,
    *,
    current_net_names: Mapping[str, object],
    source_netlist_sha256: str,
    kicad_version: str,
    rule_id: DesignLintRuleId,
    constraint_name: str,
) -> tuple[Candidate, ...]:
    """Compare one supported native per-net constraint with the path map."""
    mapped_nets = {item.net.casefold() for item in requirements.paths}
    source_nets: dict[str, str] = {}
    for net_value in current_net_names:
        net = str(net_value)
        key = net.casefold()
        source_nets[key] = min(source_nets.get(key, net), net)
    groups: dict[tuple[str, str], list[NativeRuleConstraint]] = {}
    labels: dict[tuple[str, str], tuple[str, str]] = {}
    for constraint in constraints:
        if constraint.name != constraint_name or not constraint.rule_name.strip():
            continue
        net = native_exact_net_condition(constraint.condition)
        if net is None or net.casefold() not in source_nets or net.casefold() in mapped_nets:
            continue
        key = (constraint.rule_name.casefold(), net.casefold())
        groups.setdefault(key, []).append(constraint)
        prior = labels.get(key, (constraint.rule_name, net))
        labels[key] = (min(prior[0], constraint.rule_name), min(prior[1], net))

    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    bounds_key = (
        "native_length_bounds" if constraint_name == "length" else "native_edge_clearance_bounds"
    )
    candidates: list[Candidate] = []
    for key, matches in sorted(groups.items()):
        rule_name, net = labels[key]
        candidates.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{rule_name}: {net} is absent from signal-path coverage",
                message=(
                    f"The source-bound native {constraint_name} rule {rule_name!r} targets exact "
                    f"net {net!r}, which exists in the source netlist but is absent from "
                    "pcb_signal_path_rule_map while pcb.signal_path_rule_coverage is enabled. "
                    "Add an independently reviewed path if geometry review should cover it, "
                    "or disposition this prompt if the omission is intentional. This does not "
                    "infer that the net is critical or that a path requirement is missing."
                ),
                evidence={
                    "native_rule_name": tuple(sorted({item.rule_name for item in matches})),
                    "native_rule_count": (str(len(matches)),),
                    "net": (source_nets[net.casefold()],),
                    "map_basis": (requirements.basis,),
                    "map_sha256": (map_sha256,),
                    "native_conditions": tuple(sorted({item.condition for item in matches})),
                    bounds_key: tuple(
                        sorted(
                            f"min_nm={item.minimum_nm};max_nm={item.maximum_nm};"
                            f"issue={item.issue or item.bounds_issue or '<none>'}"
                            for item in matches
                        )
                    ),
                    "native_layers": tuple(
                        sorted({item.layer or "<all layers>" for item in matches})
                    ),
                    "native_severities": tuple(
                        sorted({item.severity or "<default>" for item in matches})
                    ),
                    "source_path": (evidence.rules_path,),
                    "source_sha256": (evidence.rules_sha256 or "<rules-file-absent>",),
                    "project_path": (evidence.project_path,),
                    "project_sha256": (evidence.project_sha256,),
                    "board_path": (evidence.board_path,),
                    "board_sha256": (evidence.board_sha256,),
                    "native_drc_path": (evidence.native_drc_path,),
                    "native_drc_sha256": (evidence.native_drc_sha256,),
                    "native_drc_kicad_version": (kicad_version,),
                    "source_netlist_sha256": (source_netlist_sha256,),
                    "native_summary_path": (evidence.native_summary_path,),
                    "native_summary_sha256": (evidence.native_summary_sha256,),
                },
            )
        )
    return tuple(candidates)


def unmapped_signal_path_length_rule_candidates(
    requirements: PcbSignalPathRuleMap,
    constraints: tuple[NativeRuleConstraint, ...],
    evidence: BoundDrcEvidence,
    *,
    current_net_names: Mapping[str, object],
    source_netlist_sha256: str,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt about exact native length-rule nets absent from path coverage."""
    return _unmapped_signal_path_rule_candidates(
        requirements,
        constraints,
        evidence,
        current_net_names=current_net_names,
        source_netlist_sha256=source_netlist_sha256,
        kicad_version=kicad_version,
        rule_id=LENGTH_RULE_ID,
        constraint_name="length",
    )


def unmapped_signal_path_edge_clearance_rule_candidates(
    requirements: PcbSignalPathRuleMap,
    constraints: tuple[NativeRuleConstraint, ...],
    evidence: BoundDrcEvidence,
    *,
    current_net_names: Mapping[str, object],
    source_netlist_sha256: str,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt about exact native edge-clearance nets absent from path coverage."""
    return _unmapped_signal_path_rule_candidates(
        requirements,
        constraints,
        evidence,
        current_net_names=current_net_names,
        source_netlist_sha256=source_netlist_sha256,
        kicad_version=kicad_version,
        rule_id=EDGE_CLEARANCE_RULE_ID,
        constraint_name="edge_clearance",
    )


def unmapped_signal_path_from_to_length_rule_candidates(
    requirements: PcbSignalPathRuleMap,
    constraints: tuple[NativeRuleConstraint, ...],
    evidence: BoundDrcEvidence,
    *,
    current_net_names: Mapping[str, tuple[str, ...]],
    source_netlist_sha256: str,
    kicad_version: str,
) -> tuple[Candidate, ...]:
    """Prompt about exact native pad pairs omitted from signal-path coverage."""
    mapped_pairs = {
        frozenset(
            (drc_pad_selector(path.from_pad).casefold(), drc_pad_selector(path.to_pad).casefold())
        )
        for path in requirements.paths
    }
    pad_nets: dict[str, set[str]] = {}
    source_net_labels: dict[str, str] = {}
    for net_value, members in current_net_names.items():
        net = str(net_value)
        net_key = net.casefold()
        source_net_labels[net_key] = min(source_net_labels.get(net_key, net), net)
        for member in members:
            if member.count(".") != 1:
                continue
            selector = drc_pad_selector(member).casefold()
            pad_nets.setdefault(selector, set()).add(net_key)

    groups: dict[tuple[str, frozenset[str]], list[NativeRuleConstraint]] = {}
    labels: dict[tuple[str, frozenset[str]], tuple[str, str, tuple[str, str]]] = {}
    for constraint in constraints:
        if constraint.name != "length" or not constraint.rule_name.strip():
            continue
        endpoints = native_exact_from_to_condition(constraint.condition)
        if endpoints is None:
            continue
        endpoint_keys = tuple(item.casefold() for item in endpoints)
        pair_key = frozenset(endpoint_keys)
        if len(pair_key) != 2 or pair_key in mapped_pairs:
            continue
        first_nets = pad_nets.get(endpoint_keys[0], set())
        second_nets = pad_nets.get(endpoint_keys[1], set())
        if len(first_nets) != 1 or first_nets != second_nets:
            continue
        net_key = next(iter(first_nets))
        if net_key not in source_net_labels:
            continue
        key = (constraint.rule_name.casefold(), pair_key)
        groups.setdefault(key, []).append(constraint)
        prior = labels.get(key, (constraint.rule_name, net_key, endpoints))
        labels[key] = (
            min(prior[0], constraint.rule_name),
            min(prior[1], net_key),
            min(prior[2], endpoints),
        )

    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    candidates: list[Candidate] = []
    for key, matches in sorted(groups.items()):
        rule_name, net_key, endpoints = labels[key]
        first, second = endpoints
        net = source_net_labels[net_key]
        candidates.append(
            Candidate(
                rule_id=FROM_TO_LENGTH_RULE_ID,
                subject=f"{rule_name}: {first} to {second} is absent from signal-path coverage",
                message=(
                    f"The source-bound native length rule {rule_name!r} targets exact pads "
                    f"{first!r} and {second!r}, which the source netlist places on {net!r}, "
                    "but that endpoint pair is absent from pcb_signal_path_rule_map while "
                    "pcb.signal_path_rule_coverage is enabled. Add an independently reviewed "
                    "path if geometry review should cover it, or disposition this prompt if the "
                    "omission is intentional. This does not infer that the path is critical or "
                    "that a path requirement is missing."
                ),
                evidence={
                    "native_rule_name": tuple(sorted({item.rule_name for item in matches})),
                    "native_rule_count": (str(len(matches)),),
                    "net": (net,),
                    "from_to_pads": (f"{first} -> {second}",),
                    "map_basis": (requirements.basis,),
                    "map_sha256": (map_sha256,),
                    "native_conditions": tuple(sorted({item.condition for item in matches})),
                    "native_length_bounds": tuple(
                        sorted(
                            f"min_nm={item.minimum_nm};max_nm={item.maximum_nm};"
                            f"issue={item.issue or item.bounds_issue or '<none>'}"
                            for item in matches
                        )
                    ),
                    "native_layers": tuple(
                        sorted({item.layer or "<all layers>" for item in matches})
                    ),
                    "native_severities": tuple(
                        sorted({item.severity or "<default>" for item in matches})
                    ),
                    "source_path": (evidence.rules_path,),
                    "source_sha256": (evidence.rules_sha256 or "<rules-file-absent>",),
                    "project_path": (evidence.project_path,),
                    "project_sha256": (evidence.project_sha256,),
                    "board_path": (evidence.board_path,),
                    "board_sha256": (evidence.board_sha256,),
                    "native_drc_path": (evidence.native_drc_path,),
                    "native_drc_sha256": (evidence.native_drc_sha256,),
                    "native_drc_kicad_version": (kicad_version,),
                    "source_netlist_sha256": (source_netlist_sha256,),
                    "native_summary_path": (evidence.native_summary_path,),
                    "native_summary_sha256": (evidence.native_summary_sha256,),
                },
            )
        )
    return tuple(candidates)
