"""Explore exact net membership and one neighboring component hop."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from .connectivity_view_html import render_connectivity_view
from .connectivity_view_models import (
    AdjacentNet,
    ComponentNeighborhood,
    ConnectivityPin,
    ConnectivityViewReport,
)
from .contract_coach import receipt_directory
from .contracts import write_model
from .electrical_view_evidence import load_electrical_view_evidence
from .evidence import digest
from .grounding_models import GroundingAnalysis
from .models import NetlistContract
from .netlist_membership import net_pin_membership
from .power_connectivity_models import PowerConnectivityAnalysis

MAX_SELECTED_PINS = 300
MAX_COMPONENTS = 150
MAX_NEIGHBOR_PINS = 1000


def _authored(contract: object, net: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect only exact, explicit ground and power membership for this net."""
    from .electrical_analysis_contract_models import ElectricalAnalysisContract

    if not isinstance(contract, ElectricalAnalysisContract):
        raise TypeError("Expected an electrical analysis contract")
    roles: list[str] = []
    pins: list[str] = []
    if isinstance(contract.grounding, GroundingAnalysis):
        for domain in contract.grounding.domains:
            if domain.net == net:
                roles.append(f"GROUND_DOMAIN:{domain.net}")
                pins.extend(domain.pins)
    if isinstance(contract.power_connectivity, PowerConnectivityAnalysis):
        for rail in contract.power_connectivity.rails:
            if rail.net == net:
                roles.append(f"POWER_RAIL:{rail.id}")
                pins.extend(
                    pin
                    for group in rail.source_groups
                    for endpoint in group.endpoints
                    for pin in endpoint.pins
                )
                pins.extend(
                    pin
                    for load in rail.loads
                    for endpoint in load.endpoints
                    for pin in endpoint.pins
                )
    return tuple(roles), tuple(dict.fromkeys(pins))


def _neighborhoods(net: str, observed: NetlistContract | None) -> tuple[ComponentNeighborhood, ...]:
    if observed is None or net not in observed.nets:
        return ()
    selected = observed.nets[net]
    if len(selected) > MAX_SELECTED_PINS:
        raise ValueError("Selected net has too many observed pins for the bounded view")
    by_component: dict[str, list[str]] = defaultdict(list)
    reference_spelling: dict[str, str] = {}
    for pin in selected:
        reference, separator, _number = pin.rpartition(".")
        if not separator or not reference:
            raise ValueError(f"Observed pin has no component reference: {pin}")
        key = reference.casefold()
        by_component[key].append(pin)
        reference_spelling.setdefault(key, reference)
    selected_keys = {pin.casefold() for pin in selected}
    if len(by_component) > MAX_COMPONENTS:
        raise ValueError("Selected net has too many components for the bounded view")
    others: dict[str, dict[str | None, list[str]]] = defaultdict(lambda: defaultdict(list))
    for name, pins in observed.nets.items():
        if name == net:
            continue
        for pin in pins:
            reference, separator, _number = pin.rpartition(".")
            key = reference.casefold()
            if separator and key in by_component and pin.casefold() not in selected_keys:
                others[key][name].append(pin)
    for pins in observed.unconnected_nets.values():
        for pin in pins:
            reference, separator, _number = pin.rpartition(".")
            key = reference.casefold()
            if separator and key in by_component and pin.casefold() not in selected_keys:
                others[key][None].append(pin)
    if sum(len(pins) for groups in others.values() for pins in groups.values()) > MAX_NEIGHBOR_PINS:
        raise ValueError("Selected net has too many neighboring pins for the bounded view")
    symbols = {key.casefold(): value for key, value in observed.component_symbols.items()}
    components = {key.casefold(): value for key, value in observed.components.items()}
    dnp = {item.casefold() for item in observed.dnp_components}
    result: list[ComponentNeighborhood] = []
    for key in sorted(by_component):
        adjacent = tuple(
            AdjacentNet(
                net=name,
                pins=tuple(sorted(set(pins))),
                state="UNCONNECTED" if name is None else "CONNECTED",
            )
            for name, pins in sorted(others.get(key, {}).items(), key=lambda item: item[0] or "")
        )
        component = components.get(key)
        result.append(
            ComponentNeighborhood(
                reference=reference_spelling[key],
                selected_pins=tuple(sorted(set(by_component[key]))),
                other_nets=adjacent,
                observed_symbol=symbols.get(key),
                observed_footprint=component.footprint if component is not None else None,
                dnp=key in dnp,
            )
        )
    return tuple(result)


def build_connectivity_view(
    root: Path, receipt: Path, net: str, output: Path | None = None
) -> ConnectivityViewReport:
    """Render observed net membership with authored context when available."""
    root = root.resolve()
    evidence = load_electrical_view_evidence(root, receipt)
    roles, declared = _authored(evidence.contract, net)
    if len(declared) > MAX_SELECTED_PINS:
        raise ValueError("Selected net has too many authored pins for the bounded view")
    if not roles and (evidence.observed is None or net not in evidence.observed.nets):
        raise ValueError(f"Selected net {net!r} has no exact authored or retained observation")
    membership = net_pin_membership(net, declared, evidence.observed)
    if len(membership) > MAX_SELECTED_PINS + len(declared):
        raise ValueError("Selected net has too many pin rows for the bounded view")
    directory = receipt_directory(
        root,
        evidence.analysis.project_id,
        output
        or Path("build/connectivity-view") / f"{evidence.analysis.project_id}-{uuid4().hex[:12]}",
    )
    report = ConnectivityViewReport(
        project_id=evidence.analysis.project_id,
        net=net,
        authored_roles=roles,
        source_receipt=evidence.report_path.relative_to(root).as_posix(),
        source_report_sha256=evidence.report_sha256,
        requirements_sha256=evidence.requirements_sha256,
        observed_sha256=evidence.observed_sha256,
        native_netlist_sha256=evidence.native_sha256,
        source_hashes=evidence.analysis.source.files_sha256 if evidence.analysis.source else {},
        source_status=evidence.source_status,
        observation_status="RETAINED" if evidence.observed is not None else "UNREVIEWED",
        pins=tuple(
            ConnectivityPin(
                pin=item.pin,
                expected_net=item.expected_net,
                observed_nets=item.observed_nets,
                status=item.status,
            )
            for item in membership
        ),
        components=_neighborhoods(net, evidence.observed),
        issues=("No authored ground or power relationship selected for this exact net.",)
        if not roles
        else (),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_connectivity_view(root, report), encoding="utf-8")
    evidence.verify()
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "connectivity-view.json", report)
    return report
