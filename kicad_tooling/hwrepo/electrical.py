"""Reviewed grounding requirements, conservative power budgets and model bindings."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from ..validate import hashes
from .contracts import parse_model_text, read_model, repo_path
from .discovery import load_config, load_registry
from .models import (
    AnalysisNotApplicable,
    AnalysisPending,
    ElectricalAnalysisContract,
    ElectricalCheck,
    FrequencyAnalysis,
    GroundingAnalysis,
    HighFrequencyAnalysis,
    NetlistContract,
    PowerAnalysis,
    ProjectConfig,
    ProjectKind,
    ProjectManifest,
    TransientAnalysis,
)

SimulationCase = TransientAnalysis | FrequencyAnalysis


def regular_input_bytes(path: Path) -> bytes:
    """Read stable regular analysis input without following links or blocking on a FIFO."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"Electrical input must be a regular file: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"Electrical input must be a regular file: {path}")
        data = stream.read()
        after = os.fstat(stream.fileno())
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
    ):
        raise ValueError(f"Electrical input changed while reading: {path}")
    return data


def model_digest(path: Path) -> str:
    """Hash exactly the regular model bytes that are safe to read."""
    return hashlib.sha256(regular_input_bytes(path)).hexdigest()


def selected_config(root: Path, project_id: str) -> ProjectConfig:
    project = next((p for p in load_registry(root).projects if p.id == project_id), None)
    if project is None:
        raise ValueError(f"Unknown project {project_id!r}")
    return load_config(root, project.config)


def simulation_cases(contract: ElectricalAnalysisContract) -> tuple[SimulationCase, ...]:
    cases: list[SimulationCase] = []
    if isinstance(contract.power, PowerAnalysis):
        cases.extend((*contract.power.startup, *contract.power.steady_state))
    if isinstance(contract.high_frequency, HighFrequencyAnalysis):
        cases.extend((*contract.high_frequency.sweeps, *contract.high_frequency.waveforms))
    return tuple(cases)


def load_analysis(root: Path, config: ProjectConfig) -> ElectricalAnalysisContract | None:
    if config.electrical is None:
        return None
    if config.kind not in {ProjectKind.PCB, ProjectKind.SCHEMATIC}:
        raise ValueError("Electrical analysis requires an authoritative pcb or schematic project")
    contract = parse_model_text(
        regular_input_bytes(repo_path(root, config.electrical)).decode("utf-8"),
        ElectricalAnalysisContract,
    )
    if contract.project_id != config.project_id:
        raise ValueError("Electrical contract belongs to another project")
    return contract


