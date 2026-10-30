"""Render one authored power rail with checked netlist and budget context."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from .contract_coach import receipt_directory
from .contracts import write_model
from .electrical import power_budget_checks
from .electrical_simulation_models import PowerAnalysis, PowerRail
from .electrical_view_evidence import load_electrical_view_evidence
from .evidence import digest
from .models import NetlistContract
from .netlist_membership import PinMembership, net_pin_membership
from .power_connectivity import power_connectivity_checks
from .power_connectivity_models import (
    PowerConnectivityAnalysis,
    PowerLoadConnectivityRequirement,
    PowerPinEndpointRequirement,
    PowerSourceGroupRequirement,
)
from .power_tree_view_html import render_power_tree
from .power_tree_view_models import (
    PowerTreeBudget,
    PowerTreeEndpoint,
    PowerTreePin,
    PowerTreeRelationship,
    PowerTreeViewReport,
)

RelationshipStatus = Literal["PASS", "FAIL", "UNREVIEWED"]
ObservedIdentity = tuple[str | None, str, bool]


def _observed_identities(observed: NetlistContract | None) -> dict[str, ObservedIdentity]:
    if observed is None:
        return {}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    return {
        reference.casefold(): (
            symbols.get(reference.casefold()),
            component.footprint,
            reference.casefold() in dnp,
        )
        for reference, component in observed.components.items()
    }


def _budget(spec: PowerAnalysis | None, rail: PowerRail | None) -> PowerTreeBudget | None:
    if spec is None or rail is None:
        return None
    checks = {item.id: item for item in power_budget_checks(spec)}

    def status(name: str) -> Literal["PASS", "FAIL"]:
        result = checks[f"power/{rail.id}/{name}"].status
        if result == "PASS" or result == "FAIL":
            return result
        raise ValueError("Authored power budget did not produce comparable checks")

    return PowerTreeBudget(
        voltage_v=rail.voltage_v,
        continuous_limit_a=rail.continuous_limit_a,
        peak_limit_a=rail.peak_limit_a,
        peak_duration_limit_s=rail.peak_duration_limit_s,
        steady_demand_a=sum(load.steady_a for load in rail.loads),
        startup_demand_a=sum(max(load.startup_a, load.steady_a) for load in rail.loads),
        startup_duration_assessed_s=checks[f"power/{rail.id}/startup-duration"].observed or 0.0,
        steady_status=status("steady-current"),
        startup_status=status("startup-current"),
        duration_status=status("startup-duration"),
    )


def _endpoint(
    requirement: PowerPinEndpointRequirement,
    pins: dict[str, PinMembership],
    identities: dict[str, ObservedIdentity],
    observation_available: bool,
) -> PowerTreeEndpoint:
    identity = identities.get(requirement.reference.casefold())
    return PowerTreeEndpoint(
        id=requirement.id,
        reference=requirement.reference,
        symbol=requirement.symbol,
        footprint=requirement.footprint,
        observed_component=(
            "RETAINED"
            if identity is not None
            else "MISSING"
            if observation_available
            else "UNREVIEWED"
        ),
        observed_symbol=identity[0] if identity is not None else None,
        observed_footprint=identity[1] if identity is not None else None,
        observed_dnp=identity[2] if identity is not None else None,
        pins=tuple(
            PowerTreePin(
                pin=pin,
                observed_nets=pins[pin].observed_nets,
                status=pins[pin].status,
            )
            for pin in requirement.pins
        ),
    )


def _source_group(
    group: PowerSourceGroupRequirement,
    rail_id: str,
    checks: dict[str, tuple[RelationshipStatus, str]],
    pins: dict[str, PinMembership],
    identities: dict[str, ObservedIdentity],
    observation_available: bool,
) -> PowerTreeRelationship:
    status, detail = checks.get(
        f"power-connectivity/{rail_id}/source/{group.id}",
        ("UNREVIEWED", "No retained native netlist was available."),
    )
    return PowerTreeRelationship(
        id=group.id,
        basis=group.basis,
        role="SOURCE_GROUP",
        selection=group.selection,
        check_status=status,
        check_detail=detail,
        endpoints=tuple(
            _endpoint(endpoint, pins, identities, observation_available)
            for endpoint in group.endpoints
        ),
    )


def _load(
    requirement: PowerLoadConnectivityRequirement,
    rail_id: str,
    checks: dict[str, tuple[RelationshipStatus, str]],
    pins: dict[str, PinMembership],
    budget_rail: PowerRail | None,
    identities: dict[str, ObservedIdentity],
    observation_available: bool,
) -> PowerTreeRelationship:
    status, detail = checks.get(
        f"power-connectivity/{rail_id}/load/{requirement.id}",
        ("UNREVIEWED", "No retained native netlist was available."),
    )
    budget_load = (
        next((item for item in budget_rail.loads if item.id == requirement.id), None)
        if budget_rail is not None
        else None
    )
    return PowerTreeRelationship(
        id=requirement.id,
        basis=requirement.basis,
        role="LOAD",
        check_status=status,
        check_detail=detail,
        endpoints=tuple(
            _endpoint(endpoint, pins, identities, observation_available)
            for endpoint in requirement.endpoints
        ),
        steady_a=budget_load.steady_a if budget_load is not None else None,
        startup_a=budget_load.startup_a if budget_load is not None else None,
        startup_s=budget_load.startup_s if budget_load is not None else None,
    )


def build_power_tree_view(
    root: Path, receipt: Path, rail_id: str, output: Path | None = None
) -> PowerTreeViewReport:
    """Join an explicit rail map and optional native observation without inferring topology."""
    root = root.resolve()
    evidence = load_electrical_view_evidence(root, receipt)
    spec = evidence.contract.power_connectivity
    if not isinstance(spec, PowerConnectivityAnalysis):
        raise ValueError("Electrical receipt has no authored power-connectivity map")  # noqa: TRY004
    selected = [rail for rail in spec.rails if rail.id == rail_id]
    if len(selected) != 1:
        raise ValueError(f"Select one exact authored power rail; {rail_id!r} is absent")
    rail = selected[0]
    budget_spec = evidence.contract.power
    budget_rail = (
        next((item for item in budget_spec.rails if item.id == rail_id), None)
        if isinstance(budget_spec, PowerAnalysis)
        else None
    )
    authored_pins = tuple(
        pin for group in rail.source_groups for endpoint in group.endpoints for pin in endpoint.pins
    ) + tuple(pin for load in rail.loads for endpoint in load.endpoints for pin in endpoint.pins)
    memberships = net_pin_membership(rail.net, authored_pins, evidence.observed)
    pin_lookup = {item.pin: item for item in memberships if item.expected_net is not None}
    identities = _observed_identities(evidence.observed)
    checks: dict[str, tuple[RelationshipStatus, str]] = {}
    if evidence.observed is not None:
        for item in power_connectivity_checks(spec, evidence.observed):
            if item.status == "PASS" or item.status == "FAIL":
                checks[item.id] = (item.status, item.detail)
            else:
                raise ValueError(
                    "Native power connectivity check did not return a comparable status"
                )
    directory = receipt_directory(
        root,
        evidence.analysis.project_id,
        output
        or Path("build/power-tree-view") / f"{evidence.analysis.project_id}-{uuid4().hex[:12]}",
    )
    report = PowerTreeViewReport(
        project_id=evidence.analysis.project_id,
        rail_id=rail.id,
        net=rail.net,
        basis=rail.basis,
        analysis_status=evidence.analysis.status,
        source_receipt=evidence.report_path.relative_to(root).as_posix(),
        source_report_sha256=evidence.report_sha256,
        requirements_sha256=evidence.requirements_sha256,
        observed_sha256=evidence.observed_sha256,
        native_netlist_sha256=evidence.native_sha256,
        analysis_source_sha256=(
            evidence.analysis.source.files_sha256 if evidence.analysis.source is not None else {}
        ),
        observation_status="RETAINED" if evidence.observed is not None else "UNREVIEWED",
        source_status=evidence.source_status,
        source_groups=tuple(
            _source_group(
                group, rail.id, checks, pin_lookup, identities, evidence.observed is not None
            )
            for group in rail.source_groups
        ),
        loads=tuple(
            _load(
                load,
                rail.id,
                checks,
                pin_lookup,
                budget_rail,
                identities,
                evidence.observed is not None,
            )
            for load in rail.loads
        ),
        undeclared_pins=tuple(
            PowerTreePin(pin=item.pin, observed_nets=item.observed_nets, status=item.status)
            for item in memberships
            if item.status == "UNDECLARED"
        ),
        budget=_budget(
            budget_spec if isinstance(budget_spec, PowerAnalysis) else None, budget_rail
        ),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_power_tree(report), encoding="utf-8")
    evidence.verify()
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "power-tree-view.json", report)
    return report
