"""Create pending electrical requirements and capture unreviewed input hashes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

from ..validate import hashes
from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .discovery import load_registry
from .electrical import (
    load_analysis,
    model_digest,
    regular_input_bytes,
    selected_config,
    simulation_cases,
)
from .models import (
    AnalysisPending,
    ElectricalAnalysisContract,
    ElectricalInputInventory,
    ElectricalSetupReport,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
)

GUIDE = "docs/workflow/ELECTRICAL_ANALYSIS.md"


def initialize(
    root: Path, project_id: str, ngspice_version: str = "UNREVIEWED"
) -> ElectricalSetupReport:
    """Add only pending requirements; refuse to replace an existing authored contract."""
    root = root.resolve()
    config = selected_config(root, project_id)
    if config.kind not in {ProjectKind.PCB, ProjectKind.SCHEMATIC}:
        raise ValueError("Electrical setup needs an authoritative pcb or schematic project")
    if config.electrical is not None:
        raise ValueError(
            f"Electrical contract already configured: {config.electrical}; edit it or use --capture-inputs"
        )
    project = next(p for p in load_registry(root).projects if p.id == project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    checks = repo_path(manifest_path.parent, manifest.checks)
    before = regular_input_bytes(checks)
    contract = read_model(checks, ProjectTestContract)
    destination = repo_path(manifest_path.parent, "tests/electrical.json")
    if destination.exists():
        raise ValueError(f"Refusing to overwrite existing electrical requirements: {destination}")
    if destination == checks:
        raise ValueError("The electrical sidecar cannot replace the native test contract")
    starter = ElectricalAnalysisContract(
        project_id=project_id,
        ngspice_version=ngspice_version,
        grounding=AnalysisPending(
            reason="Review every component's required ground pins and domains."
        ),
        power=AnalysisPending(
            reason="Author derated rail/load limits and reviewed startup/steady-state models."
        ),
        high_frequency=AnalysisPending(
            reason="Determine frequency/edge requirements and reviewed AC/transient models."
        ),
    )
    data = starter.model_dump_json(indent=2) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    created = False
    try:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(data)
        created = True
        with tempfile.NamedTemporaryFile(
            dir=checks.parent, prefix=".electrical-", delete=False
        ) as stream:
            temporary = Path(stream.name)
        write_model(temporary, contract.model_copy(update={"electrical": "tests/electrical.json"}))
        if regular_input_bytes(checks) != before:
            raise ValueError(
                "Native test contract changed during setup; preserve the edit and retry"
            )
        os.chmod(temporary, checks.stat().st_mode & 0o777)
        os.replace(temporary, checks)
    except BaseException:
        if created and destination.is_file() and destination.read_text(encoding="utf-8") == data:
            destination.unlink()
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    relative = destination.relative_to(root).as_posix()
    return ElectricalSetupReport(
        project_id=project_id,
        contract=relative,
        changed=(relative, checks.relative_to(root).as_posix()),
        next_actions=(
            f"Open {relative}. All three sections are pending and cannot pass verification.",
            f"Follow {GUIDE} and templates/electrical/README.md to author requirements and models.",
            (
                f"Capture review inputs with python -B -m kicad_tooling.electrical --project {project_id} "
                "--capture-inputs --model <repository-relative-deck> (repeat --model for includes)."
            ),
            f"Run python -B -m kicad_tooling.template doctor --electrical --project-id {project_id} --format text.",
        ),
    )


def capture_inputs(
    root: Path, project_id: str, models: tuple[str, ...] = (), output: Path | None = None
) -> ElectricalInputInventory:
    """Record actual hashes in ignored output; never replace reviewed contract bindings."""
    root = root.resolve()
    config = selected_config(root, project_id)
    if config.kind not in {ProjectKind.PCB, ProjectKind.SCHEMATIC}:
        raise ValueError("Electrical inputs require a pcb or schematic project")
    project = next(p for p in load_registry(root).projects if p.id == project_id)
    island = repo_path(root, project.config).parent
    current = hashes(root, config.source_roots)
    if set(current) != set(config.required_inputs):
        raise ValueError("Repair the declared design inventory before capturing review inputs")
    names = set(models)
    if not names:
        contract = load_analysis(root, config)
        if contract is not None:
            names.update(name for case in simulation_cases(contract) for name in case.model_sha256)
    model_hashes: dict[str, str] = {}
    for name in sorted(names):
        path = repo_path(root, name)
        if "build" in Path(name).parts:
            raise ValueError(f"Generated build output cannot be a model source: {name}")
        if not path.is_relative_to(island) and name not in config.required_inputs:
            raise ValueError(f"Model must be project-local or a declared shared input: {name}")
        model_hashes[name] = model_digest(path)
    # A receipt must not combine hashes from designs changed midway through capture.
    if hashes(root, config.source_roots) != current or any(
        model_digest(repo_path(root, name)) != value for name, value in model_hashes.items()
    ):
        raise ValueError("Inputs changed during capture; rerun after saving the design")
    directory = receipt_directory(
        root,
        project_id,
        output or (Path("build/electrical-inputs") / f"{project_id}-{uuid4().hex[:12]}"),
    )
    report = ElectricalInputInventory(
        project_id=project_id,
        run_directory=str(directory),
        source_sha256=current,
        model_sha256=model_hashes,
        next_actions=(
            "UNREVIEWED: compare the models, assumptions and circuit mapping with the design.",
            "After review, copy source_sha256 and each case's applicable model_sha256 entries into the contract.",
            "Capture has not changed any approved hashes, limits or review decisions.",
        ),
    )
    write_model(directory / "inputs.json", report)
    return report