def bound_inputs(root: Path, config: ProjectConfig,
                 contract: ElectricalAnalysisContract) -> dict[str, str]:
    """Check reviewed model/design hashes and inventory every input used by this run."""
    root = root.resolve()
    source = hashes(root, config.source_roots)
    if set(source) != set(config.required_inputs):
        raise ValueError("Repair the declared design source inventory before electrical analysis")
    project = next(p for p in load_registry(root).projects if p.id == config.project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    checks_path = repo_path(manifest_path.parent, manifest.checks)
    inputs = dict(source)
    for path in (manifest_path, checks_path, repo_path(root, config.electrical or "")):
        inputs[path.relative_to(root).as_posix()] = model_digest(path)
    for case in simulation_cases(contract):
        if dict(case.source_sha256) != source:
            raise ValueError(f"{case.id}: stale or incomplete reviewed design source hashes")
        for name, expected in case.model_sha256.items():
            path = repo_path(root, name)
            if not path.is_relative_to(manifest_path.parent) and name not in config.required_inputs:
                raise ValueError(f"{case.id}: model outside project is not a declared shared input: {name}")
            if "build" in path.relative_to(root).parts:
                raise ValueError(f"{case.id}: generated build output cannot be a model source")
            actual = model_digest(path)
            if actual != expected:
                raise ValueError(f"{case.id}: stale reviewed model hash: {name}")
            inputs[name] = actual
    return inputs


def grounding_checks(spec: GroundingAnalysis | AnalysisNotApplicable | AnalysisPending,
                     observed: NetlistContract) -> tuple[ElectricalCheck, ...]:
    if isinstance(spec, AnalysisPending):
        return (ElectricalCheck(id="grounding", status="NOT_CONFIGURED", detail=spec.reason),)
    if isinstance(spec, AnalysisNotApplicable):
        return (ElectricalCheck(id="grounding", status="NOT_APPLICABLE", detail=spec.reason),)
    results: list[ElectricalCheck] = []
    covered: set[str] = set()
    pin_nets: dict[str, set[str]] = {}
    for name, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(name)
    for domain in spec.domains:
        expected = set(domain.pins)
        actual = set(observed.nets.get(domain.net, ()))
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        multiple = sorted(pin for pin in expected if pin_nets.get(pin) != {domain.net})
        missing_components = sorted(
            pin for pin in expected if pin.rsplit(".", 1)[0] not in observed.components
        )
        covered.update(pin.rsplit(".", 1)[0] for pin in expected)
        failed = bool(missing or extra or multiple or missing_components)
        results.append(ElectricalCheck(
            id=f"grounding/{domain.net}", status="FAIL" if failed else "PASS",
            detail=(f"Missing pins={missing}; unexpected pins={extra}; wrong/ambiguous net={multiple}; "
                    f"unknown components={missing_components}" if failed else
                    f"All {len(expected)} declared ground pins match the exported schematic net."),
        ))
    exemptions = set(spec.exempt_components)
    components = set(observed.components)
    missing_coverage = sorted(components - covered - exemptions)
    stale = sorted((covered | exemptions) - components)
    conflicting = sorted(covered & exemptions)
    results.append(ElectricalCheck(
        id="grounding/component-coverage",
        status="FAIL" if missing_coverage or stale or conflicting else "PASS",
        detail=(f"Components without ground-pin review={missing_coverage}; "
                f"unknown components={stale}; grounded and exempt={conflicting}"),
    ))
    return tuple(results)


def power_budget_checks(spec: PowerAnalysis | AnalysisNotApplicable | AnalysisPending) -> tuple[ElectricalCheck, ...]:
    if isinstance(spec, AnalysisPending):
        return (ElectricalCheck(id="power", status="NOT_CONFIGURED", detail=spec.reason),)
    if isinstance(spec, AnalysisNotApplicable):
        return (ElectricalCheck(id="power", status="NOT_APPLICABLE", detail=spec.reason),)
    results: list[ElectricalCheck] = []
    for rail in spec.rails:
        steady = sum(load.steady_a for load in rail.loads)
        # A load cannot contribute less than its steady demand to a worst-case startup budget.
        peak = sum(max(load.startup_a, load.steady_a) for load in rail.loads)
        duration = max(load.startup_s for load in rail.loads)
        for name, value, limit, unit in (
            ("steady-current", steady, rail.continuous_limit_a, "A"),
            ("startup-current", peak, rail.peak_limit_a, "A"),
            ("startup-duration", duration if peak > rail.continuous_limit_a else 0.0,
             rail.peak_duration_limit_s, "s"),
        ):
            results.append(ElectricalCheck(
                id=f"power/{rail.id}/{name}", status="PASS" if value <= limit else "FAIL",
                observed=value, unit=unit, detail=f"Simultaneous load budget {value:g} {unit}; limit {limit:g} {unit}.",
            ))
        results.append(ElectricalCheck(
            id=f"power/{rail.id}/steady-power", status="PASS", observed=steady * rail.voltage_v,
            unit="W", detail="Calculated input demand at the declared nominal rail voltage; not thermal validation.",
        ))
    return tuple(results)


def pending_sections(contract: ElectricalAnalysisContract) -> tuple[str, ...]:
    return tuple(name for name, section in (
        ("grounding", contract.grounding), ("power", contract.power),
        ("high_frequency", contract.high_frequency),
    ) if isinstance(section, AnalysisPending))


def policy_issues(root: Path, config: ProjectConfig) -> tuple[str, ...]:
    """Portable checks validate requirements/models/budgets, never claim a simulation ran."""
    try:
        contract = load_analysis(root, config)
        if contract is None:
            return ()
        pending = pending_sections(contract)
        if pending:
            return ((f"Pending electrical requirements: {', '.join(pending)}. "
                     "Complete tests/electrical.json using the electrical quickstart."),)
        bound_inputs(root, config, contract)
        from .spice import expanded_deck

        for case in simulation_cases(contract):
            expanded_deck(root, case)
        return tuple(f"{row.id}: {row.detail}" for row in power_budget_checks(contract.power)
                     if row.status == "FAIL")
    except (OSError, ValueError) as exc:
        return (str(exc),)
